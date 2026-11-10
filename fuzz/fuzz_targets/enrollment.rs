#![no_main]
use libfuzzer_sys::fuzz_target;
use protocol::{
    Identity,
    enrollment::{Enrollment, MAX_ENROLLMENT_MESSAGE},
    fixtures::Seeded,
};
fuzz_target!(|data: &[u8]| {
    let mut entropy = Seeded::new(80);
    let a = Identity::new(&mut entropy).unwrap();
    let b = Identity::new(&mut entropy).unwrap();
    let mut x = Enrollment::new(&a, true, &mut entropy).unwrap();
    let mut y = Enrollment::new(&b, false, &mut entropy).unwrap();
    let mut wire = [0; MAX_ENROLLMENT_MESSAGE];
    let target = data.first().copied().unwrap_or(0) % 4;
    for stage in 0..3 {
        let n = if stage == 1 {
            y.write(&mut wire)
        } else {
            x.write(&mut wire)
        }
        .unwrap();
        if stage == target {
            for p in data.get(1..).unwrap_or_default().chunks_exact(2) {
                wire[usize::from(p[0]) % n] ^= p[1];
            }
        }
        let read = if stage == 1 {
            x.read(&wire[..n])
        } else {
            y.read(&wire[..n])
        };
        if read.is_err() {
            if stage == 1 {
                assert!(x.finish().is_err())
            } else {
                assert!(y.finish().is_err())
            }
            return;
        }
    }
    let mut x = x.finish().unwrap();
    let mut y = y.finish().unwrap();
    let fp = x.fingerprint();
    assert_eq!(fp, y.fingerprint());
    let mut confirm = x.confirm_local(&fp, true).unwrap();
    if target == 3 {
        for p in data.get(1..).unwrap_or_default().chunks_exact(2) {
            confirm[usize::from(p[0]) % 48] ^= p[1];
        }
    }
    let yc = y.confirm_local(&fp, true).unwrap();
    if y.receive_confirmation(&confirm).is_err() {
        assert!(y.complete().is_err());
        return;
    }
    x.receive_confirmation(&yc).unwrap();
    assert_eq!(x.complete().unwrap().record(), &b.contact());
    assert_eq!(y.complete().unwrap().record(), &a.contact());
});
