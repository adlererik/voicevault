use call_state::{Control, Replay};
use proptest::prelude::*;
use protocol::{Error, Identity, Media, OsEntropy, Pin, fixtures};

#[test]
fn contact_binds_distinct_static_key_to_pinned_signer() {
    let a = Identity::new(&mut OsEntropy).unwrap().contact();
    let b = Identity::new(&mut OsEntropy).unwrap().contact();
    let expected = a[..32].try_into().unwrap();
    assert!(Pin::verify(&a, &expected).is_ok());
    assert!(Pin::verify(&b, &expected).is_err());
    assert_ne!(a[..32], a[32..64]);
    let mut changed = a;
    changed[40] ^= 1;
    assert!(Pin::verify(&changed, &expected).is_err());
}

#[test]
fn bad_handshake_tag_and_wrong_pin_fail() {
    let (mut a, mut b) = fixtures::handshakes(0).unwrap();
    let mut wire = a.send().unwrap();
    wire[40] ^= 1;
    assert_eq!(b.receive(&wire), Err(Error::Handshake));
    assert!(b.split().is_err());

    let a = Identity::new(&mut OsEntropy).unwrap();
    let b = Identity::new(&mut OsEntropy).unwrap();
    let c = Identity::new(&mut OsEntropy).unwrap();
    let pin = |id: &Identity| {
        let record = id.contact();
        Pin::verify(&record, record[..32].try_into().unwrap()).unwrap()
    };
    let wire = a.handshake(&pin(&b), true).unwrap().send().unwrap();
    assert!(
        b.handshake(&pin(&c), false)
            .unwrap()
            .receive(&wire)
            .is_err()
    );
}

#[test]
fn reject_control_and_media_until_local_consent() {
    let (mut a, mut b) = fixtures::sessions(0).unwrap();
    assert_eq!(b.control(Control::Confirm), Err(Error::State));
    assert_eq!(b.media(0, Media::Filler), Err(Error::State));
    a.consent();
    b.receive(&a.control(Control::Confirm).unwrap(), 0..8)
        .unwrap();
    assert!(!b.active());
    assert_eq!(b.control(Control::Ready), Err(Error::State));
    let early = fixtures::peer_record(&a, 2, 3, &[]).unwrap();
    assert_eq!(b.receive(&early, 0..8), Err(Error::State));
    for command in 4..=7 {
        let wire = fixtures::peer_record(&a, 2, command, &[]).unwrap();
        assert_eq!(b.receive(&wire, 0..8), Err(Error::Command));
    }
}

#[test]
fn auth_and_counters_cannot_poison_window() {
    let (mut a, mut b) = fixtures::sessions(0).unwrap();
    fixtures::activate(&mut a, &mut b).unwrap();
    let first = a.media(0, Media::Filler).unwrap();
    let mut forged = first;
    forged[..8].copy_from_slice(&50_000u64.to_le_bytes());
    assert_eq!(b.receive(&forged, 0..8), Err(Error::Auth));
    let peer_forged = fixtures::peer_record(&a, 50_000, 3, &[]).unwrap();
    assert_eq!(b.receive(&peer_forged, 0..8), Err(Error::Counter));
    assert!(b.receive(&first, 0..8).is_ok());
    assert_eq!(b.receive(&first, 0..8), Err(Error::Replay));
    assert_eq!(a.media(0, Media::Filler), Err(Error::Counter));
    assert_eq!(a.media(u64::MAX, Media::Filler), Err(Error::Expired));
}

#[test]
fn reconnect_restarts_counter_with_fresh_split_and_directions() {
    fn call(a: &Identity, b: &Identity) -> (protocol::Session, protocol::Session) {
        let pin = |id: &Identity| {
            let record = id.contact();
            Pin::verify(&record, record[..32].try_into().unwrap()).unwrap()
        };
        let mut alice = a.handshake(&pin(b), true).unwrap();
        let mut bob = b.handshake(&pin(a), false).unwrap();
        bob.receive(&alice.send().unwrap()).unwrap();
        alice.receive(&bob.send().unwrap()).unwrap();
        let (mut alice, mut bob) = (alice.split().unwrap(), bob.split().unwrap());
        fixtures::activate(&mut alice, &mut bob).unwrap();
        (alice, bob)
    }
    let a = Identity::new(&mut OsEntropy).unwrap();
    let b = Identity::new(&mut OsEntropy).unwrap();
    let (mut first_a, mut first_b) = call(&a, &b);
    let old = first_a.media(0, Media::Filler).unwrap();
    let reflected = first_b.media(0, Media::Filler).unwrap();
    assert_ne!(old, reflected);
    assert_eq!(first_b.receive(&reflected, 0..8), Err(Error::Auth));
    drop((first_a, first_b));
    let (mut new_a, mut new_b) = call(&a, &b);
    let new = new_a.media(0, Media::Filler).unwrap();
    assert_eq!(new[..8], old[..8]);
    assert_ne!(new, old);
    assert_eq!(new_b.receive(&old, 0..8), Err(Error::Auth));
    assert!(new_b.receive(&new, 0..8).is_ok());
}

proptest! {
    #[test]
    fn bitmap_matches_set(sequences in prop::collection::vec(prop_oneof![0u64..256, any::<u64>()], 0..150)) {
        let mut window = Replay::default();
        let mut seen = std::collections::BTreeSet::new();
        for sequence in sequences {
            let eligible = sequence != u64::MAX && !seen.contains(&sequence) &&
                seen.last().is_none_or(|&head: &u64| head.saturating_sub(sequence) < 64);
            prop_assert_eq!(window.eligible(sequence), eligible);
            prop_assert_eq!(window.commit(sequence), eligible);
            if eligible {
                seen.insert(sequence);
                let head = *seen.last().unwrap();
                seen.retain(|&value| head - value < 64);
            }
        }
    }
}
