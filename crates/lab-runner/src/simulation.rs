use crate::{Event, PEERS, Result, check};
use device_core::{Device, JITTER, PERIOD_NS, Playout, Slots};
use link::{ASSEMBLIES, DATAGRAM, Drop, Reassembly, fragments};
use protocol::{Error, Frame, Media, RECORD, fixtures};
use std::collections::VecDeque;

const SLOTS: u64 = 20;
const CAPACITY: usize = 8;
type Fragment = ([u8; DATAGRAM], usize);

struct Network {
    pending: VecDeque<(u64, u32, [u8; RECORD])>,
    fragments: Reassembly,
}

impl Network {
    fn new() -> Self {
        Self {
            pending: VecDeque::with_capacity(CAPACITY),
            fragments: Reassembly::default(),
        }
    }

    fn enqueue(&mut self, delivery: u64, id: u32, wire: [u8; RECORD]) -> bool {
        if self.pending.len() == CAPACITY {
            return false;
        }
        self.pending.push_back((delivery, id, wire));
        true
    }

    fn deliver(
        &mut self,
        tick: u64,
        target: &mut Device,
        direction: [usize; 5],
    ) -> Vec<std::result::Result<(), Error>> {
        let mut results = Vec::with_capacity(CAPACITY);
        for _ in 0..self.pending.len() {
            let (delivery, id, wire) = self.pending.pop_front().expect("bounded work list");
            if delivery > tick {
                self.pending.push_back((delivery, id, wire));
                continue;
            }
            for edge in direction.windows(2).skip(1) {
                trace(
                    "virtual-link",
                    tick,
                    "forward",
                    (edge[0], edge[1]),
                    "opaque fragments traverse simulated link",
                    "forwarded",
                );
            }
            let parts: Vec<Fragment> = fragments(id, &wire).unwrap().collect();
            for (bytes, len) in parts.iter().rev() {
                if let Ok(Some((assembled, size))) = self.fragments.push(&bytes[..*len], tick) {
                    let result = target.ingest(&assembled[..size], tick);
                    trace(
                        "virtual-link",
                        tick,
                        if result.is_ok() { "receive" } else { "reject" },
                        (direction[3], direction[4]),
                        "authenticate complete record",
                        if result.is_ok() {
                            "buffered"
                        } else {
                            "rejected"
                        },
                    );
                    results.push(result);
                }
            }
        }
        results
    }
}

fn trace(
    test: &'static str,
    tick: u64,
    action: &'static str,
    edge: (usize, usize),
    expected: &'static str,
    observed: &'static str,
) {
    Event {
        test,
        tick,
        action,
        from: PEERS[edge.0],
        to: PEERS[edge.1],
        expected,
        observed,
        status: "info",
    }
    .emit();
}

fn verdict(
    test: &'static str,
    expected: &'static str,
    observed: &'static str,
    pass: bool,
) -> Result<()> {
    Event {
        test,
        tick: 0,
        action: "verdict",
        from: "",
        to: "",
        expected,
        observed,
        status: if pass { "pass" } else { "fail" },
    }
    .emit();
    check(pass, test)
}

