use ed25519_dalek::SigningKey;
use proptest::prelude::*;
use protocol::{
    contacts::*, enrollment::*, entropy::*, fixtures::Seeded, invitation::*, update::*, *,
};

struct Clock(u64);
impl TrustedClock for Clock {
    fn seconds(&self) -> u64 {
        self.0
    }
}
fn id(i: &Identity) -> [u8; 32] {
    i.contact()[..32].try_into().unwrap()
}
fn identities() -> (Identity, Identity, Seeded, Seeded) {
    let mut ea = Seeded::new(100);
    let mut eb = Seeded::new(200);
    (
        Identity::new(&mut ea).unwrap(),
        Identity::new(&mut eb).unwrap(),
        ea,
        eb,
    )
}
fn ceremony(a: &Identity, b: &Identity, ea: &mut Seeded, eb: &mut Seeded) -> (Pairing, Pairing) {
    let mut a = Enrollment::new(a, true, ea).unwrap();
    let mut b = Enrollment::new(b, false, eb).unwrap();
    let mut buf = [0; MAX_ENROLLMENT_MESSAGE];
    let n = a.write(&mut buf).unwrap();
    b.read(&buf[..n]).unwrap();
    let n = b.write(&mut buf).unwrap();
    a.read(&buf[..n]).unwrap();
    let n = a.write(&mut buf).unwrap();
    b.read(&buf[..n]).unwrap();
    (a.finish().unwrap(), b.finish().unwrap())
}
fn books(
    a: &Identity,
    b: &Identity,
    ea: &mut Seeded,
    eb: &mut Seeded,
) -> (ContactBook, ContactBook) {
    let (mut pa, mut pb) = ceremony(a, b, ea, eb);
    let fa = pa.fingerprint();
    let fb = pb.fingerprint();
    assert_eq!(fa, fb);
    let ac = pa.confirm_local(&fb, true).unwrap();
    let bc = pb.confirm_local(&fa, true).unwrap();
    pa.receive_confirmation(&bc).unwrap();
    pb.receive_confirmation(&ac).unwrap();
    let mut ba = ContactBook::new(id(a));
    let mut bb = ContactBook::new(id(b));
    ba.install(pa.complete().unwrap(), "Bob").unwrap();
    bb.install(pb.complete().unwrap(), "Alice").unwrap();
    (ba, bb)
}
#[allow(clippy::too_many_arguments)]
fn sessions(
    a: &Identity,
    b: &Identity,
    ba: &ContactBook,
    bb: &ContactBook,
    ea: &mut Seeded,
    eb: &mut Seeded,
    ca: &[u8; 32],
    cb: &[u8; 32],
) -> Result<(Session, Session), Error> {
    let mut x = a.handshake_with_entropy(&ba.pin(&id(b)).unwrap(), true, ea, Some(ca))?;
    let mut y = b.handshake_with_entropy(&bb.pin(&id(a)).unwrap(), false, eb, Some(cb))?;
    y.receive(&x.send()?)?;
    x.receive(&y.send()?)?;
    Ok((x.split()?, y.split()?))
}

#[test]
fn enrollment_requires_both_local_comparisons_and_authenticated_confirmations() {
    let (a, b, mut ea, mut eb) = identities();
    let (mut pa, mut pb) = ceremony(&a, &b, &mut ea, &mut eb);
    let fa = pa.fingerprint();
    let fb = pb.fingerprint();
    let ac = pa.confirm_local(&fb, true).unwrap();
    pb.receive_confirmation(&ac).unwrap();
    assert!(pb.complete().is_err());
    let (mut pa, mut pb) = ceremony(&a, &b, &mut ea, &mut eb);
    let fa2 = pa.fingerprint();
    assert_ne!(fa, fa2);
    assert!(pa.confirm_local(&[0; 32], true).is_err());
    assert!(pa.complete().is_err());
    assert!(pb.confirm_local(&fa2, false).is_err());
    assert!(pb.complete().is_err());
    let (ba, bb) = books(&a, &b, &mut ea, &mut eb);
    assert!(ba.pin(&id(&b)).is_ok());
    assert!(bb.pin(&id(&a)).is_ok());
}

