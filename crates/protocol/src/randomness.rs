//! Fresh device/OS entropy supplies one classical ephemeral and the KEM seeds.
//! No application PRNG and no fallback to phone-provided entropy.
use alloc::boxed::Box;
use chacha20poly1305::{ChaCha20Poly1305, KeyInit, aead::AeadInPlace};
use core::cell::Cell;
use curve25519_dalek::montgomery::MontgomeryPoint;
use snow::{
    params::{CipherChoice, DHChoice, HashChoice},
    resolvers::{CryptoResolver, DefaultResolver},
    types::{Cipher, Dh, Hash, Random},
};
use zeroize::{Zeroize, Zeroizing};

// Snow's default resolver stores these long-lived secrets in plain arrays.
// These adapters retain its wire suite while zeroizing the owned key buffers.
// Snow's internal KDF temporaries still require separate erasure review.
struct SecretDh {
    secret: Zeroizing<[u8; 32]>,
    public: [u8; 32],
}
impl Default for SecretDh {
    fn default() -> Self {
        Self {
            secret: Zeroizing::new([0; 32]),
            public: [0; 32],
        }
    }
}
impl Dh for SecretDh {
    fn name(&self) -> &'static str {
        "25519"
    }
    fn pub_len(&self) -> usize {
        32
    }
    fn priv_len(&self) -> usize {
        32
    }
    fn set(&mut self, key: &[u8]) {
        self.secret.copy_from_slice(&key[..32]);
        self.public = MontgomeryPoint::mul_base_clamped(*self.secret).to_bytes();
    }
    fn generate(&mut self, rng: &mut dyn Random) -> Result<(), snow::Error> {
        rng.try_fill_bytes(&mut self.secret[..])?;
        self.public = MontgomeryPoint::mul_base_clamped(*self.secret).to_bytes();
        Ok(())
    }
    fn pubkey(&self) -> &[u8] {
        &self.public
    }
    fn privkey(&self) -> &[u8] {
        &self.secret[..]
    }
    fn dh(&self, peer: &[u8], out: &mut [u8]) -> Result<(), snow::Error> {
        let bytes: [u8; 32] = peer
            .get(..32)
            .ok_or(snow::Error::Dh)?
            .try_into()
            .map_err(|_| snow::Error::Dh)?;
        let shared = Zeroizing::new(MontgomeryPoint(bytes).mul_clamped(*self.secret).to_bytes());
        if shared.iter().all(|&b| b == 0) || out.len() < 32 {
            return Err(snow::Error::Dh);
        }
        out[..32].copy_from_slice(shared.as_ref());
        Ok(())
    }
}
struct SecretCipher {
    key: Zeroizing<[u8; 32]>,
}
impl Default for SecretCipher {
    fn default() -> Self {
        Self {
            key: Zeroizing::new([0; 32]),
        }
    }
}
fn nonce(n: u64) -> [u8; 12] {
    let mut bytes = [0; 12];
    bytes[4..].copy_from_slice(&n.to_le_bytes());
    bytes
}
impl Cipher for SecretCipher {
    fn name(&self) -> &'static str {
        "ChaChaPoly"
    }
    fn set(&mut self, key: &[u8; 32]) {
        self.key.zeroize();
        self.key.copy_from_slice(key);
    }
    fn encrypt(&self, n: u64, aad: &[u8], plain: &[u8], out: &mut [u8]) -> usize {
        if out.len() < plain.len() + 16 {
            return 0;
        }
        out[..plain.len()].copy_from_slice(plain);
        let cipher = ChaCha20Poly1305::new(self.key.as_ref().into());
        let Ok(tag) =
            cipher.encrypt_in_place_detached((&nonce(n)).into(), aad, &mut out[..plain.len()])
        else {
            return 0;
        };
        out[plain.len()..plain.len() + 16].copy_from_slice(&tag);
        plain.len() + 16
    }
    fn decrypt(
        &self,
        n: u64,
        aad: &[u8],
        wire: &[u8],
        out: &mut [u8],
    ) -> Result<usize, snow::Error> {
        let len = wire
            .len()
            .checked_sub(16)
            .filter(|&len| len <= out.len())
            .ok_or(snow::Error::Decrypt)?;
        out[..len].copy_from_slice(&wire[..len]);
        ChaCha20Poly1305::new(self.key.as_ref().into())
            .decrypt_in_place_detached((&nonce(n)).into(), aad, &mut out[..len], wire[len..].into())
            .map_err(|_| snow::Error::Decrypt)?;
        Ok(len)
    }
}

