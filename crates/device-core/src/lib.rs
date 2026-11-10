#![forbid(unsafe_code)]

use codec::{Decoder, Encoder, MAX_PACKET, Pcm};
use protocol::{Frame, Media, Received, Session};

pub const JITTER: usize = 4;
pub const QUEUE: usize = 8;
pub const PERIOD_NS: u64 = 20_000_000;
pub const MIN_SEND_GAP_NS: u64 = PERIOD_NS / 2;

#[derive(Default)]
pub struct Slots {
    next: u64,
    last: Option<u64>,
}

impl Slots {
    pub fn next(&self) -> u64 {
        self.next
    }

    /// Skip every expired slot. Also avoid closely spaced sends after a late slot.
    pub fn select(&mut self, elapsed: u64, count: u64) -> Option<u64> {
        let slot = elapsed / PERIOD_NS;
        if slot < self.next || slot >= count {
            self.next = self.next.max(slot.min(count));
            return None;
        }
        self.next = slot + 1;
        if self
            .last
            .is_some_and(|last| elapsed - last < MIN_SEND_GAP_NS)
        {
            return None;
        }
        Some(slot)
    }

    pub fn sent(&mut self, elapsed: u64) {
        self.last = Some(elapsed);
    }
}

#[derive(Default)]
pub struct Jitter {
    next: u64,
    frames: [Option<(u64, Media)>; QUEUE],
    count: usize,
    pub peak: usize,
}

impl Jitter {
    pub fn range(&self, local_slot: u64) -> std::ops::Range<u64> {
        self.next..(self.next.saturating_add(QUEUE as u64)).min(local_slot.saturating_add(2))
    }

    pub fn push(&mut self, slot: u64, media: Media) -> bool {
        if !(self.next..self.next.saturating_add(QUEUE as u64)).contains(&slot) {
            return false;
        }
        let index = slot as usize % QUEUE;
        if self.frames[index].is_some() {
            return false;
        }
        self.frames[index] = Some((slot, media));
        self.count += 1;
        self.peak = self.peak.max(self.count);
        true
    }

    pub fn pop(&mut self) -> Option<Media> {
        let index = self.next as usize % QUEUE;
        self.next += 1;
        self.frames[index].take().map(|(_, media)| {
            self.count -= 1;
            media
        })
    }

    /// Drop stale media after a wall-clock scheduling gap with bounded work.
    pub fn skip_to(&mut self, slot: u64) {
        if slot <= self.next {
            return;
        }
        for entry in &mut self.frames {
            if entry.is_some_and(|(queued, _)| queued < slot) {
                *entry = None;
                self.count -= 1;
            }
        }
        self.next = slot;
    }
}

pub struct Device {
    session: Session,
    encoder: Encoder,
    decoder: Decoder,
    pub jitter: Jitter,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Playout {
    Audio,
    Filler,
    Loss,
    Malformed,
}

impl Device {
    pub fn new(session: Session) -> Result<Self, &'static str> {
        Ok(Self {
            session,
            encoder: Encoder::new()?,
            decoder: Decoder::new()?,
            jitter: Jitter::default(),
        })
    }

    pub fn encode(&mut self, pcm: Option<&Pcm>) -> Media {
        let mut buffer = [0; MAX_PACKET];
        pcm.and_then(|pcm| self.encoder.encode(pcm, &mut buffer).ok())
            .and_then(|len| Frame::new(&buffer[..len]).ok())
            .map_or(Media::Filler, Media::Audio)
    }

    pub fn seal(
        &mut self,
        slot: u64,
        media: Media,
    ) -> Result<[u8; protocol::RECORD], protocol::Error> {
        self.session.media(slot, media)
    }

    pub fn ingest(&mut self, wire: &[u8], slot: u64) -> Result<(), protocol::Error> {
        match self.session.receive(wire, self.jitter.range(slot))? {
            Received::Media(slot, media) if self.jitter.push(slot, media) => Ok(()),
            _ => Err(protocol::Error::State),
        }
    }

    pub fn playout(&mut self) -> (Pcm, Playout) {
        match self.jitter.pop() {
            Some(Media::Audio(frame)) => match self.decoder.audio(frame.as_slice()) {
                Ok(pcm) => (pcm, Playout::Audio),
                Err(_) => (self.decoder.conceal(), Playout::Malformed),
            },
            Some(Media::Filler) => {
                self.decoder.conceal(); // advance codec time without audible PLC on mute
                ([0; codec::SAMPLES], Playout::Filler)
            }
            None => (self.decoder.conceal(), Playout::Loss),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn absolute_slots_skip_and_never_catch_up() {
        let mut slots = Slots::default();
        assert_eq!(slots.select(18_000_000, 7), Some(0));
        slots.sent(18_000_000);
        assert_eq!(slots.select(PERIOD_NS, 7), None);
        assert_eq!(slots.select(5 * PERIOD_NS, 7), Some(5));
        slots.sent(5 * PERIOD_NS);
        assert_eq!(slots.select(5 * PERIOD_NS, 7), None);
        assert_eq!(slots.select(7 * PERIOD_NS, 7), None);
        assert_eq!(slots.next(), 7);
    }
}