#[test]
fn mitm_creates_different_display_fingerprints() {
    let (a, b, mut ea, mut eb) = identities();
    let mut em = Seeded::new(300);
    let m = Identity::new(&mut em).unwrap();
    let (mut a_to_m, _) = ceremony(&a, &m, &mut ea, &mut em);
    let (_, b_to_m) = ceremony(&m, &b, &mut em, &mut eb);
    assert_ne!(a_to_m.fingerprint(), b_to_m.fingerprint());
    assert!(a_to_m.confirm_local(&b_to_m.fingerprint(), true).is_err());
}

#[test]
fn malformed_enrollment_poisoned_state_and_confirmation_replay_fail() {
    let (a, b, mut ea, mut eb) = identities();
    let mut p = Enrollment::new(&b, false, &mut eb).unwrap();
    assert!(p.read(&[]).is_err());
    let mut good = Enrollment::new(&a, true, &mut ea).unwrap();
    let mut buf = [0; MAX_ENROLLMENT_MESSAGE];
    let n = good.write(&mut buf).unwrap();
    assert!(p.read(&buf[..n]).is_err());
    assert!(p.finish().is_err());
    let (mut pa, mut pb) = ceremony(&a, &b, &mut ea, &mut eb);
    let fp = pa.fingerprint();
    let msg = pa.confirm_local(&fp, true).unwrap();
    pb.receive_confirmation(&msg).unwrap();
    assert!(pb.receive_confirmation(&msg).is_err());
    let (mut fresh, _) = ceremony(&a, &b, &mut ea, &mut eb);
    assert!(fresh.receive_confirmation(&msg).is_err());
}

#[test]
fn sealed_contacts_reject_tampering_rollback_wrong_device_and_unavailable_root() {
    let (a, b, mut ea, mut eb) = identities();
    let (ba, _) = books(&a, &b, &mut ea, &mut eb);
    let mut root = StorageRoot::new(&mut ea).unwrap();
    let first = ba.persist(&mut root).unwrap();
    let mut restored = ContactBook::restore(&first, &root, id(&a)).unwrap();
    assert!(restored.pin(&id(&b)).is_ok());
    for offset in [0, 8, 80, SNAPSHOT_BYTES - 1] {
        let mut changed = first;
        changed[offset] ^= 1;
        assert!(ContactBook::restore(&changed, &root, id(&a)).is_err());
    }
    assert!(ContactBook::restore(&first, &root, id(&b)).is_err());
    let another = StorageRoot::new(&mut eb).unwrap();
    assert!(ContactBook::restore(&first, &another, id(&a)).is_err());
    restored.revoke(&id(&b)).unwrap();
    let second = restored.persist(&mut root).unwrap();
    assert!(ContactBook::restore(&first, &root, id(&a)).is_err());
    assert!(
        ContactBook::restore(&second, &root, id(&a))
            .unwrap()
            .pin(&id(&b))
            .is_err()
    );
    root.set_unavailable(true);
    assert!(ba.persist(&mut root).is_err());
    assert!(ContactBook::restore(&second, &root, id(&a)).is_err());
    root.set_unavailable(false);
    let generation = root.generation();
    let _ = ba.persist(&mut root).unwrap();
    assert_eq!(root.generation(), generation + 1);
}

#[test]
fn local_enrollment_and_contact_capacity_are_bounded() {
    let (a, b, mut ea, _) = identities();
    assert!(EnrolledContact::verified_oob(b.contact(), &id(&b), false).is_err());
    assert!(EnrolledContact::verified_oob(b.contact(), &id(&a), true).is_err());
    let mut book = ContactBook::new(id(&a));
    for n in 0..CONTACT_SLOTS + 1 {
        let person = Identity::new(&mut ea).unwrap();
        let contact = EnrolledContact::verified_oob(person.contact(), &id(&person), true).unwrap();
        assert_eq!(book.install(contact, "Peer").is_ok(), n < CONTACT_SLOTS);
    }
}