fn virtual_link() -> Result<()> {
    let (mut a, mut b) = fixtures::sessions(1)?;
    fixtures::activate(&mut a, &mut b)?;
    let (mut a, mut b) = (Device::new(a)?, Device::new(b)?);
    let (mut ab, mut ba) = (Network::new(), Network::new());
    let mut older = [0; RECORD];
    let mut rejected = Vec::new();
    let mut observed = Vec::new();
    let mut clock = 0;
    let (mut send_a, mut send_b) = (Slots::default(), Slots::default());
    for tick in 0..SLOTS + JITTER as u64 {
        if tick < SLOTS {
            check(
                send_a.select(clock, SLOTS) == Some(tick),
                "virtual Alice deadline",
            )?;
            check(
                send_b.select(clock, SLOTS) == Some(tick),
                "virtual Bob deadline",
            )?;
            send_a.sent(clock);
            send_b.sent(clock);
            let pcm_a = if tick == 9 {
                [0; codec::SAMPLES]
            } else {
                codec::synthetic(true, tick)
            };
            let pcm_b = codec::synthetic(false, tick);
            let media_a = a.encode((tick != 8).then_some(&pcm_a));
            let media_b = b.encode(Some(&pcm_b));
            check(
                matches!(media_a, Media::Filler) == (tick == 8),
                "silence, mute or codec underrun mismatch",
            )?;
            check(
                matches!(media_b, Media::Audio(_)),
                "encoder underrun in virtual call",
            )?;
            let wire_a = a.seal(tick, media_a)?;
            let wire_b = b.seal(tick, media_b)?;
            for edge in [(0, 1), (4, 3)] {
                trace(
                    "virtual-link",
                    tick,
                    "send",
                    edge,
                    "one 128-byte record",
                    "scheduled",
                );
            }
            match tick {
                1 => trace(
                    "virtual-link",
                    tick,
                    "drop",
                    (2, 3),
                    "loss uses PLC",
                    "relay dropped record",
                ),
                2 => {
                    trace(
                        "virtual-link",
                        tick,
                        "delay",
                        (2, 3),
                        "delayed record arrives after next slot",
                        "held for two ticks",
                    );
                    assert!(ab.enqueue(tick + 2, tick as u32, wire_a));
                }
                5 => {
                    let mut corrupt = wire_a;
                    corrupt[35] ^= 0x10;
                    trace(
                        "virtual-link",
                        tick,
                        "tamper",
                        (2, 3),
                        "invalid tag",
                        "relay changed ciphertext",
                    );
                    assert!(ab.enqueue(tick, tick as u32, corrupt));
                }
                6 => {
                    trace(
                        "virtual-link",
                        tick,
                        "replay",
                        (1, 3),
                        "duplicate across colluding phones",
                        "Phone B reinjected Phone A capture",
                    );
                    assert!(ab.enqueue(tick, 90, older));
                    assert!(ab.enqueue(tick, tick as u32, wire_a));
                }
                7 => {
                    trace(
                        "virtual-link",
                        tick,
                        "inject",
                        (3, 4),
                        "forged counter and ciphertext rejected",
                        "Phone B fabricated record",
                    );
                    let mut invented = [0x5a; RECORD];
                    invented[..8].copy_from_slice(&10_000u64.to_le_bytes());
                    assert!(ab.enqueue(tick, 91, invented));
                    assert!(ab.enqueue(tick, tick as u32, wire_a));
                }
                _ => assert!(ab.enqueue(tick, tick as u32, wire_a)),
            }
            if tick == 0 {
                older = wire_a;
                trace(
                    "virtual-link",
                    tick,
                    "duplicate",
                    (2, 3),
                    "duplicate rejected",
                    "relay queued second copy with another link identifier",
                );
                assert!(ab.enqueue(tick, 80, wire_a));
            }
            assert!(ba.enqueue(tick, tick as u32, wire_b));
        }
        for result in ab.deliver(tick, &mut b, [0, 1, 2, 3, 4]) {
            if let Err(error) = result {
                rejected.push(error);
            }
        }
        check(
            ba.deliver(tick, &mut a, [4, 3, 2, 1, 0])
                .into_iter()
                .all(|result| result.is_ok()),
            "reverse direction transport",
        )?;
        if tick >= JITTER as u64 {
            let (_, a_played) = a.playout();
            let (b_pcm, b_played) = b.playout();
            check(
                a_played == Playout::Audio,
                "Alice should decode all reverse slots",
            )?;
            if b_played == Playout::Filler {
                check(
                    b_pcm.iter().all(|&sample| sample == 0),
                    "muted playout must be silent",
                )?;
            }
            trace(
                "virtual-link",
                tick,
                "playout",
                (0, 4),
                "audio, silence or bounded concealment",
                match b_played {
                    Playout::Audio => "decoded",
                    Playout::Filler => "muted",
                    Playout::Loss => "concealed",
                    Playout::Malformed => "malformed",
                },
            );
            observed.push(b_played);
        }
        clock += PERIOD_NS;
    }
    let correct = observed.iter().enumerate().all(|(slot, played)| {
        *played
            == match slot {
                1 | 5 => Playout::Loss,
                8 => Playout::Filler,
                _ => Playout::Audio,
            }
    });
    verdict(
        "virtual-link",
        "loss, delay, reorder, duplication, replay, tampering, injection and collusion handled",
        "compared all playout outcomes and four rejects",
        correct && rejected == [Error::Replay, Error::Auth, Error::Replay, Error::Auth],
    )
}

