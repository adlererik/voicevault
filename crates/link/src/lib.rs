#![no_std]
#![forbid(unsafe_code)]

//! Fixed-size fragments for the simulated BLE-like link.
pub const CHUNK: usize = 32;
pub const MAX_RECORD: usize = 128;
pub const HEADER: usize = 6;
pub const DATAGRAM: usize = HEADER + CHUNK;
pub const ASSEMBLIES: usize = 8;
const TTL: u64 = 3;

pub fn fragments(
    id: u32,
    wire: &[u8],
) -> Option<impl Iterator<Item = ([u8; DATAGRAM], usize)> + '_> {
    if wire.len() != MAX_RECORD {
        return None;
    }
    let len = wire.len() as u8;
    Some(wire.chunks(CHUNK).enumerate().map(move |(index, payload)| {
        let mut frame = [0; DATAGRAM];
        frame[..4].copy_from_slice(&id.to_le_bytes());
        frame[4] = len;
        frame[5] = index as u8;
        frame[HEADER..HEADER + payload.len()].copy_from_slice(payload);
        (frame, HEADER + payload.len())
    }))
}

#[derive(Clone, Copy)]
struct Partial {
    id: u32,
    born: u64,
    len: usize,
    mask: u8,
    wire: [u8; MAX_RECORD],
}

#[derive(Default)]
pub struct Reassembly {
    pending: [Option<Partial>; ASSEMBLIES],
    pub peak: usize,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Drop {
    Shape,
    Duplicate,
    Full,
}

pub type Assembled = ([u8; MAX_RECORD], usize);

impl Reassembly {
    pub fn push(&mut self, frame: &[u8], tick: u64) -> Result<Option<Assembled>, Drop> {
        let header = frame.get(..HEADER).ok_or(Drop::Shape)?;
        let id = u32::from_le_bytes(header[..4].try_into().map_err(|_| Drop::Shape)?);
        let len = usize::from(header[4]);
        let index = usize::from(header[5]);
        let chunks = len.div_ceil(CHUNK);
        if len != MAX_RECORD || index >= chunks {
            return Err(Drop::Shape);
        }
        let start = index * CHUNK;
        let end = len.min(start + CHUNK);
        if frame.len() != HEADER + end - start {
            return Err(Drop::Shape);
        }
        for entry in &mut self.pending {
            if entry.is_some_and(|partial| tick.saturating_sub(partial.born) >= TTL) {
                *entry = None;
            }
        }
        let position = self
            .pending
            .iter()
            .position(|entry| entry.is_some_and(|part| part.id == id))
            .or_else(|| self.pending.iter().position(Option::is_none))
            .ok_or(Drop::Full)?;
        let partial = self.pending[position].get_or_insert(Partial {
            id,
            born: tick,
            len,
            mask: 0,
            wire: [0; MAX_RECORD],
        });
        if partial.len != len {
            return Err(Drop::Shape);
        }
        let bit = 1 << index;
        if partial.mask & bit != 0 {
            return Err(Drop::Duplicate);
        }
        partial.mask |= bit;
        partial.wire[start..end].copy_from_slice(&frame[HEADER..]);
        let complete = (partial.mask == (1 << chunks) - 1).then_some((partial.wire, len));
        self.peak = self.peak.max(self.pending.iter().flatten().count());
        if complete.is_some() {
            self.pending[position] = None;
        }
        Ok(complete)
    }
}

/// A single, separately budgeted hybrid startup flight. Media keeps its
/// original 128-byte buffer and never accepts this framing.
pub const STARTUP_MAX: usize = 1248;
pub const STARTUP_FIRST: usize = 1248;
pub const STARTUP_SECOND: usize = 1152;
pub const STARTUP_MAGIC: u8 = 0xd2;
const STARTUP_TTL_MS: u64 = 3000;
pub fn startup_fragments(
    flight: u8,
    wire: &[u8],
) -> Option<impl Iterator<Item = ([u8; DATAGRAM], usize)> + '_> {
    let expected = match flight {
        0 => STARTUP_FIRST,
        1 => STARTUP_SECOND,
        _ => return None,
    };
    if wire.len() != expected {
        return None;
    }
    Some(wire.chunks(CHUNK).enumerate().map(move |(index, payload)| {
        let mut frame = [0; DATAGRAM];
        frame[0] = STARTUP_MAGIC;
        frame[1] = flight;
        frame[2..4].copy_from_slice(&(expected as u16).to_le_bytes());
        frame[4] = index as u8;
        frame[5] = expected.div_ceil(CHUNK) as u8;
        frame[HEADER..HEADER + payload.len()].copy_from_slice(payload);
        (frame, HEADER + payload.len())
    }))
}

