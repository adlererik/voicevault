#![no_main]
use libfuzzer_sys::fuzz_target;
use protocol::{Identity, Pin, fixtures};
fuzz_target!(|data: &[u8]| {
    let mut entropy = fixtures::Seeded::new(5);
    let a = Identity::new(&mut entropy).unwrap();
    let b = Identity::new(&mut entropy).unwrap();
    let pin = |i: &Identity| {
        let r = i.contact();
        Pin::verify(&r, r[..32].try_into().unwrap()).unwrap()
    };
    let mut fault = fixtures::KemFault::default();
    if data.first().is_some_and(|b| b & 1 == 0) {
        let mut pk = Box::new([0; 1184]);
        for (i, byte) in data.iter().skip(1).take(1184).enumerate() {
            pk[i] = *byte;
        }
        fault.public_key = Some(pk);
        let mut x = a
            .fixture_handshake_fault(&pin(&b), true, &[2; 32], Some(Box::new(fault)))
            .unwrap();
        let mut y = b.fixture_handshake(&pin(&a), false, &[3; 32]).unwrap();
        y.receive(&x.send().unwrap()).unwrap();
        if let Ok(wire) = y.send() {
            let _ = x.receive(&wire);
        }
    } else {
        let mut effective = [0u8; 1088];
        for part in data.get(1..).unwrap_or_default().chunks_exact(3).take(1024) {
            let index = usize::from(u16::from_le_bytes([part[0], part[1]])) % 1088;
            fault.ciphertext.push((index, part[2]));
            effective[index] ^= part[2];
        }
        let mut x = a.fixture_handshake(&pin(&b), true, &[2; 32]).unwrap();
        let mut y = b
            .fixture_handshake_fault(&pin(&a), false, &[3; 32], Some(Box::new(fault)))
            .unwrap();
        y.receive(&x.send().unwrap()).unwrap();
        let wire = y.send().unwrap();
        let result = x.receive(&wire);
        if effective.iter().any(|&b| b != 0) {
            assert!(result.is_err());
            assert!(x.split().is_err());
        } else {
            assert!(result.is_ok());
        }
    }
});
