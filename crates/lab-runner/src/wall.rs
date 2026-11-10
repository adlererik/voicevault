use crate::{Event, PEERS, Result, check, sandbox};
use call_state::Control;
use device_core::{Device, JITTER, MIN_SEND_GAP_NS, PERIOD_NS, Playout, Slots};
use link::{DATAGRAM, Reassembly, fragments};
use protocol::{CONTACT, Entropy, Identity, Media, OsEntropy, RECORD};
use serde::Serialize;
use std::{
    fs::{self, File},
    io::{self, BufWriter, Write},
    os::fd::AsRawFd,
    os::unix::net::UnixDatagram,
    path::Path,
    process::{Child, Command, Stdio},
    time::Duration,
};

const RECEIVE_BUDGET: usize = 64;
const TRACE_SLOTS: u64 = 24;
const TRACE_LIMIT: usize = 256;

#[derive(Default)]
pub struct Children(Vec<Child>);

impl Children {
    pub fn add(&mut self, child: Child) -> u32 {
        let pid = child.id();
        self.0.push(child);
        pid
    }
}

impl Drop for Children {
    fn drop(&mut self) {
        for child in &mut self.0 {
            let _ = child.kill();
        }
        for child in &mut self.0 {
            let _ = child.wait();
        }
    }
}

fn timespec(ns: u64) -> libc::timespec {
    libc::timespec {
        tv_sec: (ns / 1_000_000_000) as _,
        tv_nsec: (ns % 1_000_000_000) as _,
    }
}

fn now(clock: libc::clockid_t) -> u64 {
    let mut time = timespec(0);
    // SAFETY: time is a valid writable timespec and clocks are kernel constants.
    assert_eq!(unsafe { libc::clock_gettime(clock, &mut time) }, 0);
    time.tv_sec as u64 * 1_000_000_000 + time.tv_nsec as u64
}

fn mono() -> u64 {
    now(libc::CLOCK_MONOTONIC)
}

fn sleep_until(deadline: u64) -> io::Result<()> {
    let target = timespec(deadline);
    loop {
        // SAFETY: The absolute deadline is valid and the remainder is unused.
        let result = unsafe {
            libc::clock_nanosleep(
                libc::CLOCK_MONOTONIC,
                libc::TIMER_ABSTIME,
                &target,
                std::ptr::null_mut(),
            )
        };
        match result {
            0 => return Ok(()),
            libc::EINTR => {}
            error => return Err(io::Error::from_raw_os_error(error)),
        }
    }
}

