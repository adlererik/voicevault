use protocol::{Entropy, Error, HANDSHAKE_FIRST, HANDSHAKE_SECOND, Identity, Media, Pin, fixtures};
fn pin(id: &Identity) -> Pin {
    let c = id.contact();
    Pin::verify(&c, c[..32].try_into().unwrap()).unwrap()
}
fn identities() -> (Identity, Identity) {
    let mut e = fixtures::Seeded::new(42);
    (
        Identity::new(&mut e).unwrap(),
        Identity::new(&mut e).unwrap(),
    )
}

#[test]
fn hybrid_freshness_and_pq_contribution_with_classical_randomness_held_fixed() {
    struct Blocks {
        pq: u8,
        n: u8,
    }
    impl Entropy for Blocks {
        fn seed(&mut self) -> Result<[u8; 32], Error> {
            self.n += 1;
            Ok([if self.n == 1 { 3 } else { self.pq }; 32])
        }
    }
    let (a, b) = identities();
    let call = |pq| {
        let mut x = a
            .handshake_with_entropy(&pin(&b), true, &mut Blocks { pq, n: 0 }, Some(&[8; 32]))
            .unwrap();
        let mut y = b
            .handshake_with_entropy(&pin(&a), false, &mut Blocks { pq, n: 0 }, Some(&[8; 32]))
            .unwrap();
        let first = x.send().unwrap();
        assert_eq!(first.len(), HANDSHAKE_FIRST);
        y.receive(&first).unwrap();
        let second = y.send().unwrap();
        assert_eq!(second.len(), HANDSHAKE_SECOND);
        x.receive(&second).unwrap();
        let (mut x, mut y) = (x.split().unwrap(), y.split().unwrap());
        assert_eq!(x.channel_binding(), y.channel_binding());
        fixtures::activate(&mut x, &mut y).unwrap();
        let wire = x.media(0, Media::Filler).unwrap();
        assert!(y.receive(&wire, 0..8).is_ok());
        (first, second, wire)
    };
    let (a, b, c) = call(10);
    let (x, y, z) = call(20);
    assert_eq!(a[..32], x[..32]);
    assert_eq!(b[..32], y[..32]); // same DH ephemerals
    assert_ne!(a[32..], x[32..]);
    assert_ne!(b[32..], y[32..]);
    assert_ne!(c, z);
}

#[test]
fn every_entropy_acquisition_failure_is_fatal_without_fallback() {
    struct Fails {
        at: u8,
        n: u8,
    }
    impl Entropy for Fails {
        fn seed(&mut self) -> Result<[u8; 32], Error> {
            self.n += 1;
            if self.at == self.n {
                Err(Error::Entropy)
            } else {
                Ok([self.n; 32])
            }
        }
    }
    let (a, b) = identities();
    for role in [true, false] {
        for at in 1..=4 {
            let mut e = Fails { at, n: 0 };
            assert!(matches!(
                a.handshake_with_entropy(&pin(&b), role, &mut e, None),
                Err(Error::Entropy)
            ));
            assert_eq!(e.n, at);
        }
    }
}

#[test]
fn classical_only_truncated_oversized_and_wrong_order_never_create_a_session() {
    for len in [0, 1, 32, 48, HANDSHAKE_FIRST - 1, HANDSHAKE_FIRST + 1, 4096] {
        let (_, mut b) = fixtures::handshakes(1).unwrap();
        assert!(b.receive(&vec![0; len]).is_err());
        assert!(b.send().is_err());
        assert!(b.split().is_err());
    }
    let (mut a, mut b) = fixtures::handshakes(1).unwrap();
    assert!(b.send().is_err());
    assert!(b.split().is_err());
    assert!(a.receive(&[0; HANDSHAKE_SECOND]).is_err());
    assert!(a.send().is_err());
    assert!(a.split().is_err());
    let (a, b) = fixtures::handshakes(1).unwrap();
    assert!(a.split().is_err());
    assert!(b.split().is_err());
}