#[test]
fn invitations_bind_peer_recipient_boot_nonce_time_and_persist_replay_state() {
    let (a, b, mut ea, mut eb) = identities();
    let (mut ba, mut bb) = books(&a, &b, &mut ea, &mut eb);
    let mut ra = StorageRoot::new(&mut ea).unwrap();
    let mut rb = StorageRoot::new(&mut eb).unwrap();
    let challenge = [7; 16];
    let (offer, _) = Invitation::issue(
        &a,
        &mut ba,
        &id(&b),
        challenge,
        &Clock(100),
        Kind::Offer,
        None,
        &mut ea,
        &mut ra,
    )
    .unwrap();
    let mut admission = Admission::default();
    let mut forged = *offer.as_bytes();
    forged[8..16].copy_from_slice(&u64::MAX.to_le_bytes());
    let forged = Invitation::parse(&forged).unwrap();
    assert!(
        forged
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &challenge,
                &Clock(100),
                &mut admission,
                &mut rb
            )
            .is_err()
    );
    assert_eq!(rb.generation(), 0);
    assert!(
        offer
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &[8; 16],
                &Clock(100),
                &mut admission,
                &mut rb
            )
            .is_err()
    );
    assert!(
        offer
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &challenge,
                &Clock(99),
                &mut Admission::default(),
                &mut rb
            )
            .is_err()
    );
    assert!(
        offer
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &challenge,
                &Clock(161),
                &mut Admission::default(),
                &mut rb
            )
            .is_err()
    );
    let (verified, saved) = offer
        .verify(
            &b,
            &mut bb,
            &id(&a),
            &challenge,
            &Clock(100),
            &mut admission,
            &mut rb,
        )
        .unwrap();
    assert_eq!(verified.trusted_name(), "Alice");
    assert_eq!(verified.kind(), Kind::Offer);
    assert!(
        offer
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &challenge,
                &Clock(100),
                &mut admission,
                &mut rb
            )
            .is_err()
    );
    let mut restored = ContactBook::restore(&saved, &rb, id(&b)).unwrap();
    assert!(
        offer
            .verify(
                &b,
                &mut restored,
                &id(&a),
                &challenge,
                &Clock(100),
                &mut Admission::default(),
                &mut rb
            )
            .is_err()
    );
    restored.revoke(&id(&a)).unwrap();
    assert!(
        offer
            .verify(
                &b,
                &mut restored,
                &id(&a),
                &challenge,
                &Clock(100),
                &mut Admission::default(),
                &mut rb
            )
            .is_err()
    );
}

#[test]
fn invitation_admission_bounds_signature_work_and_never_uses_phone_time() {
    let (a, b, mut ea, mut eb) = identities();
    let (mut ba, mut bb) = books(&a, &b, &mut ea, &mut eb);
    let mut ra = StorageRoot::new(&mut ea).unwrap();
    let mut rb = StorageRoot::new(&mut eb).unwrap();
    let (offer, _) = Invitation::issue(
        &a,
        &mut ba,
        &id(&b),
        [9; 16],
        &Clock(20),
        Kind::Offer,
        None,
        &mut ea,
        &mut ra,
    )
    .unwrap();
    let mut bad = *offer.as_bytes();
    bad[127] ^= 1;
    let bad = Invitation::parse(&bad).unwrap();
    let mut gate = Admission::default();
    for _ in 0..8 {
        assert!(
            bad.verify(
                &b,
                &mut bb,
                &id(&a),
                &[9; 16],
                &Clock(20),
                &mut gate,
                &mut rb
            )
            .is_err()
        );
    }
    assert!(matches!(
        offer.verify(
            &b,
            &mut bb,
            &id(&a),
            &[9; 16],
            &Clock(20),
            &mut gate,
            &mut rb
        ),
        Err(PolicyError::Busy)
    ));
    assert!(matches!(
        offer.verify(
            &b,
            &mut bb,
            &id(&a),
            &[9; 16],
            &Clock(19),
            &mut gate,
            &mut rb
        ),
        Err(PolicyError::Clock)
    ));
    assert!(
        offer
            .verify(
                &b,
                &mut bb,
                &id(&a),
                &[9; 16],
                &Clock(21),
                &mut gate,
                &mut rb
            )
            .is_ok()
    );
}