fn affinity(cpu: Option<usize>) -> io::Result<Vec<usize>> {
    // SAFETY: cpu_set_t is a C bitset and zero is its empty representation.
    let mut set: libc::cpu_set_t = unsafe { std::mem::zeroed() };
    if let Some(cpu) = cpu {
        if cpu >= libc::CPU_SETSIZE as usize {
            return Err(io::Error::other("CPU is outside cpu_set_t"));
        }
        // SAFETY: cpu is within bounds and set is live.
        unsafe { libc::CPU_SET(cpu, &mut set) };
        // SAFETY: set has the supplied ABI size.
        if unsafe { libc::sched_setaffinity(0, size_of_val(&set), &set) } != 0 {
            return Err(io::Error::last_os_error());
        }
    }
    // SAFETY: set is writable for its supplied ABI size.
    if unsafe { libc::sched_getaffinity(0, size_of_val(&set), &mut set) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: Every queried index is within the bitset.
    Ok((0..libc::CPU_SETSIZE as usize)
        .filter(|&cpu| unsafe { libc::CPU_ISSET(cpu, &set) })
        .collect())
}

pub fn contention(cpu: usize, stop: u64) -> Result<()> {
    affinity(Some(cpu))?;
    let mut x = 1u64;
    while mono() < stop {
        for _ in 0..8192 {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
        }
        std::hint::black_box(x);
    }
    Ok(())
}

fn count(mode: &str) -> Result<u64> {
    match mode {
        "idle" | "contention" => Ok(1500),
        "overload" | "blocked-phone" => Ok(150),
        "demo" => Ok(100),
        "live" | "live-faults" => Ok(400),
        _ => Err("invalid timing scenario".into()),
    }
}

fn read_exact<const N: usize>(socket: &UnixDatagram) -> Result<[u8; N]> {
    let mut scratch = [0; CONTACT + 1];
    check(
        socket.recv(&mut scratch)? == N,
        "invalid trusted control message",
    )?;
    Ok(scratch[..N].try_into()?)
}

fn send(socket: &UnixDatagram, id: u32, wire: &[u8]) -> io::Result<()> {
    for (packet, len) in
        fragments(id, wire).ok_or_else(|| io::Error::other("invalid link input"))?
    {
        if socket.send(&packet[..len])? != len {
            return Err(io::Error::other("short datagram write"));
        }
    }
    Ok(())
}

fn radio_frame(
    port: &mut protocol::radio::RadioPort,
    bytes: &[u8],
    tick: u64,
) -> Option<protocol::radio::Frame> {
    if bytes.len() > protocol::radio::FRAME_BYTES {
        return None;
    }
    let mut command = [0; 40];
    command[0] = 1;
    command[1] = bytes.len() as u8;
    command[2..2 + bytes.len()].copy_from_slice(bytes);
    port.receive(&command[..2 + bytes.len()], tick).ok()?;
    port.pop(tick)
}

fn recv_start(socket: &UnixDatagram) -> Result<([u8; RECORD], usize)> {
    let stop = mono() + 3_000_000_000;
    let mut parts = Reassembly::default();
    let mut radio = protocol::radio::RadioPort::default();
    let mut scratch = [0; DATAGRAM + 1];
    while mono() < stop {
        match socket.recv(&mut scratch) {
            Ok(len) => {
                if let Some(frame) = radio_frame(&mut radio, &scratch[..len], mono() / PERIOD_NS)
                    && let Ok(Some(record)) = parts.push(&frame.bytes[..usize::from(frame.len)], 0)
                {
                    return Ok(record);
                }
            }
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                std::thread::sleep(Duration::from_millis(1));
            }
            Err(error) => return Err(error.into()),
        }
    }
    Err("handshake/control timed out (sandbox or transport failed closed)".into())
}

// The Linux clock and supervisor control socket model trusted device-local
// peripherals. They are never supplied by either hostile phone process.
struct LocalClock;
impl protocol::invitation::TrustedClock for LocalClock {
    fn seconds(&self) -> u64 {
        now(libc::CLOCK_REALTIME) / 1_000_000_000
    }
}
fn device_status(mode: &str, actor: &str, message: &str) {
    if mode.starts_with("live") {
        Event {
            test: mode,
            tick: 0,
            action: "device",
            from: actor,
            to: "",
            expected: "trusted endpoint and separate untrusted transport",
            observed: message,
            status: "info",
        }
        .emit_live();
    }
}

