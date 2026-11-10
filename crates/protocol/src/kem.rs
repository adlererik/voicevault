//! ML-KEM-768 adapter for Snow's published (experimental) Noise HFS extension.
//! Fresh external entropy is consumed once. No OS RNG or fallback lives here.
use crate::Error;
use core::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use libcrux_ml_kem::mlkem768::{self, MlKem768Ciphertext, MlKem768PrivateKey, MlKem768PublicKey};
use snow::types::{Kem, Random};
use zeroize::{Zeroize, Zeroizing};

pub const PUBLIC: usize = 1184;
pub const CIPHERTEXT: usize = 1088;
const PRIVATE: usize = 2400;

/// Atomic consumption permits Snow's shared `encapsulate` interface without
/// cloning a seed, a mutex, a heap allocation or an OS dependency.
pub(crate) struct OnceSeed<const N: usize> {
    bytes: [AtomicU8; N],
    used: AtomicBool,
}
impl<const N: usize> OnceSeed<N> {
    pub(crate) fn new(seed: Zeroizing<[u8; N]>) -> Self {
        Self {
            bytes: core::array::from_fn(|i| AtomicU8::new(seed[i])),
            used: AtomicBool::new(false),
        }
    }
    pub(crate) fn take(&self) -> Result<Zeroizing<[u8; N]>, Error> {
        if self.used.swap(true, Ordering::AcqRel) {
            return Err(Error::Entropy);
        }
        let mut out = Zeroizing::new([0; N]);
        for (to, from) in out.iter_mut().zip(&self.bytes) {
            *to = from.swap(0, Ordering::Relaxed);
        }
        Ok(out)
    }
    #[cfg(test)]
    fn erased(&self) -> bool {
        self.bytes.iter().all(|b| b.load(Ordering::Relaxed) == 0)
    }
}
impl<const N: usize> Drop for OnceSeed<N> {
    fn drop(&mut self) {
        for byte in &mut self.bytes {
            byte.get_mut().zeroize();
        }
    }
}

struct Private(MlKem768PrivateKey);
impl Private {
    fn erase(&mut self) {
        self.0[0..PRIVATE].zeroize();
    }
}
impl Drop for Private {
    fn drop(&mut self) {
        self.erase();
    }
}

pub(crate) struct MlKem {
    key_seed: OnceSeed<64>,
    enc_seed: OnceSeed<32>,
    private: Option<Private>,
    public: [u8; PUBLIC],
    #[cfg(feature = "fixtures")]
    fault: Option<alloc::boxed::Box<super::fixtures::KemFault>>,
}
impl MlKem {
    pub(crate) fn new(key_seed: Zeroizing<[u8; 64]>, enc_seed: Zeroizing<[u8; 32]>) -> Self {
        Self {
            key_seed: OnceSeed::new(key_seed),
            enc_seed: OnceSeed::new(enc_seed),
            private: None,
            public: [0; PUBLIC],
            #[cfg(feature = "fixtures")]
            fault: None,
        }
    }
    #[cfg(feature = "fixtures")]
    pub(crate) fn fault(&mut self, fault: Option<alloc::boxed::Box<super::fixtures::KemFault>>) {
        self.fault = fault;
    }
}
impl Kem for MlKem {
    fn name(&self) -> &'static str {
        "MLKEM768"
    }
    fn pub_len(&self) -> usize {
        PUBLIC
    }
    fn ciphertext_len(&self) -> usize {
        CIPHERTEXT
    }
    fn shared_secret_len(&self) -> usize {
        32
    }
    fn generate(&mut self, _rng: &mut dyn Random) {
        // The fallible external entropy acquisition happened before the Noise
        // state was created. This infallible trait never substitutes randomness.
        let Ok(seed) = self.key_seed.take() else {
            self.private.take();
            self.public.fill(0);
            return;
        };
        let (private, public) = mlkem768::portable::generate_key_pair(*seed).into_parts();
        self.private = Some(Private(private));
        self.public.copy_from_slice(public.as_ref());
        #[cfg(feature = "fixtures")]
        if let Some(fault) = &self.fault
            && let Some(bytes) = &fault.public_key
        {
            self.public.copy_from_slice(bytes.as_ref());
        }
    }
    fn pubkey(&self) -> &[u8] {
        &self.public
    }
    fn encapsulate(
        &self,
        pk: &[u8],
        ss: &mut [u8],
        ct: &mut [u8],
    ) -> Result<(usize, usize), snow::Error> {
        if pk.len() != PUBLIC || ss.len() < 32 || ct.len() < CIPHERTEXT {
            return Err(snow::Error::Kem);
        }
        let pk = MlKem768PublicKey::try_from(pk).map_err(|_| snow::Error::Kem)?;
        if !mlkem768::portable::validate_public_key(&pk) {
            return Err(snow::Error::Kem);
        }
        let seed = self.enc_seed.take().map_err(|_| snow::Error::Rng)?;
        let (ciphertext, secret) = mlkem768::portable::encapsulate(&pk, *seed);
        let secret = Zeroizing::new(secret);
        ct[..CIPHERTEXT].copy_from_slice(ciphertext.as_ref());
        ss[..32].copy_from_slice(secret.as_ref());
        #[cfg(feature = "fixtures")]
        if let Some(fault) = &self.fault {
            for &(index, mask) in &fault.ciphertext {
                ct[index % CIPHERTEXT] ^= mask;
            }
        }
        Ok((32, CIPHERTEXT))
    }
    fn decapsulate(&self, ct: &[u8], ss: &mut [u8]) -> Result<usize, snow::Error> {
        if ct.len() != CIPHERTEXT || ss.len() < 32 {
            return Err(snow::Error::Kem);
        }
        let private = &self.private.as_ref().ok_or(snow::Error::Kem)?.0;
        let ct = MlKem768Ciphertext::try_from(ct).map_err(|_| snow::Error::Kem)?;
        if !mlkem768::portable::validate_private_key(private, &ct) {
            return Err(snow::Error::Kem);
        }
        // FIPS implicit rejection is not a public ciphertext-validity oracle.
        // The following Noise payload tag is mandatory key confirmation.
        let secret = Zeroizing::new(mlkem768::portable::decapsulate(private, &ct));
        ss[..32].copy_from_slice(secret.as_ref());
        Ok(32)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn consumed_entropy_is_erased_and_cannot_be_reused() {
        let seed = OnceSeed::new(Zeroizing::new([77; 64]));
        assert!(!seed.erased());
        let output = seed.take().unwrap();
        assert_eq!(&output[..], &[77; 64]);
        assert!(seed.erased());
        assert_eq!(seed.take(), Err(Error::Entropy));
    }
    #[test]
    fn private_key_explicit_zeroization_clears_owned_bytes() {
        let (private, _) = mlkem768::portable::generate_key_pair([42; 64]).into_parts();
        let mut private = Private(private);
        assert!(private.0.as_ref().iter().any(|&b| b != 0));
        private.erase();
        assert!(private.0.as_ref().iter().all(|&b| b == 0));
    }
}