#[test]
fn accepted_invitation_binds_noise_and_epoch_renewal_needs_fresh_keys() {
    let (a, b, mut ea, mut eb) = identities();
    let (mut ba, mut bb) = books(&a, &b, &mut ea, &mut eb);
    let mut ra = StorageRoot::new(&mut ea).unwrap();
    let mut rb = StorageRoot::new(&mut eb).unwrap();
    let (offer, _) = Invitation::issue(
        &a,
        &mut ba,
        &id(&b),
        [7; 16],
        &Clock(100),
        Kind::Offer,
        None,
        &mut ea,
        &mut ra,
    )
    .unwrap();
    let (v_offer, _) = offer
        .verify(
            &b,
            &mut bb,
            &id(&a),
            &[7; 16],
            &Clock(100),
            &mut Admission::default(),
            &mut rb,
        )
        .unwrap();
    let (accept, _) = Invitation::issue(
        &b,
        &mut bb,
        &id(&a),
        [8; 16],
        &Clock(100),
        Kind::Accept,
        Some(v_offer.call_nonce()),
        &mut eb,
        &mut rb,
    )
    .unwrap();
    let (v_accept, _) = accept
        .verify(
            &a,
            &mut ba,
            &id(&b),
            &[8; 16],
            &Clock(100),
            &mut Admission::default(),
            &mut ra,
        )
        .unwrap();
    let ca = call_context(&a, &ba, &offer, &v_accept).unwrap();
    let cb = call_context(&b, &bb, &accept, &v_offer).unwrap();
    assert_eq!(ca, cb);
    let (mut x, mut y) = sessions(&a, &b, &ba, &bb, &mut ea, &mut eb, &ca, &cb).unwrap();
    assert!(x.media(0, Media::Filler).is_err());
    fixtures::activate(&mut x, &mut y).unwrap();
    let old = x.media(MAX_EPOCH_SLOTS - 1, Media::Filler).unwrap();
    assert!(matches!(
        x.media(MAX_EPOCH_SLOTS, Media::Filler),
        Err(Error::Expired)
    ));
    assert!(!x.active());
    assert!(matches!(x.media(0, Media::Filler), Err(Error::State)));
    let (mut nx, mut ny) = sessions(&a, &b, &ba, &bb, &mut ea, &mut eb, &ca, &cb).unwrap();
    fixtures::activate(&mut nx, &mut ny).unwrap();
    assert_ne!(x.channel_binding(), nx.channel_binding());
    assert!(ny.receive(&old, 0..MAX_EPOCH_SLOTS).is_err());
    let fresh = nx.media(0, Media::Filler).unwrap();
    assert!(y.receive(&fresh, 0..8).is_err());
    assert!(ny.receive(&fresh, 0..8).is_ok());
    x.close();
    x.consent();
    assert!(!x.active());
    assert!(x.media(0, Media::Filler).is_err());
    assert!(sessions(&a, &b, &ba, &bb, &mut ea, &mut eb, &ca, &[0; 32]).is_err());
}

struct Sources {
    generation: u64,
    failed: [bool; 3],
    stuck: bool,
}
impl HardwareSources for Sources {
    fn next_protected_generation(&mut self) -> PolicyResult<u64> {
        self.generation += 1;
        Ok(self.generation)
    }
    fn read_source(&mut self, i: usize, out: &mut [u8; 32]) -> PolicyResult<()> {
        if self.failed[i] {
            return Err(PolicyError::Entropy);
        }
        for (n, b) in out.iter_mut().enumerate() {
            *b = n as u8 ^ (i as u8 * 31) ^ if self.stuck { 0 } else { self.generation as u8 };
        }
        Ok(())
    }
}
#[test]
fn onboard_entropy_fails_closed_without_two_healthy_sources() {
    for mask in 0u8..8 {
        let failed = core::array::from_fn(|i| mask & (1 << i) != 0);
        let mut pool = EntropyPool::new(Sources {
            generation: 0,
            failed,
            stuck: false,
        });
        assert_eq!(pool.conditioned_seed().is_ok(), mask.count_ones() <= 1);
    }
    let mut pool = EntropyPool::new(Sources {
        generation: 0,
        failed: [false; 3],
        stuck: true,
    });
    assert!(pool.conditioned_seed().is_ok());
    assert!(pool.conditioned_seed().is_err());
    let mut pool = EntropyPool::new(Sources {
        generation: 0,
        failed: [false; 3],
        stuck: false,
    });
    let first = pool.conditioned_seed().unwrap();
    assert_ne!(first, pool.conditioned_seed().unwrap());
    pool.source_mut().generation = 0;
    assert!(pool.conditioned_seed().is_err());
}

