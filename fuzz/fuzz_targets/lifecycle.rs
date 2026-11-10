#![no_main]
use libfuzzer_sys::fuzz_target;
use protocol::{
    Identity,
    contacts::{ContactBook, StorageRoot},
    enrollment::EnrolledContact,
    fixtures::Seeded,
    invitation::{Admission, Invitation, Kind, TrustedClock},
};
struct Clock;
impl TrustedClock for Clock {
    fn seconds(&self) -> u64 {
        100
    }
}
fuzz_target!(|data: &[u8]| {
    let mut entropy = Seeded::new(81);
    let a = Identity::new(&mut entropy).unwrap();
    let b = Identity::new(&mut entropy).unwrap();
    let ak = a.contact()[..32].try_into().unwrap();
    let bk = b.contact()[..32].try_into().unwrap();
    let mut ab = ContactBook::new(ak);
    let mut ba = ContactBook::new(bk);
    ab.install(
        EnrolledContact::verified_oob(b.contact(), &bk, true).unwrap(),
        "Bob",
    )
    .unwrap();
    ba.install(
        EnrolledContact::verified_oob(a.contact(), &ak, true).unwrap(),
        "Alice",
    )
    .unwrap();
    let mut ar = StorageRoot::new(&mut entropy).unwrap();
    let mut br = StorageRoot::new(&mut entropy).unwrap();
    let (offer, _) = Invitation::issue(
        &a,
        &mut ab,
        &bk,
        [7; 16],
        &Clock,
        Kind::Offer,
        None,
        &mut entropy,
        &mut ar,
    )
    .unwrap();
    let mut changed = *offer.as_bytes();
    for p in data.chunks_exact(2) {
        changed[usize::from(p[0]) % 128] ^= p[1];
    }
    let accepted = Invitation::parse(&changed)
        .and_then(|i| {
            i.verify(
                &b,
                &mut ba,
                &ak,
                &[7; 16],
                &Clock,
                &mut Admission::default(),
                &mut br,
            )
        })
        .is_ok();
    assert_eq!(accepted, changed == *offer.as_bytes());
    assert_eq!(br.generation(), u64::from(accepted));
    assert_eq!(
        offer
            .verify(
                &b,
                &mut ba,
                &ak,
                &[7; 16],
                &Clock,
                &mut Admission::default(),
                &mut br
            )
            .is_ok(),
        !accepted
    );
    let sealed = ba.persist(&mut br).unwrap();
    let mut corrupt = sealed;
    for p in data.chunks_exact(2) {
        let offset = (usize::from(p[0]) * 7) % corrupt.len();
        corrupt[offset] ^= p[1];
    }
    assert_eq!(
        ContactBook::restore(&corrupt, &br, bk).is_ok(),
        corrupt == sealed
    );
    assert!(ContactBook::restore(&sealed, &br, bk).is_ok());
});
