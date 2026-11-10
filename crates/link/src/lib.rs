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
    if !matches!(wire.len(), 48 | MAX_RECORD) {
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
        if !matches!(len, 48 | MAX_RECORD) || index >= chunks {
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