#[derive(Clone)]
struct Flash {
    banks: [Vec<u8>; 2],
    remaining: Option<usize>,
    torn: bool,
}
impl Flash {
    fn new() -> Self {
        Self {
            banks: [vec![0xff; 8192], vec![0xff; 8192]],
            remaining: None,
            torn: false,
        }
    }
    fn operation(&mut self) -> PolicyResult<()> {
        if let Some(n) = self.remaining.as_mut() {
            if *n == 0 {
                return Err(PolicyError::Storage);
            }
            *n -= 1;
        }
        Ok(())
    }
}
impl FlashBanks for Flash {
    fn capacity(&self) -> usize {
        8192
    }
    fn read(&self, b: usize, o: usize, out: &mut [u8]) -> PolicyResult<()> {
        let x = self
            .banks
            .get(b)
            .and_then(|x| x.get(o..o + out.len()))
            .ok_or(PolicyError::Storage)?;
        out.copy_from_slice(x);
        Ok(())
    }
    fn erase(&mut self, b: usize) -> PolicyResult<()> {
        self.operation()?;
        self.banks
            .get_mut(b)
            .ok_or(PolicyError::Storage)?
            .fill(0xff);
        Ok(())
    }
    fn write(&mut self, b: usize, o: usize, x: &[u8]) -> PolicyResult<()> {
        if self.operation().is_err() {
            if self.torn {
                let n = x.len() / 2;
                self.banks[b][o..o + n].copy_from_slice(&x[..n]);
            }
            return Err(PolicyError::Storage);
        }
        self.banks
            .get_mut(b)
            .and_then(|v| v.get_mut(o..o + x.len()))
            .ok_or(PolicyError::Storage)?
            .copy_from_slice(x);
        Ok(())
    }
}
#[test]
fn offline_update_requires_local_action_trusted_signature_target_and_new_version() {
    let key = SigningKey::from_bytes(&[8; 32]);
    let other = SigningKey::from_bytes(&[9; 32]);
    let policy = BootPolicy::new(7, key.verifying_key().to_bytes()).unwrap();
    let mut flash = Flash::new();
    let mut floor = VersionFloor::default();
    let image = fixture_image(&[3; 1024], 7, 1, &key);
    assert!(
        policy
            .install_local_sd(&image, false, &mut flash, &mut floor)
            .is_err()
    );
    assert!(policy.boot(&flash, &mut floor).is_err());
    for bad in [
        fixture_image(&[3; 1024], 8, 1, &key),
        fixture_image(&[3; 1024], 7, 1, &other),
    ] {
        assert!(
            policy
                .install_local_sd(&bad, true, &mut flash, &mut floor)
                .is_err()
        );
    }
    let mut bad = image.clone();
    bad[HEADER + 1] ^= 1;
    assert!(policy.verify_envelope(&bad).is_err());
    assert_eq!(
        policy
            .install_local_sd(&image, true, &mut flash, &mut floor)
            .unwrap()
            .version,
        1
    );
    assert!(
        policy
            .install_local_sd(&image, true, &mut flash, &mut floor)
            .is_err()
    );
    let v2 = fixture_image(&[4; 1536], 7, 2, &key);
    assert_eq!(
        policy
            .install_local_sd(&v2, true, &mut flash, &mut floor)
            .unwrap()
            .version,
        2
    );
    assert!(
        policy
            .install_local_sd(&image, true, &mut flash, &mut floor)
            .is_err()
    );
    floor.set_unavailable(true);
    assert!(policy.boot(&flash, &mut floor).is_err());
}