fn connect(data: &UnixDatagram, control: &UnixDatagram, alice: bool, mode: &str) -> Result<Device> {
    use protocol::{
        contacts::{ContactBook, StorageRoot},
        enrollment::EnrolledContact,
        invitation::{Admission, Invitation, Kind, call_context},
    };
    let actor = if alice { "Alice" } else { "Bob" };
    device_status(mode, actor, "Creating local identity and boot challenge");
    let mut entropy = OsEntropy;
    let identity = Identity::new(&mut entropy)?;
    let owner: [u8; 32] = identity.contact()[..32].try_into()?;
    let challenge: [u8; 16] = entropy.seed()?[..16].try_into()?;
    control.send(&identity.contact())?;
    control.send(&challenge)?;
    let signer = read_exact::<32>(control)?;
    let peer = read_exact::<CONTACT>(control)?;
    let peer_challenge = read_exact::<16>(control)?;
    check(
        read_exact::<1>(control)? == [1],
        "local user denied consent",
    )?;
    let mut book = ContactBook::new(owner);
    book.install(
        EnrolledContact::verified_oob(peer, &signer, true)?,
        if alice { "Bob" } else { "Alice" },
    )?;
    let mut root = StorageRoot::new(&mut entropy)?;
    let snapshot = book.persist(&mut root)?;
    book = ContactBook::restore(&snapshot, &root, owner)?;
    device_status(
        mode,
        actor,
        "Pinned contact verified; sealed contact state restored",
    );
    let mut admission = Admission::default();
    let (issued, verified) = if alice {
        let (offer, _snapshot) = Invitation::issue(
            &identity,
            &mut book,
            &signer,
            peer_challenge,
            &LocalClock,
            Kind::Offer,
            None,
            &mut entropy,
            &mut root,
        )?;
        send(data, 10, offer.as_bytes())?;
        let (wire, n) = recv_start(data)?;
        let (verified, _snapshot) = Invitation::parse(&wire[..n])?.verify(
            &identity,
            &mut book,
            &signer,
            &challenge,
            &LocalClock,
            &mut admission,
            &mut root,
        )?;
        check(
            verified.kind() == Kind::Accept,
            "expected authenticated acceptance",
        )?;
        (offer, verified)
    } else {
        let (wire, n) = recv_start(data)?;
        let (verified, _snapshot) = Invitation::parse(&wire[..n])?.verify(
            &identity,
            &mut book,
            &signer,
            &challenge,
            &LocalClock,
            &mut admission,
            &mut root,
        )?;
        check(
            verified.kind() == Kind::Offer,
            "expected authenticated offer",
        )?;
        let (accept, _snapshot) = Invitation::issue(
            &identity,
            &mut book,
            &signer,
            peer_challenge,
            &LocalClock,
            Kind::Accept,
            Some(verified.call_nonce()),
            &mut entropy,
            &mut root,
        )?;
        send(data, 11, accept.as_bytes())?;
        (accept, verified)
    };
    let context = call_context(&identity, &book, &issued, &verified)?;
    device_status(
        mode,
        actor,
        "Signed invitation authenticated and bound to call",
    );
    let mut handshake = identity.handshake_with_entropy(
        &book.pin(&signer)?,
        alice,
        &mut entropy,
        Some(&context),
    )?;
    if alice {
        send(data, 0, &handshake.send()?)?;
    }
    let (wire, len) = recv_start(data)?;
    handshake.receive(&wire[..len])?;
    if !alice {
        send(data, 0, &handshake.send()?)?;
    }
    let mut session = handshake.split()?;
    device_status(
        mode,
        actor,
        "Noise handshake authenticated; local consent confirmed",
    );
    session.consent();
    for (index, command) in [Control::Confirm, Control::Ready].into_iter().enumerate() {
        send(data, index as u32 + 1, &session.control(command)?)?;
        let (wire, len) = recv_start(data)?;
        session.receive(&wire[..len], 0..0)?;
    }
    check(session.active(), "mutual confirmation failed")?;
    device_status(
        mode,
        actor,
        "Call active: confirmation complete; audio gate open",
    );
    Ok(Device::new(session)?)
}

#[derive(Default, Serialize)]
struct Distribution {
    count: usize,
    p50_ns: u64,
    p95_ns: u64,
    p99_ns: u64,
    max_ns: u64,
}

fn distribution(values: &mut [u64]) -> Distribution {
    values.sort_unstable();
    let quantile = |percent: usize| {
        let index = (values.len() * percent)
            .div_ceil(100usize)
            .saturating_sub(1);
        values.get(index).copied().unwrap_or(0)
    };
    Distribution {
        count: values.len(),
        p50_ns: quantile(50),
        p95_ns: quantile(95),
        p99_ns: quantile(99),
        max_ns: quantile(100),
    }
}

#[derive(Default, Serialize)]
struct Stats {
    scheduled_slots: u64,
    sent: u64,
    missed_slots: u64,
    missed_slot_indices: Vec<u64>,
    catch_up_bursts: u64,
    transmit_drops: u64,
    receive_drops: u64,
    reassembly_peak: usize,
    jitter_peak: usize,
    ipc_output_queue_peak_bytes: i32,
    ipc_output_buffer_bytes: i32,
    plc_slots: u64,
    decoded_slots: u64,
    filler_slots: u64,
    filler_sent_slots: u64,
    cpu_ns: u64,
    codec_ns: u64,
    crypto_ns: u64,
    peak_rss_kib: i64,
    absolute_send_error: Distribution,
    digital_playout_latency: Distribution,
}

struct Measurements {
    stats: Stats,
    send_error: Vec<u64>,
    playout_latency: Vec<u64>,
    pcm: Vec<i16>,
    traces: Vec<Event<'static>>,
    live: bool,
}

impl Measurements {
    fn trace(&mut self, event: Event<'static>) {
        if self.live {
            event.emit_live();
        }
        if self.traces.len() < TRACE_LIMIT {
            self.traces.push(event);
        }
    }
}