pub struct Startup {
    flight: u8,
    len: usize,
    born: Option<u64>,
    mask: u64,
    wire: [u8; STARTUP_MAX],
    work: u8,
    failed: bool,
    finished: bool,
}
impl Startup {
    pub fn new(flight: u8) -> Option<Self> {
        let len = match flight {
            0 => STARTUP_FIRST,
            1 => STARTUP_SECOND,
            _ => return None,
        };
        Some(Self {
            flight,
            len,
            born: None,
            mask: 0,
            wire: [0; STARTUP_MAX],
            work: 0,
            failed: false,
            finished: false,
        })
    }
    /// Fixed storage, at most 96 datagrams and one absolute lifetime. No
    /// attacker-controlled IDs, allocation growth, or sliding timeout.
    pub fn push(&mut self, frame: &[u8], now_ms: u64) -> Result<Option<&[u8]>, Drop> {
        if self.failed || self.finished {
            return Err(Drop::Full);
        }
        self.work = self.work.saturating_add(1);
        let born = *self.born.get_or_insert(now_ms);
        if self.work > 96 || now_ms < born || now_ms - born >= STARTUP_TTL_MS {
            self.failed = true;
            return Err(Drop::Full);
        }
        let h = frame.get(..HEADER).ok_or(Drop::Shape)?;
        let index = usize::from(h[4]);
        let chunks = self.len.div_ceil(CHUNK);
        if h[0] != STARTUP_MAGIC
            || h[1] != self.flight
            || usize::from(u16::from_le_bytes([h[2], h[3]])) != self.len
            || usize::from(h[5]) != chunks
            || index >= chunks
        {
            return Err(Drop::Shape);
        }
        let start = index * CHUNK;
        let end = self.len.min(start + CHUNK);
        if frame.len() != HEADER + end - start {
            return Err(Drop::Shape);
        }
        let bit = 1u64 << index;
        if self.mask & bit != 0 {
            return Err(Drop::Duplicate);
        }
        self.wire[start..end].copy_from_slice(&frame[HEADER..]);
        self.mask |= bit;
        if self.mask == (1u64 << chunks) - 1 {
            self.finished = true;
            Ok(Some(&self.wire[..self.len]))
        } else {
            Ok(None)
        }
    }
}

#[cfg(test)]
mod startup_tests {
    use super::*;
    #[test]
    fn hybrid_flights_reassemble_in_reverse_order_without_changing_media_bounds() {
        for flight in 0..2 {
            let wire = [42; STARTUP_MAX];
            let len = if flight == 0 {
                STARTUP_FIRST
            } else {
                STARTUP_SECOND
            };
            let mut receiver = Startup::new(flight).unwrap();
            let mut frames = [([0; DATAGRAM], 0); 39];
            let mut count = 0;
            for packet in startup_fragments(flight, &wire[..len]).unwrap() {
                frames[count] = packet;
                count += 1;
            }
            for i in (0..count).rev() {
                let (frame, n) = &frames[i];
                let result = receiver.push(&frame[..*n], 100).unwrap();
                if i == 0 {
                    assert_eq!(result.unwrap(), &wire[..len]);
                } else {
                    assert!(result.is_none());
                }
            }
            assert!(receiver.push(&frames[0].0[..frames[0].1], 100).is_err());
            assert!(fragments(0, &wire[..len]).is_none());
            assert!(
                Reassembly::default()
                    .push(&frames[0].0[..frames[0].1], 0)
                    .is_err()
            );
        }
    }
    #[test]
    fn startup_rejects_wrong_flight_shapes_duplicates_and_bounded_floods() {
        let wire = [8; STARTUP_MAX];
        let (packet, n) = startup_fragments(0, &wire).unwrap().next().unwrap();
        let mut a = Startup::new(0).unwrap();
        assert!(a.push(&packet[..n], 0).unwrap().is_none());
        assert_eq!(a.push(&packet[..n], 1), Err(Drop::Duplicate));
        for index in 0..HEADER {
            let mut corrupt = packet;
            corrupt[index] ^= 128;
            assert_eq!(
                Startup::new(0).unwrap().push(&corrupt[..n], 0),
                Err(Drop::Shape)
            );
        }
        assert_eq!(
            Startup::new(1).unwrap().push(&packet[..n], 0),
            Err(Drop::Shape)
        );
        for len in 0..n {
            assert_eq!(
                Startup::new(0).unwrap().push(&packet[..len], 0),
                Err(Drop::Shape)
            );
        }
        for _ in 0..100 {
            let _ = a.push(&packet[..n], 1);
        }
        assert_eq!(a.push(&packet[..n], 1), Err(Drop::Full));
        let mut a = Startup::new(0).unwrap();
        let _ = a.push(&packet[..n], 100);
        assert_eq!(a.push(&packet[..n], 3100), Err(Drop::Full));
        let mut a = Startup::new(0).unwrap();
        let _ = a.push(&packet[..n], 100);
        assert_eq!(a.push(&packet[..n], 99), Err(Drop::Full));
        assert!(startup_fragments(2, &wire).is_none());
        assert!(startup_fragments(0, &wire[..48]).is_none());
    }
}