#[test]
fn every_update_write_cut_and_torn_write_boots_only_verified_nonrollback_image() {
    let key = SigningKey::from_bytes(&[8; 32]);
    let policy = BootPolicy::new(7, key.verifying_key().to_bytes()).unwrap();
    let v1 = fixture_image(&[3; 1024], 7, 1, &key);
    let v2 = fixture_image(&[5; 2300], 7, 2, &key);
    let mut original = Flash::new();
    let mut floor = VersionFloor::default();
    policy
        .install_local_sd(&v1, true, &mut original, &mut floor)
        .unwrap();
    for cut in 0..9 {
        for torn in [false, true] {
            let mut flash = original.clone();
            let mut floor = VersionFloor::default();
            floor.advance(1).unwrap();
            flash.remaining = Some(cut);
            flash.torn = torn;
            let _ = policy.install_local_sd(&v2, true, &mut flash, &mut floor);
            flash.remaining = None;
            let boot = policy.boot(&flash, &mut floor).unwrap();
            assert!(boot.version == 1 || boot.version == 2);
            assert!(boot.version >= floor.current().unwrap());
            assert_eq!(
                boot.hash,
                if boot.version == 1 {
                    policy.verify_envelope(&v1).unwrap().hash
                } else {
                    policy.verify_envelope(&v2).unwrap().hash
                }
            );
        }
    }
}

#[test]
fn controller_has_no_privileged_opcode_and_cannot_bypass_bounds_by_reset() {
    use protocol::radio::*;
    let mut port = RadioPort::default();
    for opcode in 0u8..=255 {
        let mut wire = [0; 8];
        wire[0] = opcode;
        wire[1] = 6;
        assert_eq!(port.receive(&wire, u64::from(opcode)).is_ok(), opcode == 1);
    }
    let mut wire = [0; 40];
    wire[0] = 1;
    wire[1] = 38;
    for _ in 0..1000 {
        let _ = port.receive(&wire, 300);
    }
    assert!(port.depth() <= QUEUE);
    assert_eq!(port.peak, QUEUE);
    assert!(port.pop(303).is_none());
    port.controller_reset();
    assert!(matches!(port.receive(&wire, 300), Err(PolicyError::Busy)));
    port.local_update_mode(true);
    assert!(port.receive(&wire, 400).is_err());
    port.controller_reset();
    assert!(port.receive(&wire, 401).is_err());
    port.local_update_mode(false);
    assert!(port.receive(&wire, 402).is_ok());
    assert!(port.receive(&wire, 401).is_err());
}

#[test]
fn storage_failure_never_releases_an_invitation_or_consumes_a_received_counter() {
    let (a, b, mut ea, mut eb) = identities();
    let (mut ab, mut ba) = books(&a, &b, &mut ea, &mut eb);
    let mut ar = StorageRoot::new(&mut ea).unwrap();
    let mut br = StorageRoot::new(&mut eb).unwrap();
    ar.set_unavailable(true);
    assert!(
        Invitation::issue(
            &a,
            &mut ab,
            &id(&b),
            [9; 16],
            &Clock(50),
            Kind::Offer,
            None,
            &mut ea,
            &mut ar
        )
        .is_err()
    );
    assert_eq!(ar.generation(), 0);
    ar.set_unavailable(false);
    let (offer, _) = Invitation::issue(
        &a,
        &mut ab,
        &id(&b),
        [9; 16],
        &Clock(50),
        Kind::Offer,
        None,
        &mut ea,
        &mut ar,
    )
    .unwrap();
    br.set_unavailable(true);
    assert!(
        offer
            .verify(
                &b,
                &mut ba,
                &id(&a),
                &[9; 16],
                &Clock(50),
                &mut Admission::default(),
                &mut br
            )
            .is_err()
    );
    assert_eq!(br.generation(), 0);
    br.set_unavailable(false);
    assert!(
        offer
            .verify(
                &b,
                &mut ba,
                &id(&a),
                &[9; 16],
                &Clock(50),
                &mut Admission::default(),
                &mut br
            )
            .is_ok()
    );
    // The signed recipient is part of the invitation, not supplied by a relay.
    let c = Identity::new(&mut eb).unwrap();
    let mut ca = ContactBook::new(id(&c));
    ca.install(
        EnrolledContact::verified_oob(a.contact(), &id(&a), true).unwrap(),
        "Alice",
    )
    .unwrap();
    let mut cr = StorageRoot::new(&mut eb).unwrap();
    assert!(
        offer
            .verify(
                &c,
                &mut ca,
                &id(&a),
                &[9; 16],
                &Clock(50),
                &mut Admission::default(),
                &mut cr
            )
            .is_err()
    );
    assert_eq!(cr.generation(), 0);
}