#[test]
fn tampering_at_every_hybrid_message_byte_is_rejected_and_poisoned() {
    // Replay an authentic flight into a fresh matching receiver, mutate each
    // byte once, including DH points, encrypted KEM material and final tags.
    let (mut a, _) = fixtures::handshakes(9).unwrap();
    let first = a.send().unwrap();
    for index in 0..first.len() {
        let (_, mut b) = fixtures::handshakes(9).unwrap();
        let mut corrupt = first.clone();
        corrupt[index] ^= 1;
        assert!(b.receive(&corrupt).is_err(), "first byte {index}");
        assert!(b.receive(&first).is_err());
        assert!(b.split().is_err());
    }
    let (mut a, mut b) = fixtures::handshakes(9).unwrap();
    b.receive(&a.send().unwrap()).unwrap();
    let second = b.send().unwrap();
    for index in 0..second.len() {
        let (mut a, _) = fixtures::handshakes(9).unwrap();
        a.send().unwrap();
        let mut corrupt = second.clone();
        corrupt[index] ^= 1;
        assert!(a.receive(&corrupt).is_err(), "second byte {index}");
        assert!(a.receive(&second).is_err());
        assert!(a.split().is_err());
    }
}

#[test]
fn duplicate_reflected_and_cross_call_responses_fail_closed() {
    let (mut a, mut b) = fixtures::handshakes(1).unwrap();
    let first = a.send().unwrap();
    b.receive(&first).unwrap();
    assert!(b.receive(&first).is_err());
    assert!(b.send().is_err());
    assert!(b.split().is_err());
    let (mut a, mut b) = fixtures::handshakes(1).unwrap();
    b.receive(&a.send().unwrap()).unwrap();
    let old = b.send().unwrap();
    a.receive(&old).unwrap();
    assert!(a.receive(&old).is_err());
    assert!(a.split().is_err());
    let (mut fresh, _) = fixtures::handshakes(2).unwrap();
    fresh.send().unwrap();
    assert!(fresh.receive(&old).is_err());
    assert!(fresh.split().is_err());
    let (mut a, _) = fixtures::handshakes(1).unwrap();
    let first = a.send().unwrap();
    assert!(a.receive(&first).is_err());
    assert!(a.split().is_err());
}

#[test]
fn both_verified_identities_roles_and_invitation_context_are_bound() {
    let (a, b) = identities();
    let c = Identity::new(&mut fixtures::Seeded::new(99)).unwrap();
    for wrong_peer in [false, true] {
        let mut ea = fixtures::Seeded::new(10);
        let mut eb = fixtures::Seeded::new(20);
        let mut x = a
            .handshake_with_entropy(&pin(&b), true, &mut ea, Some(&[1; 32]))
            .unwrap();
        let mut y = b
            .handshake_with_entropy(
                &pin(if wrong_peer { &c } else { &a }),
                false,
                &mut eb,
                Some(&[if wrong_peer { 1 } else { 2 }; 32]),
            )
            .unwrap();
        assert!(y.receive(&x.send().unwrap()).is_err());
        assert!(y.split().is_err());
    }
    let mut x = a
        .handshake_with_entropy(&pin(&b), true, &mut fixtures::Seeded::new(10), None)
        .unwrap();
    let mut y = b
        .handshake_with_entropy(
            &pin(&a),
            false,
            &mut fixtures::Seeded::new(20),
            Some(&[0; 32]),
        )
        .unwrap();
    assert!(y.receive(&x.send().unwrap()).is_err());
}

#[test]
fn authenticated_invalid_kem_public_key_cannot_trigger_encapsulation() {
    let (a, b) = identities();
    let fault = fixtures::KemFault {
        public_key: Some(Box::new([255; 1184])),
        ..Default::default()
    };
    let mut x = a
        .fixture_handshake_fault(&pin(&b), true, &[2; 32], Some(Box::new(fault)))
        .unwrap();
    let mut y = b.fixture_handshake(&pin(&a), false, &[3; 32]).unwrap();
    y.receive(&x.send().unwrap()).unwrap(); // valid classical authentication
    assert!(y.send().is_err());
    assert!(y.split().is_err());
}

