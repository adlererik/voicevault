#![no_main]
use ed25519_dalek::SigningKey;
use libfuzzer_sys::fuzz_target;
use protocol::{
    radio::{QUEUE, RadioPort},
    update::{BootPolicy, fixture_image},
};
fuzz_target!(|data: &[u8]| {
    let key = SigningKey::from_bytes(&[8; 32]);
    let policy = BootPolicy::new(7, key.verifying_key().to_bytes()).unwrap();
    let _ = policy.verify_envelope(data);
    let original = fixture_image(&[4; 256], 7, 2, &key);
    let mut changed = original.clone();
    for p in data.chunks_exact(3) {
        let n = (usize::from(p[0]) * 256 + usize::from(p[1])) % changed.len();
        changed[n] ^= p[2];
    }
    assert_eq!(
        policy.verify_envelope(&changed).is_ok(),
        changed == original
    );
    let mut radio = RadioPort::default();
    for (i, chunk) in data.chunks(40).enumerate() {
        let _ = radio.receive(chunk, (i / 8) as u64);
        assert!(radio.depth() <= QUEUE);
        if chunk.first().is_some_and(|b| b & 1 == 1) {
            radio.controller_reset();
        }
        if chunk.first().is_some_and(|b| b & 2 == 2) {
            let _ = radio.pop((i / 8) as u64);
        }
    }
    radio.local_update_mode(true);
    radio.controller_reset();
    assert!(radio.receive(&[1, 6, 0, 0, 0, 0, 0, 0], 1000).is_err());
});