fn output_queue(socket: &UnixDatagram) -> i32 {
    let mut bytes = 0i32;
    // SAFETY: TIOCOUTQ writes one int.
    if unsafe { libc::ioctl(socket.as_raw_fd(), libc::TIOCOUTQ, &mut bytes) } < 0 {
        -1
    } else {
        bytes
    }
}

fn buffer_bytes(socket: &UnixDatagram) -> io::Result<i32> {
    let mut bytes = 0i32;
    let mut size = size_of_val(&bytes) as libc::socklen_t;
    // SAFETY: Both output pointers refer to objects of the specified sizes.
    if unsafe {
        libc::getsockopt(
            socket.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_SNDBUF,
            (&raw mut bytes).cast(),
            &mut size,
        )
    } == 0
    {
        Ok(bytes)
    } else {
        Err(io::Error::last_os_error())
    }
}

fn measure(
    data: &UnixDatagram,
    mut device: Device,
    alice: bool,
    mode: &'static str,
    start: u64,
    count: u64,
) -> Result<Measurements> {
    let mut parts = Reassembly::default();
    let mut radio = protocol::radio::RadioPort::default();
    let mut schedule = Slots::default();
    let mut m = Measurements {
        stats: Stats {
            scheduled_slots: count,
            ipc_output_buffer_bytes: buffer_bytes(data)?,
            ..Stats::default()
        },
        send_error: Vec::with_capacity(count as usize),
        playout_latency: Vec::with_capacity(count as usize),
        pcm: vec![0; count as usize * codec::SAMPLES],
        traces: Vec::with_capacity(TRACE_LIMIT),
        live: mode.starts_with("live"),
    };
    let (local, phone, remote) = if alice {
        ("Alice", "Phone A", "Bob")
    } else {
        ("Bob", "Phone B", "Alice")
    };
    let mut scratch = [0; DATAGRAM + 1];
    let mut last_attempt = None;
    let mut last_success = None;
    let mut delivered = vec![false; count as usize];
    let cpu_begin = now(libc::CLOCK_PROCESS_CPUTIME_ID);
    let prepare = |device: &mut Device, stats: &mut Stats, slot| {
        let began = mono();
        let pcm = codec::synthetic(alice, slot);
        let encoded = device.encode(Some(&pcm));
        stats.codec_ns += mono() - began;
        (slot, encoded)
    };
    let mut prepared = Some(prepare(&mut device, &mut m.stats, 0));
    let mut tick = 0;
    while tick < count + JITTER as u64 {
        sleep_until(start + tick * PERIOD_NS)?;
        if mode == "overload" && tick < count && tick % 9 == 3 {
            sleep_until(start + tick * PERIOD_NS + 55_000_000)?;
        }
        let elapsed = mono().saturating_sub(start);
        if let Some(slot) = schedule.select(elapsed, count) {
            let media = prepared
                .take()
                .filter(|(encoded_slot, _)| *encoded_slot == slot)
                .map_or(Media::Filler, |(_, media)| media);
            let encrypted_at = mono();
            let wire = device.seal(slot, media)?;
            let transmit_at = mono();
            m.stats.crypto_ns += transmit_at - encrypted_at;
            if transmit_at < start + (slot + 1) * PERIOD_NS
                && last_attempt.is_none_or(|last| transmit_at - last >= MIN_SEND_GAP_NS)
            {
                schedule.sent(transmit_at - start);
                last_attempt = Some(transmit_at);
                let result = send(data, slot as u32 + 3, &wire);
                let queued = output_queue(data);
                m.stats.ipc_output_queue_peak_bytes =
                    m.stats.ipc_output_queue_peak_bytes.max(queued);
                if result.is_ok() {
                    if last_success.is_some_and(|last| transmit_at - last < MIN_SEND_GAP_NS) {
                        m.stats.catch_up_bursts += 1;
                    }
                    last_success = Some(transmit_at);
                    delivered[slot as usize] = true;
                    m.stats.sent += 1;
                    m.stats.filler_sent_slots += u64::from(media == Media::Filler);
                    m.send_error
                        .push(transmit_at.abs_diff(start + slot * PERIOD_NS));
                } else {
                    m.stats.transmit_drops += 1;
                }
                if mode.starts_with("live") || slot < TRACE_SLOTS {
                    let (action, observed) = if result.is_ok() {
                        ("send", "128-byte ciphertext submitted")
                    } else {
                        ("drop", "bounded IPC would block")
                    };
                    m.trace(Event {
                        test: mode,
                        tick: slot,
                        action,
                        from: local,
                        to: phone,
                        expected: "one record or a counted miss",
                        observed,
                        status: "info",
                    });
                }
            }
        }
        let current = mono().saturating_sub(start) / PERIOD_NS;
        let play = current
            .checked_sub(JITTER as u64)
            .filter(|&slot| slot < count);
        if let Some(slot) = play {
            device.jitter.skip_to(slot);
        }
        for _ in 0..RECEIVE_BUDGET {
            let len = match data.recv(&mut scratch) {
                Ok(len) => len,
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                Err(error) => return Err(error.into()),
            };
            let Some(frame) = radio_frame(&mut radio, &scratch[..len], current) else {
                m.stats.receive_drops += 1;
                continue;
            };
            match parts.push(&frame.bytes[..usize::from(frame.len)], current) {
                Ok(Some((wire, len))) => {
                    let at = mono();
                    let outcome = device.ingest(&wire[..len], current);
                    let accepted = outcome.is_ok();
                    m.stats.crypto_ns += mono() - at;
                    if !accepted {
                        m.stats.receive_drops += 1;
                    }
                    if mode.starts_with("live") || current < TRACE_SLOTS {
                        m.trace(Event {
                            test: mode,
                            tick: current,
                            action: if accepted { "receive" } else { "reject" },
                            from: phone,
                            to: local,
                            expected: "authenticate before playout",
                            observed: if accepted {
                                "authenticated record buffered"
                            } else if matches!(outcome, Err(protocol::Error::Auth)) {
                                "authentication failed; record discarded"
                            } else {
                                "record rejected"
                            },
                            status: "info",
                        });
                    }
                }
                Ok(None) => {}
                Err(_) => m.stats.receive_drops += 1,
            }
        }
        if let Some(slot) = play {
            let at = mono();
            let (pcm, outcome) = device.playout();
            let emitted = mono();
            m.stats.codec_ns += emitted - at;
            match outcome {
                Playout::Audio => {
                    m.stats.decoded_slots += 1;
                    m.playout_latency.push(emitted - (start + slot * PERIOD_NS));
                }
                Playout::Filler => m.stats.filler_slots += 1,
                _ => m.stats.plc_slots += 1,
            }
            let offset = slot as usize * codec::SAMPLES;
            m.pcm[offset..offset + codec::SAMPLES].copy_from_slice(&pcm);
            if mode.starts_with("live") || current < TRACE_SLOTS {
                m.trace(Event {
                    test: mode,
                    tick: current,
                    action: "playout",
                    from: remote,
                    to: local,
                    expected: "bounded jitter and one frame of audio or concealment",
                    observed: match outcome {
                        Playout::Audio => "decoded",
                        Playout::Filler => "muted",
                        _ => "concealed",
                    },
                    status: "info",
                });
            }
        }
        tick = current + 1;
        // Finish encoding in the preceding slot. If work overruns, the next
        // deadline can still send authenticated filler without waiting for Opus.
        if tick < count && mono() + 5_000_000 < start + tick * PERIOD_NS {
            prepared = Some(prepare(&mut device, &mut m.stats, tick));
        }
    }
    m.stats.cpu_ns = now(libc::CLOCK_PROCESS_CPUTIME_ID) - cpu_begin;
    m.stats.missed_slot_indices = delivered
        .iter()
        .enumerate()
        .filter_map(|(index, &sent)| (!sent).then_some(index as u64))
        .collect();
    m.stats.missed_slots = m.stats.missed_slot_indices.len() as u64;
    m.stats.jitter_peak = device.jitter.peak;
    m.stats.reassembly_peak = parts.peak;
    // SAFETY: getrusage initializes the caller's ABI structure on success.
    let mut usage = std::mem::MaybeUninit::<libc::rusage>::uninit();
    if unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) } != 0 {
        return Err(io::Error::last_os_error().into());
    }
    // SAFETY: getrusage reported success above.
    m.stats.peak_rss_kib = unsafe { usage.assume_init() }.ru_maxrss;
    m.stats.absolute_send_error = distribution(&mut m.send_error);
    m.stats.digital_playout_latency = distribution(&mut m.playout_latency);
    Ok(m)
}