#[cfg(test)]
mod acvp {
    use super::*;
    use serde_json::Value;
    fn hex(v: &Value) -> alloc::vec::Vec<u8> {
        v.as_str()
            .unwrap()
            .as_bytes()
            .as_chunks::<2>()
            .0
            .iter()
            .map(|b| u8::from_str_radix(core::str::from_utf8(b).unwrap(), 16).unwrap())
            .collect()
    }
    #[test]
    fn nist_acvp_mlkem768_all_keygen_vectors() {
        let json: Value =
            serde_json::from_str(include_str!("../tests/acvp/ML-KEM-keyGen-FIPS203.json")).unwrap();
        let mut count = 0;
        for group in json["testGroups"].as_array().unwrap() {
            for test in group["tests"].as_array().unwrap() {
                let mut seed = [0; 64];
                seed[..32].copy_from_slice(&hex(&test["d"]));
                seed[32..].copy_from_slice(&hex(&test["z"]));
                let (private, public) = mlkem768::portable::generate_key_pair(seed).into_parts();
                assert_eq!(private.as_ref(), hex(&test["dk"]));
                assert_eq!(public.as_ref(), hex(&test["ek"]));
                count += 1;
            }
        }
        assert_eq!(count, 25);
    }
    #[test]
    fn nist_acvp_mlkem768_encapsulation_decapsulation_and_key_validation_vectors() {
        let json: Value =
            serde_json::from_str(include_str!("../tests/acvp/ML-KEM-encapDecap-FIPS203.json"))
                .unwrap();
        let mut counts = [0; 4];
        for group in json["testGroups"].as_array().unwrap() {
            for test in group["tests"].as_array().unwrap() {
                match group["function"].as_str().unwrap() {
                    "encapsulation" => {
                        let public =
                            MlKem768PublicKey::try_from(hex(&test["ek"]).as_slice()).unwrap();
                        assert!(mlkem768::portable::validate_public_key(&public));
                        let (ct, key) = mlkem768::portable::encapsulate(
                            &public,
                            hex(&test["m"]).try_into().unwrap(),
                        );
                        assert_eq!(ct.as_ref(), hex(&test["c"]));
                        assert_eq!(key.as_slice(), hex(&test["k"]));
                        counts[0] += 1;
                    }
                    "decapsulation" => {
                        let private =
                            MlKem768PrivateKey::try_from(hex(&test["dk"]).as_slice()).unwrap();
                        let ct = MlKem768Ciphertext::try_from(hex(&test["c"]).as_slice()).unwrap();
                        assert!(mlkem768::portable::validate_private_key(&private, &ct));
                        assert_eq!(
                            mlkem768::portable::decapsulate(&private, &ct).as_slice(),
                            hex(&test["k"])
                        );
                        counts[1] += 1;
                    }
                    "decapsulationKeyCheck" => {
                        let private =
                            MlKem768PrivateKey::try_from(hex(&test["dk"]).as_slice()).unwrap();
                        let ct = MlKem768Ciphertext::from([0; CIPHERTEXT]);
                        assert_eq!(
                            mlkem768::portable::validate_private_key(&private, &ct),
                            test["testPassed"].as_bool().unwrap()
                        );
                        counts[2] += 1;
                    }
                    "encapsulationKeyCheck" => {
                        let public =
                            MlKem768PublicKey::try_from(hex(&test["ek"]).as_slice()).unwrap();
                        assert_eq!(
                            mlkem768::portable::validate_public_key(&public),
                            test["testPassed"].as_bool().unwrap()
                        );
                        counts[3] += 1;
                    }
                    _ => panic!("unexpected ACVP group"),
                }
            }
        }
        assert_eq!(counts, [25, 10, 10, 10]);
    }
}
