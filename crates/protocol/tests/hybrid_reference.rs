//! Independent, test-only transcription of Noise revision 34 plus the HFS
//! modifier prose (not its inconsistent KK example table). Does not call Snow.
//! This is a differential check, not an independent cryptographic audit.
use blake2::{Blake2s256, Digest};
use chacha20poly1305::{ChaCha20Poly1305, KeyInit, aead::AeadInPlace};
use curve25519_dalek::montgomery::MontgomeryPoint;
use protocol::{Entropy, Error, Identity, PATTERN, Pin};
fn hash(bytes: &[u8]) -> [u8; 32] {
    Blake2s256::digest(bytes).into()
}
fn hmac(key: &[u8], data: &[u8]) -> [u8; 32] {
    let mut ipad = [0x36; 64];
    let mut opad = [0x5c; 64];
    for (i, k) in key.iter().enumerate() {
        ipad[i] ^= k;
        opad[i] ^= k;
    }
    let mut h = Blake2s256::new();
    h.update(ipad);
    h.update(data);
    let inner = h.finalize();
    let mut h = Blake2s256::new();
    h.update(opad);
    h.update(inner);
    h.finalize().into()
}
fn hkdf(ck: &[u8; 32], input: &[u8]) -> ([u8; 32], [u8; 32]) {
    let temp = hmac(ck, input);
    let one = hmac(&temp, &[1]);
    let mut data = one.to_vec();
    data.push(2);
    (one, hmac(&temp, &data))
}
fn dh(secret: [u8; 32], public: [u8; 32]) -> [u8; 32] {
    MontgomeryPoint(public).mul_clamped(secret).to_bytes()
}
fn public(secret: [u8; 32]) -> [u8; 32] {
    MontgomeryPoint::mul_base_clamped(secret).to_bytes()
}
fn encrypt(key: &[u8; 32], nonce: u64, aad: &[u8], plain: &[u8]) -> Vec<u8> {
    let mut n = [0; 12];
    n[4..].copy_from_slice(&nonce.to_le_bytes());
    let mut out = plain.to_vec();
    let tag = ChaCha20Poly1305::new(key.into())
        .encrypt_in_place_detached((&n).into(), aad, &mut out)
        .unwrap();
    out.extend_from_slice(&tag);
    out
}
struct Ref {
    ck: [u8; 32],
    h: [u8; 32],
    key: [u8; 32],
}
impl Ref {
    fn new(name: &str, prologue: &[u8], as_: [u8; 32], bs: [u8; 32]) -> Self {
        let h = if name.len() <= 32 {
            let mut b = [0; 32];
            b[..name.len()].copy_from_slice(name.as_bytes());
            b
        } else {
            hash(name.as_bytes())
        };
        let mut s = Self {
            ck: h,
            h,
            key: [0; 32],
        };
        s.mix_hash(prologue);
        s.mix_hash(&as_);
        s.mix_hash(&bs);
        s
    }
    fn mix_hash(&mut self, data: &[u8]) {
        let mut h = Blake2s256::new();
        h.update(self.h);
        h.update(data);
        self.h = h.finalize().into();
    }
    fn mix_key(&mut self, data: &[u8]) {
        (self.ck, self.key) = hkdf(&self.ck, data);
    }
    fn enc(&mut self, data: &[u8]) -> Vec<u8> {
        let out = encrypt(&self.key, 0, &self.h, data);
        self.mix_hash(&out);
        out
    }
}
fn hex(v: &serde_json::Value) -> Vec<u8> {
    let s = v.as_str().unwrap();
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}
#[test]
fn independent_noise_reference_first_flight_matches_published_classical_vector() {
    let v: serde_json::Value = serde_json::from_str(include_str!("noise-kk.json")).unwrap();
    let ai = hex(&v["init_static"]).try_into().unwrap();
    let bi = hex(&v["resp_static"]).try_into().unwrap();
    let ae = hex(&v["init_ephemeral"]).try_into().unwrap();
    let mut s = Ref::new(
        v["protocol_name"].as_str().unwrap(),
        &hex(&v["init_prologue"]),
        public(ai),
        public(bi),
    );
    let mut first = public(ae).to_vec();
    s.mix_hash(&first);
    s.mix_key(&dh(ae, public(bi)));
    s.mix_key(&dh(ai, public(bi)));
    first.extend_from_slice(&s.enc(&hex(&v["messages"][0]["payload"])));
    assert_eq!(first, hex(&v["messages"][0]["ciphertext"]));
}
#[test]
fn hybrid_transcript_and_both_transport_keys_match_independent_reference() {
    use libcrux_ml_kem::mlkem768;
    struct Seeds(u8);
    impl Entropy for Seeds {
        fn seed(&mut self) -> Result<[u8; 32], Error> {
            self.0 += 1;
            Ok([self.0; 32])
        }
    }
    let a = Identity::new(&mut Seeds(0)).unwrap();
    let b = Identity::new(&mut Seeds(10)).unwrap();
    let pin = |i: &Identity| {
        let r = i.contact();
        Pin::verify(&r, r[..32].try_into().unwrap()).unwrap()
    };
    let ae = [31; 32];
    let be = [47; 32];
    let mut x = a.fixture_handshake(&pin(&b), true, &ae).unwrap();
    let mut y = b.fixture_handshake(&pin(&a), false, &be).unwrap();
    let first = x.send().unwrap();
    y.receive(&first).unwrap();
    let second = y.send().unwrap();
    x.receive(&second).unwrap();
    let derive = |e: &[u8; 32], i: u8| {
        let mut h = Blake2s256::new();
        h.update(b"PUBLIC VoiceVault hybrid fixture v2");
        h.update(e);
        h.update([i]);
        let b: [u8; 32] = h.finalize().into();
        b
    };
    let mut seed = [0; 64];
    seed[..32].copy_from_slice(&derive(&ae, 0));
    seed[32..].copy_from_slice(&derive(&ae, 1));
    let pair = mlkem768::portable::generate_key_pair(seed);
    let (ct, ss) = mlkem768::portable::encapsulate(pair.public_key(), derive(&be, 2));
    let mut prologue = b"VoiceVault hybrid call v2".to_vec();
    prologue.extend_from_slice(&a.contact()[..32]);
    prologue.extend_from_slice(&b.contact()[..32]);
    prologue.push(0);
    let mut s = Ref::new(PATTERN, &prologue, public([2; 32]), public([12; 32]));
    let mut expected = public(ae).to_vec();
    s.mix_hash(&expected);
    s.mix_key(&dh(ae, public([12; 32])));
    expected.extend_from_slice(&s.enc(pair.public_key().as_ref()));
    s.mix_key(&dh([2; 32], public([12; 32])));
    expected.extend_from_slice(&s.enc(&[]));
    assert_eq!(first, expected);
    let mut expected = public(be).to_vec();
    s.mix_hash(&expected);
    s.mix_key(&dh(ae, public(be)));
    expected.extend_from_slice(&s.enc(ct.as_ref()));
    s.mix_key(&ss);
    s.mix_key(&dh([2; 32], public(be)));
    expected.extend_from_slice(&s.enc(&[]));
    assert_eq!(second, expected);
    let (mut x, mut y) = (x.split().unwrap(), y.split().unwrap());
    assert_eq!(x.channel_binding(), s.h);
    assert_eq!(y.channel_binding(), s.h);
    let (k1, k2) = hkdf(&s.ck, &[]);
    x.consent();
    y.consent();
    let control = |key| {
        let mut wire = vec![0; 8];
        wire.extend_from_slice(&encrypt(&key, 0, &[], &[0; 104]));
        wire
    };
    assert_eq!(
        x.control(call_state::Control::Confirm).unwrap().as_slice(),
        control(k1)
    );
    assert_eq!(
        y.control(call_state::Control::Confirm).unwrap().as_slice(),
        control(k2)
    );
    // Consent is still needed even after a successful hybrid exchange.
    assert!(!x.active());
    assert!(!y.active());
}