#[test]
fn authenticated_corrupt_kem_ciphertext_fails_key_confirmation() {
    let (a, b) = identities();
    for index in [0, 1, 767, 1023, 1087] {
        let fault = fixtures::KemFault {
            ciphertext: vec![(index, 1)],
            ..Default::default()
        };
        let mut x = a.fixture_handshake(&pin(&b), true, &[2; 32]).unwrap();
        let mut y = b
            .fixture_handshake_fault(&pin(&a), false, &[3; 32], Some(Box::new(fault)))
            .unwrap();
        y.receive(&x.send().unwrap()).unwrap();
        let wire = y.send().unwrap();
        // The outer ciphertext tag is valid; decapsulation produces an implicit
        // rejection secret, and the mandatory following Noise tag must fail.
        assert!(x.receive(&wire).is_err());
        assert!(x.split().is_err());
        let mut y = y.split().unwrap();
        assert!(!y.active());
        assert!(y.media(0, Media::Filler).is_err());
    }
}

#[test]
fn a_valid_legacy_noise_kk_exchange_is_rejected_as_a_downgrade() {
    use snow::Builder;
    struct ConstantStatic(u8);
    impl Entropy for ConstantStatic {
        fn seed(&mut self) -> Result<[u8; 32], Error> {
            self.0 += 1;
            Ok([self.0; 32])
        }
    }
    let a = Identity::new(&mut ConstantStatic(0)).unwrap();
    let b = Identity::new(&mut ConstantStatic(10)).unwrap();
    let ac = a.contact();
    let bc = b.contact();
    let legacy = |own: &[u8; 32], remote: &[u8], initiator| {
        let builder = Builder::with_resolver(
            "Noise_KK_25519_ChaChaPoly_BLAKE2s".parse().unwrap(),
            fixtures::resolver(),
        )
        .local_private_key(own)
        .unwrap()
        .remote_public_key(remote)
        .unwrap()
        .prologue(b"quietlink call v1")
        .unwrap();
        if initiator {
            builder.build_initiator().unwrap()
        } else {
            builder.build_responder().unwrap()
        }
    };
    let (mut x, mut y) = (
        legacy(&[2; 32], &bc[32..64], true),
        legacy(&[12; 32], &ac[32..64], false),
    );
    let mut flight = [0; 48];
    assert_eq!(x.write_message(&[], &mut flight).unwrap(), 48);
    assert_eq!(y.read_message(&flight, &mut []).unwrap(), 0);
    let mut modern = b.handshake(&pin(&a), false).unwrap();
    assert_eq!(modern.receive(&flight), Err(Error::Size));
    assert!(modern.send().is_err());
    assert!(modern.split().is_err());
    let mut padded = vec![0; HANDSHAKE_FIRST];
    padded[..48].copy_from_slice(&flight);
    let mut modern = b.handshake(&pin(&a), false).unwrap();
    assert_eq!(modern.receive(&padded), Err(Error::Handshake));
    assert!(modern.split().is_err());
}

#[test]
fn two_contacts_sharing_a_dh_key_cannot_be_substituted_for_each_other() {
    struct Fixed {
        sign: u8,
        first: bool,
    }
    impl Entropy for Fixed {
        fn seed(&mut self) -> Result<[u8; 32], Error> {
            let byte = if self.first { self.sign } else { 44 };
            self.first = false;
            Ok([byte; 32])
        }
    }
    let (a, _) = identities();
    let b = Identity::new(&mut Fixed {
        sign: 1,
        first: true,
    })
    .unwrap();
    let c = Identity::new(&mut Fixed {
        sign: 2,
        first: true,
    })
    .unwrap();
    assert_eq!(b.contact()[32..64], c.contact()[32..64]);
    assert_ne!(b.contact()[..32], c.contact()[..32]);
    let mut x = a.handshake(&pin(&c), true).unwrap();
    let mut y = b.handshake(&pin(&a), false).unwrap();
    assert_eq!(y.receive(&x.send().unwrap()), Err(Error::Handshake));
    assert!(y.split().is_err());
}