#[test]
fn corrupted_new_firmware_never_falls_back_below_the_protected_floor() {
    let key = SigningKey::from_bytes(&[8; 32]);
    let policy = BootPolicy::new(7, key.verifying_key().to_bytes()).unwrap();
    let mut flash = Flash::new();
    let mut floor = VersionFloor::default();
    policy
        .install_local_sd(
            &fixture_image(&[3; 1024], 7, 1, &key),
            true,
            &mut flash,
            &mut floor,
        )
        .unwrap();
    let active = policy
        .install_local_sd(
            &fixture_image(&[4; 1024], 7, 2, &key),
            true,
            &mut flash,
            &mut floor,
        )
        .unwrap();
    flash.banks[active.bank][HEADER + 3] ^= 1;
    assert!(policy.boot(&flash, &mut floor).is_err());
    assert_eq!(floor.current().unwrap(), 2);
}

#[test]
fn a_closed_session_rejects_even_authentic_future_packets() {
    let (mut a, mut b) = fixtures::sessions(88).unwrap();
    fixtures::activate(&mut a, &mut b).unwrap();
    let good = a.media(0, Media::Filler).unwrap();
    b.close();
    b.consent();
    assert!(!b.active());
    assert!(b.receive(&good, 0..8).is_err());
    assert!(b.control(call_state::Control::Confirm).is_err());
}

#[test]
fn protected_commit_or_flash_read_failure_never_erases_an_unrecognized_active_bank() {
    let key = SigningKey::from_bytes(&[8; 32]);
    let policy = BootPolicy::new(7, key.verifying_key().to_bytes()).unwrap();
    let v1 = fixture_image(&[3; 1024], 7, 1, &key);
    let v2 = fixture_image(&[4; 1024], 7, 2, &key);
    let mut flash = Flash::new();
    flash.banks[0][..v1.len()].copy_from_slice(&v1);
    struct FailedCommit;
    impl ProtectedVersion for FailedCommit {
        fn current(&self) -> PolicyResult<u64> {
            Ok(0)
        }
        fn advance(&mut self, _version: u64) -> PolicyResult<()> {
            Err(PolicyError::Storage)
        }
    }
    let before = flash.banks.clone();
    assert!(matches!(
        policy.install_local_sd(&v2, true, &mut flash, &mut FailedCommit),
        Err(PolicyError::Storage)
    ));
    assert_eq!(flash.banks, before);
    struct FailedRead(Flash);
    impl FlashBanks for FailedRead {
        fn capacity(&self) -> usize {
            self.0.capacity()
        }
        fn read(&self, _b: usize, _o: usize, _out: &mut [u8]) -> PolicyResult<()> {
            Err(PolicyError::Storage)
        }
        fn erase(&mut self, _b: usize) -> PolicyResult<()> {
            panic!("erase after failed active-bank read")
        }
        fn write(&mut self, _b: usize, _o: usize, _x: &[u8]) -> PolicyResult<()> {
            panic!("write after failed active-bank read")
        }
    }
    let mut broken = FailedRead(flash);
    let mut floor = VersionFloor::default();
    assert!(matches!(
        policy.install_local_sd(&v2, true, &mut broken, &mut floor),
        Err(PolicyError::Storage)
    ));
    assert_eq!(floor.current().unwrap(), 0);
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]
    #[test]
    fn arbitrary_radio_frames_cannot_exceed_capacity(frames in prop::collection::vec(prop::collection::vec(any::<u8>(),0..200),0..120)){
        let mut port=protocol::radio::RadioPort::default();
        for (i,frame) in frames.iter().enumerate(){let _=port.receive(frame,(i/10)as u64);prop_assert!(port.depth()<=protocol::radio::QUEUE);}
    }
    #[test]
    fn arbitrary_firmware_envelopes_do_not_pass_signature(bytes in prop::collection::vec(any::<u8>(),0..4096)){
        let key=SigningKey::from_bytes(&[8;32]);let policy=BootPolicy::new(7,key.verifying_key().to_bytes()).unwrap();
        prop_assert!(policy.verify_envelope(&bytes).is_err());
    }
}
