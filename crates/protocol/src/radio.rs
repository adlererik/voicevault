//! Controller-side capability boundary. A radio can submit bounded link bytes;
//! it has no opcode for consent, contacts, memory, flash, debug, clock or entropy.
use crate::{PolicyError as E, PolicyResult as R};
pub const FRAME_BYTES: usize = 38;
pub const QUEUE: usize = 8;
pub const PER_TICK: usize = 32;
#[derive(Clone, Copy)]
pub struct Frame {
    pub bytes: [u8; FRAME_BYTES],
    pub len: u8,
    born: u64,
}
pub struct RadioPort {
    frames: [Option<Frame>; QUEUE],
    head: usize,
    tail: usize,
    count: usize,
    tick: u64,
    work: usize,
    offline_update: bool,
    pub dropped: u64,
    pub peak: usize,
}
impl Default for RadioPort {
    fn default() -> Self {
        Self {
            frames: [None; QUEUE],
            head: 0,
            tail: 0,
            count: 0,
            tick: 0,
            work: 0,
            offline_update: false,
            dropped: 0,
            peak: 0,
        }
    }
}
impl RadioPort {
    /// Local control only; there is deliberately no corresponding wire command.
    pub fn local_update_mode(&mut self, enabled: bool) {
        self.offline_update = enabled;
        self.clear();
    }
    fn clear(&mut self) {
        self.frames = [None; QUEUE];
        self.head = 0;
        self.tail = 0;
        self.count = 0;
    }
    pub fn controller_reset(&mut self) {
        self.clear();
    }
    pub fn depth(&self) -> usize {
        self.count
    }
    pub fn receive(&mut self, wire: &[u8], trusted_tick: u64) -> R<()> {
        if trusted_tick < self.tick {
            return Err(E::Clock);
        }
        if trusted_tick != self.tick {
            self.tick = trusted_tick;
            self.work = 0;
        }
        if self.work >= PER_TICK {
            self.dropped = self.dropped.saturating_add(1);
            return Err(E::Busy);
        }
        self.work += 1;
        if self.offline_update {
            return Err(E::State);
        }
        if wire.len() < 2 || wire[0] != 1 {
            return Err(E::Unsupported);
        }
        let len = usize::from(wire[1]);
        if !(6..=FRAME_BYTES).contains(&len) || wire.len() != len + 2 {
            return Err(E::Invalid);
        }
        if self.count == QUEUE {
            self.dropped = self.dropped.saturating_add(1);
            return Err(E::Full);
        }
        let mut frame = Frame {
            bytes: [0; FRAME_BYTES],
            len: len as u8,
            born: trusted_tick,
        };
        frame.bytes[..len].copy_from_slice(&wire[2..]);
        self.frames[self.tail] = Some(frame);
        self.tail = (self.tail + 1) % QUEUE;
        self.count += 1;
        self.peak = self.peak.max(self.count);
        Ok(())
    }
    pub fn pop(&mut self, trusted_tick: u64) -> Option<Frame> {
        if trusted_tick < self.tick {
            return None;
        }
        while self.count > 0 {
            let frame = self.frames[self.head].take();
            self.head = (self.head + 1) % QUEUE;
            self.count -= 1;
            if let Some(frame) = frame
                && trusted_tick.saturating_sub(frame.born) < 3
            {
                return Some(frame);
            }
        }
        None
    }
}