pub fn write_wav(path: &Path, pcm: &[i16]) -> Result<()> {
    let mut file = BufWriter::new(File::create(path)?);
    let bytes = u32::try_from(pcm.len() * 2)?;
    let rate = codec::RATE as u32;
    file.write_all(b"RIFF")?;
    file.write_all(&(36 + bytes).to_le_bytes())?;
    file.write_all(b"WAVEfmt ")?;
    file.write_all(&[16, 0, 0, 0, 1, 0, 1, 0])?;
    file.write_all(&rate.to_le_bytes())?;
    file.write_all(&(rate * 2).to_le_bytes())?;
    file.write_all(&[2, 0, 16, 0])?;
    file.write_all(b"data")?;
    file.write_all(&bytes.to_le_bytes())?;
    for sample in pcm {
        file.write_all(&sample.to_le_bytes())?;
    }
    file.flush()?;
    Ok(())
}

pub fn endpoint(out: &Path, alice: bool, mode: &str) -> Result<()> {
    let mode = [
        "idle",
        "contention",
        "overload",
        "blocked-phone",
        "demo",
        "live",
        "live-faults",
    ]
    .into_iter()
    .find(|candidate| *candidate == mode)
    .ok_or("unknown wall-clock mode")?;
    let data = sandbox::inherited(0);
    let control = sandbox::inherited(1);
    control.set_read_timeout(Some(Duration::from_secs(8)))?;
    let device = connect(&data, &control, alice, mode)?;
    control.send(b"active")?;
    let parameters = read_exact::<16>(&control)?;
    let start = u64::from_le_bytes(parameters[..8].try_into()?);
    let cpu = usize::try_from(u64::from_le_bytes(parameters[8..].try_into()?))?;
    affinity(Some(cpu))?;
    let result = measure(&data, device, alice, mode, start, count(mode)?)?;
    let who = if alice { "alice" } else { "bob" };
    write_wav(&out.join(format!("{who}-received.wav")), &result.pcm)?;
    fs::write(
        out.join(format!("{who}.json")),
        serde_json::to_vec_pretty(&result.stats)?,
    )?;
    let traces = result
        .traces
        .iter()
        .map(serde_json::to_string)
        .collect::<std::result::Result<Vec<_>, _>>()?;
    fs::write(out.join(format!("{who}.ndjson")), traces.join("\n"))?;
    device_status(
        mode,
        if alice { "Alice" } else { "Bob" },
        "Call complete; recovered synthetic audio saved",
    );
    control.send(b"done")?;
    Ok(())
}