struct OneShot {
    seed: Zeroizing<[u8; 32]>,
    used: bool,
}
impl Random for OneShot {
    fn try_fill_bytes(&mut self, dest: &mut [u8]) -> Result<(), snow::Error> {
        if self.used || dest.len() != 32 {
            return Err(snow::Error::Rng);
        }
        dest.copy_from_slice(self.seed.as_ref());
        self.seed.zeroize();
        self.used = true;
        Ok(())
    }
}
pub(crate) struct SeedResolver {
    kem_seeds: Option<(crate::kem::OnceSeed<64>, crate::kem::OnceSeed<32>)>,
    #[cfg(feature = "fixtures")]
    fault: Option<alloc::boxed::Box<crate::fixtures::KemFault>>,
    seed: Zeroizing<[u8; 32]>,
    issued: Cell<bool>,
}
impl SeedResolver {
    pub(crate) fn new(seed: [u8; 32]) -> Self {
        Self {
            kem_seeds: None,
            #[cfg(feature = "fixtures")]
            fault: None,
            seed: Zeroizing::new(seed),
            issued: Cell::new(false),
        }
    }
    pub(crate) fn hybrid(
        seed: [u8; 32],
        kem: Zeroizing<[u8; 64]>,
        enc: Zeroizing<[u8; 32]>,
    ) -> Self {
        let mut result = Self::new(seed);
        result.kem_seeds = Some((
            crate::kem::OnceSeed::new(kem),
            crate::kem::OnceSeed::new(enc),
        ));
        result
    }
    #[cfg(feature = "fixtures")]
    pub(crate) fn with_fault(
        mut self,
        fault: Option<alloc::boxed::Box<crate::fixtures::KemFault>>,
    ) -> Self {
        self.fault = fault;
        self
    }
}
impl CryptoResolver for SeedResolver {
    fn resolve_kem(&self, choice: &snow::params::KemChoice) -> Option<Box<dyn snow::types::Kem>> {
        if *choice != snow::params::KemChoice::MlKem768 {
            return None;
        }
        let (kem, enc) = self.kem_seeds.as_ref()?;
        #[allow(unused_mut)]
        let mut implementation = crate::kem::MlKem::new(kem.take().ok()?, enc.take().ok()?);
        #[cfg(feature = "fixtures")]
        implementation.fault(self.fault.clone());
        Some(Box::new(implementation))
    }
    fn resolve_rng(&self) -> Option<Box<dyn Random>> {
        if self.issued.replace(true) {
            return None;
        }
        Some(Box::new(OneShot {
            seed: Zeroizing::new(*self.seed),
            used: false,
        }))
    }
    fn resolve_dh(&self, c: &DHChoice) -> Option<Box<dyn Dh>> {
        match c {
            DHChoice::Curve25519 => Some(Box::new(SecretDh::default())),
            _ => None,
        }
    }
    fn resolve_hash(&self, c: &HashChoice) -> Option<Box<dyn Hash>> {
        DefaultResolver.resolve_hash(c)
    }
    fn resolve_cipher(&self, c: &CipherChoice) -> Option<Box<dyn Cipher>> {
        match c {
            CipherChoice::ChaChaPoly => Some(Box::new(SecretCipher::default())),
            _ => None,
        }
    }
}