fn bounded_link() -> Result<()> {
    let mut parts = Reassembly::default();
    let mut net = Network::new();
    let wire = [0; RECORD];
    for id in 0..CAPACITY as u32 {
        assert!(net.enqueue(1, id, wire));
    }
    let backpressure = !net.enqueue(1, 99, wire);
    let mut rejected = 0;
    for id in 0..1024 {
        let (piece, len) = fragments(id, &wire).unwrap().next().unwrap();
        if parts.push(&piece[..len], 0) == Err(Drop::Full) {
            rejected += 1;
        }
    }
    trace(
        "fragment-flood",
        0,
        "inject",
        (3, 4),
        "limit incomplete assemblies",
        "1,024 incomplete records injected",
    );
    trace(
        "fragment-flood",
        0,
        "drop",
        (3, 4),
        "limit link queue",
        "backpressure on ninth record",
    );
    let malformed = parts.push(&[0; DATAGRAM + 1], 0) == Err(Drop::Shape);
    let fragments: Vec<_> = fragments(1000, &wire).unwrap().collect();
    let (piece, len) = fragments[2];
    let timeout = parts.push(&piece[..len], 3) == Ok(None);
    let duplicate = parts.push(&piece[..len], 3) == Err(Drop::Duplicate);
    let mut reconstructed = None;
    for (bytes, len) in [fragments[3], fragments[0], fragments[1]] {
        reconstructed = parts
            .push(&bytes[..len], 3)
            .map_err(|_| "reassembly rejected valid fragment")?;
    }
    verdict(
        "fragment-flood",
        "bounded flood, expiration, fragment duplication and backpressure",
        "checked limits, expired entries and reassembled out of order",
        backpressure
            && malformed
            && timeout
            && duplicate
            && parts.peak == ASSEMBLIES
            && rejected == 1024 - ASSEMBLIES
            && reconstructed == Some((wire, RECORD)),
    )
}

fn authenticated_peer() -> Result<()> {
    let (mut a, mut b) = fixtures::sessions(2)?;
    let early = fixtures::peer_record(&a, 2, 3, &[])?;
    let early_rejected = b.receive(&early, 0..8) == Err(Error::State);
    let commands_rejected = [("pair", 4), ("mic", 5), ("debug", 6), ("update", 7)]
        .into_iter()
        .all(|(label, kind)| {
            let record = fixtures::peer_record(&a, 2, kind, &[]).unwrap();
            let denied = b.receive(&record, 0..8) == Err(Error::Command);
            trace(
                "authenticated-peer",
                0,
                "reject",
                (0, 4),
                label,
                if denied { "rejected" } else { "accepted" },
            );
            denied
        });
    fixtures::activate(&mut a, &mut b)?;
    let forged = fixtures::peer_record(&a, 500_000, 3, &[])?;
    let mut b = Device::new(b)?;
    let far_rejected = b.ingest(&forged, 0) == Err(Error::Counter);
    // Invalid duration, truncated framing with a valid duration, and stereo.
    for (slot, bytes) in [&[0x18, 1][..], &[0x0b, 0x41], &[0x0c, 1]]
        .into_iter()
        .enumerate()
    {
        let frame = Frame::new(bytes)?;
        b.ingest(&a.media(slot as u64, Media::Audio(frame))?, slot as u64)?;
        check(
            b.playout().1 == Playout::Malformed,
            "authenticated malformed Opus must use PLC",
        )?;
        trace(
            "authenticated-peer",
            slot as u64,
            "reject",
            (0, 4),
            "validate Opus geometry and framing after authentication",
            "concealed malformed authenticated Opus",
        );
    }
    let old = a.media(3, Media::Filler)?;
    let (mut new_a, mut new_b) = fixtures::sessions(3)?;
    fixtures::activate(&mut new_a, &mut new_b)?;
    let fresh = new_a.media(3, Media::Filler)?;
    let reset = old[..8] == fresh[..8]
        && old != fresh
        && new_b.receive(&old, 0..8) == Err(Error::Auth)
        && new_b.receive(&fresh, 0..8).is_ok();
    verdict(
        "authenticated-peer",
        "early media, remote commands, counter poisoning and old-session replay denied",
        "rejected adversarial cases and accepted fresh ciphertext after reset",
        early_rejected && commands_rejected && far_rejected && reset,
    )
}

pub fn run() -> Result<()> {
    let failures: Vec<_> = [virtual_link(), bounded_link(), authenticated_peer()]
        .into_iter()
        .filter_map(Result::err)
        .collect();
    check(
        failures.is_empty(),
        &failures
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("; "),
    )
}