fn power(pcm: &[i16], frequency: f64) -> f64 {
    let omega = std::f64::consts::TAU * frequency / codec::RATE as f64;
    let mut re = 0.0;
    let mut im = 0.0;
    for (index, sample) in pcm.iter().enumerate() {
        let (sin, cos) = (omega * index as f64).sin_cos();
        re += f64::from(*sample) * cos;
        im += f64::from(*sample) * sin;
    }
    (re * re + im * im) / (pcm.len() as f64).powi(2)
}

pub fn wav_direction(path: &Path, expected: f64, wrong: f64) -> Result<(f64, f64)> {
    let wav = fs::read(path)?;
    check(
        wav.get(..4) == Some(b"RIFF") && wav.get(8..12) == Some(b"WAVE"),
        "invalid WAV",
    )?;
    let data = wav.get(44..).ok_or("short WAV")?;
    let pcm: Vec<_> = data
        .as_chunks::<2>()
        .0
        .iter()
        .take(codec::RATE * 3)
        .map(|&bytes| i16::from_le_bytes(bytes))
        .collect();
    let pcm = pcm
        .get(codec::SAMPLES * JITTER..)
        .ok_or("no received audio")?;
    Ok((power(pcm, expected), power(pcm, wrong)))
}

pub fn run(out: &Path, mode: &str) -> Result<()> {
    let slots = count(mode)?;
    fs::create_dir_all(out)?;
    let executable = std::env::current_exe()?;
    let available = affinity(None)?;
    let last = *available.last().ok_or("empty CPU affinity")?;
    let siblings = |cpu| {
        fs::read_to_string(format!(
            "/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
        ))
        .ok()
    };
    let first_core = siblings(last);
    let other = available
        .iter()
        .copied()
        .rev()
        .find(|&cpu| cpu != last && (first_core.is_none() || siblings(cpu) != first_core))
        .or_else(|| available.iter().copied().rev().find(|&cpu| cpu != last))
        .unwrap_or(last);
    let cpus = [other, last];
    let mut chain = (0..4)
        .map(|_| sandbox::bounded_pair().map(|(a, b)| [Some(a), Some(b)]))
        .collect::<io::Result<Vec<_>>>()?;
    let mut children = Children::default();
    let mut controls = Vec::new();
    for (role, (edge, end)) in [("alice", (0, 0)), ("bob", (3, 1))] {
        let (parent, child) = UnixDatagram::pair()?;
        parent.set_read_timeout(Some(Duration::from_secs(8)))?;
        children.add(
            Command::new(&executable)
                .arg("endpoint")
                .arg(out)
                .args([role, mode])
                .stdin(sandbox::stdio(chain[edge][end].take().unwrap()))
                .stdout(sandbox::stdio(child))
                .spawn()?,
        );
        controls.push(parent);
    }
    let endpoint_pid = children.0[0].id().to_string();
    for index in 0..3 {
        let variant = if mode == "blocked-phone" && index == 0 {
            "blocked"
        } else if mode == "live-faults" && index == 0 {
            "faults"
        } else {
            "pass"
        };
        children.add(
            Command::new(&executable)
                .args(["forward", variant, &endpoint_pid])
                .env_clear()
                .stdin(sandbox::stdio(chain[index][1].take().unwrap()))
                .stdout(sandbox::stdio(chain[index + 1][0].take().unwrap()))
                .stderr(Stdio::null())
                .spawn()?,
        );
    }
    for peer in ["Phone A", "Relay", "Phone B"] {
        device_status(
            mode,
            peer,
            if mode == "live-faults" && peer == "Phone A" {
                "Hostile process running; injected media corruption and loss enabled"
            } else {
                "Untrusted forwarding process running"
            },
        );
    }
    let a = read_exact::<CONTACT>(&controls[0])?;
    let b = read_exact::<CONTACT>(&controls[1])?;
    let ac = read_exact::<16>(&controls[0])?;
    let bc = read_exact::<16>(&controls[1])?;
    controls[0].send(&b[..32])?;
    controls[1].send(&a[..32])?;
    controls[0].send(&b)?;
    controls[1].send(&a)?;
    controls[0].send(&bc)?;
    controls[1].send(&ac)?;
    for control in &controls {
        control.send(&[1])?;
    }
    for control in &controls {
        check(
            &read_exact::<6>(control)? == b"active",
            "endpoint did not consent",
        )?;
    }
    let start = mono() + 300_000_000;
    let stop = start + (slots + JITTER as u64) * PERIOD_NS;
    if mode == "contention" {
        for cpu in cpus {
            children.add(
                Command::new(&executable)
                    .args(["contention", &cpu.to_string(), &stop.to_string()])
                    .stdin(Stdio::null())
                    .spawn()?,
            );
        }
    }
    for (index, control) in controls.iter().enumerate() {
        control.set_read_timeout(Some(Duration::from_nanos(stop - mono() + 6_000_000_000)))?;
        let mut parameters = [0; 16];
        parameters[..8].copy_from_slice(&start.to_le_bytes());
        parameters[8..].copy_from_slice(&(cpus[index] as u64).to_le_bytes());
        control.send(&parameters)?;
    }
    for control in &controls {
        check(
            &read_exact::<4>(control)? == b"done",
            "endpoint failed during timing",
        )?;
    }
    for child in children.0.iter_mut().take(2) {
        check(child.wait()?.success(), "endpoint exited unsuccessfully")?;
    }
    for child in children.0.iter_mut().skip(2).take(3) {
        check(child.try_wait()?.is_none(), "hostile forwarder exited")?;
    }
    for child in children.0.iter_mut().skip(5) {
        check(child.wait()?.success(), "CPU load generator failed")?;
    }
    let read = |name| -> Result<serde_json::Value> {
        Ok(serde_json::from_slice(&fs::read(out.join(name))?)?)
    };
    let a = read("alice.json")?;
    let b = read("bob.json")?;
    let mut passed = true;
    let mut reasons = Vec::new();
    for (name, stats) in [(PEERS[0], &a), (PEERS[4], &b)] {
        let integer = |field: &str| stats[field].as_u64().unwrap_or(u64::MAX);
        let ipc_peak = stats["ipc_output_queue_peak_bytes"].as_i64().unwrap_or(-1);
        let ipc_buffer = stats["ipc_output_buffer_bytes"].as_i64().unwrap_or(-1);
        let bounded = ipc_peak >= 0
            && ipc_peak <= ipc_buffer + 4096
            && integer("sent") + integer("missed_slots") == slots
            && integer("jitter_peak") <= device_core::QUEUE as u64
            && integer("reassembly_peak") <= link::ASSEMBLIES as u64
            && integer("catch_up_bursts") == 0;
        if !bounded {
            reasons.push(format!("{name}: queue bound or burst gate"));
        }
        passed &= bounded;
        if matches!(mode, "idle" | "contention") {
            let p99 = stats["absolute_send_error"]["p99_ns"]
                .as_u64()
                .unwrap_or(u64::MAX);
            let misses = integer("missed_slots");
            if p99 > 5_000_000 || misses.saturating_mul(1000) > slots {
                reasons.push(format!("{name}: p99 {p99} ns and {misses}/{slots} misses"));
                passed = false;
            }
        }
        if mode == "overload" && integer("missed_slots") == 0 {
            reasons.push(format!("{name}: injected overload did not cause misses"));
            passed = false;
        }
    }
    if mode == "blocked-phone" && a["transmit_drops"].as_u64() == Some(0) {
        reasons.push("Phone A blockage did not cause backpressure".into());
        passed = false;
    }
    if mode == "live-faults"
        && (b["receive_drops"].as_u64().unwrap_or(0) == 0
            || b["plc_slots"].as_u64().unwrap_or(0) == 0)
    {
        reasons.push("injected live faults did not produce rejection and concealment".into());
        passed = false;
    }
    let mut tones = serde_json::Value::Null;
    if matches!(
        mode,
        "idle" | "contention" | "demo" | "live" | "live-faults"
    ) {
        let (a_right, a_wrong) = wav_direction(&out.join("alice-received.wav"), 700.0, 400.0)?;
        let (b_right, b_wrong) = wav_direction(&out.join("bob-received.wav"), 400.0, 700.0)?;
        tones = serde_json::json!({"alice_700hz": a_right, "alice_400hz": a_wrong, "bob_400hz": b_right, "bob_700hz": b_wrong});
        if !(a_right > 100_000.0
            && a_right > a_wrong * 20.0
            && b_right > 100_000.0
            && b_right > b_wrong * 20.0)
        {
            reasons.push("WAV frequency or direction check failed".into());
            passed = false;
        }
    }
    let report = serde_json::json!({
        "mode": mode, "passed": passed, "reasons": reasons, "period_ns": PERIOD_NS,
        "duration_seconds": slots as f64 / 50.0, "allowed_cpus": available, "endpoint_cpus": cpus,
        "pids": children.0.iter().map(Child::id).collect::<Vec<_>>(),
        "load": match mode {
            "contention" => "two pinned xorshift CPU workers, one on each endpoint CPU",
            "overload" => "55 ms absolute stall after every ninth slot on both endpoints",
            "blocked-phone" => "Phone A stops reading Alice after control exchange",
            _ => "no lab-generated load",
        },
        "alice_to_bob_tx": a, "bob_to_alice_tx": b,
        "digital_playout_latency_by_direction": {
            "alice_to_bob": b["digital_playout_latency"], "bob_to_alice": a["digital_playout_latency"],
        },
        "playout_metrics_are_local_rx": true, "wav_tone_power": tones,
    });
    fs::write(
        out.join("metrics.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    let mut traces = Vec::new();
    for who in ["alice", "bob"] {
        for line in fs::read_to_string(out.join(format!("{who}.ndjson")))?.lines() {
            let event: serde_json::Value = serde_json::from_str(line)?;
            traces.push((event["tick"].as_u64().unwrap_or(0), line.to_owned()));
        }
    }
    traces.sort_by_key(|(tick, _)| *tick);
    if !mode.starts_with("live") {
        for (_, line) in traces {
            println!("{line}");
        }
    }
    Event {
        test: mode,
        tick: slots,
        action: "verdict",
        from: "",
        to: "",
        expected: "scenario timing, queue, burst and applicable WAV gates",
        observed: if passed {
            "gates met"
        } else {
            "see timing metrics and diagnostic log"
        },
        status: if passed { "pass" } else { "fail" },
    }
    .emit();
    check(passed, &reasons.join("; "))
}
