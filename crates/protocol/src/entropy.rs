//! On-device source health/failure model. Sanity checks do not estimate entropy.
//! Hardware sources must independently be evaluated before any device claim.
use crate::{Entropy, Error, PolicyError as E, PolicyResult as R};
use blake2::{Blake2s256, Digest};
use zeroize::Zeroizing;

pub trait HardwareSources {
    /// 0 = MCU, 1 = secure element A, 2 = secure element B. No phone slot exists.
    fn read_source(&mut self, source: usize, out: &mut [u8; 32]) -> R<()>;
    fn next_protected_generation(&mut self) -> R<u64>;
}
pub struct EntropyPool<S> {
    sources: S,
    previous: [Option<[u8; 32]>; 3],
    last_generation: u64,
}
impl<S: HardwareSources> EntropyPool<S> {
    pub fn new(sources: S) -> Self {
        Self {
            sources,
            previous: [None; 3],
            last_generation: 0,
        }
    }
    pub fn source_mut(&mut self) -> &mut S {
        &mut self.sources
    }
    pub fn conditioned_seed(&mut self) -> R<[u8; 32]> {
        let generation = self.sources.next_protected_generation()?;
        if generation == 0 || generation == u64::MAX || generation <= self.last_generation {
            return Err(E::Entropy);
        }
        self.last_generation = generation;
        let mut h = Blake2s256::new();
        h.update(b"quietlink onboard entropy v1");
        h.update(generation.to_le_bytes());
        let mut healthy = 0u8;
        for i in 0..3 {
            let mut block = Zeroizing::new([0; 32]);
            if self.sources.read_source(i, &mut block).is_err() {
                continue;
            }
            let uniform = block.iter().all(|&b| b == block[0]);
            let repeated = self.previous[i].is_some_and(|prev| prev == *block);
            self.previous[i] = Some(*block);
            if uniform || repeated {
                continue;
            }
            healthy += 1;
            h.update([i as u8]);
            h.update(block.as_ref());
        }
        // A failed/stuck source cannot silently select the phone as a fallback.
        if healthy < 2 {
            return Err(E::Entropy);
        }
        Ok(h.finalize().into())
    }
}
impl<S: HardwareSources> Entropy for EntropyPool<S> {
    fn seed(&mut self) -> Result<[u8; 32], Error> {
        self.conditioned_seed().map_err(|_| Error::Entropy)
    }
}
