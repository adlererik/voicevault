//! Relay-independent, bounded signed invitations. Phone time is never authoritative.
use crate::{
    CONTACT, Entropy, Identity, PolicyError as E, PolicyResult as R,
    contacts::{ContactBook, SNAPSHOT_BYTES, StorageRoot},
};
use blake2::{Blake2s256, Digest};
use ed25519_dalek::{Signature, Signer, VerifyingKey};

pub const INVITATION_BYTES: usize = 128;
pub const MAX_TTL: u64 = 60;
pub trait TrustedClock {
    fn seconds(&self) -> u64;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Offer = 1,
    Accept = 2,
}
#[derive(Clone, Copy)]
pub struct Invitation([u8; INVITATION_BYTES]);
pub struct VerifiedInvitation {
    source: [u8; 32],
    nonce: [u8; 16],
    kind: Kind,
    alias: [u8; 32],
    alias_len: u8,
    wire: [u8; INVITATION_BYTES],
}
impl VerifiedInvitation {
    pub fn source(&self) -> [u8; 32] {
        self.source
    }
    pub fn call_nonce(&self) -> [u8; 16] {
        self.nonce
    }
    pub fn kind(&self) -> Kind {
        self.kind
    }
    pub fn trusted_name(&self) -> &str {
        core::str::from_utf8(&self.alias[..usize::from(self.alias_len)]).unwrap_or("")
    }
}
#[derive(Default)]
pub struct Admission {
    last: u64,
    window: u64,
    used: u8,
}
impl Admission {
    fn allow(&mut self, clock: &impl TrustedClock) -> R<u64> {
        let now = clock.seconds();
        if now < self.last {
            return Err(E::Clock);
        }
        self.last = now;
        if now != self.window {
            self.window = now;
            self.used = 0;
        }
        if self.used >= 8 {
            return Err(E::Busy);
        }
        self.used += 1;
        Ok(now)
    }
}
fn message(header: &[u8], sender: &[u8; CONTACT], recipient: &[u8; CONTACT]) -> [u8; 32] {
    let mut h = Blake2s256::new();
    h.update(b"quietlink invitation v1");
    h.update(header);
    h.update(&sender[..64]);
    h.update(&recipient[..64]);
    h.finalize().into()
}
impl Invitation {
    pub fn parse(wire: &[u8]) -> R<Self> {
        let out: [u8; INVITATION_BYTES] = wire.try_into().map_err(|_| E::Invalid)?;
        if out[0] != 1 || !matches!(out[1], 1 | 2) || out[2..8].iter().any(|&b| b != 0) {
            return Err(E::Invalid);
        }
        Ok(Self(out))
    }
    pub fn as_bytes(&self) -> &[u8; INVITATION_BYTES] {
        &self.0
    }
    // Explicit authorities stay separate at this policy boundary.
    #[allow(clippy::too_many_arguments)]
    pub fn issue(
        identity: &Identity,
        book: &mut ContactBook,
        peer: &[u8; 32],
        challenge: [u8; 16],
        clock: &impl TrustedClock,
        kind: Kind,
        reply_nonce: Option<[u8; 16]>,
        entropy: &mut impl Entropy,
        root: &mut StorageRoot,
    ) -> R<(Self, [u8; SNAPSHOT_BYTES])> {
        let local = identity.contact();
        if book.owner != local[..32] {
            return Err(E::Identity);
        }
        let i = book.index(peer)?;
        let old = book.entries[i].ok_or(E::Identity)?;
        let counter = old
            .sent
            .checked_add(1)
            .filter(|&n| n != u64::MAX)
            .ok_or(E::Counter)?;
        let now = clock.seconds();
        let expires = now.checked_add(MAX_TTL).ok_or(E::Clock)?;
        let nonce = match (kind, reply_nonce) {
            (Kind::Offer, None) => entropy.seed().map_err(|_| E::Entropy)?[..16]
                .try_into()
                .map_err(|_| E::Entropy)?,
            (Kind::Accept, Some(n)) => n,
            _ => return Err(E::State),
        };
        if nonce == [0; 16] || challenge == [0; 16] {
            return Err(E::Entropy);
        }
        let mut wire = [0; INVITATION_BYTES];
        wire[0] = 1;
        wire[1] = kind as u8;
        wire[8..16].copy_from_slice(&counter.to_le_bytes());
        wire[16..24].copy_from_slice(&now.to_le_bytes());
        wire[24..32].copy_from_slice(&expires.to_le_bytes());
        wire[32..48].copy_from_slice(&challenge);
        wire[48..64].copy_from_slice(&nonce);
        let sig = identity
            .signing
            .sign(&message(&wire[..64], &local, &old.record));
        wire[64..].copy_from_slice(&sig.to_bytes());
        book.entries[i].as_mut().ok_or(E::Identity)?.sent = counter;
        match book.persist(root) {
            Ok(snapshot) => Ok((Self(wire), snapshot)),
            Err(e) => {
                book.entries[i] = Some(old);
                Err(e)
            }
        }
    }
    #[allow(clippy::too_many_arguments)]
    pub fn verify(
        &self,
        identity: &Identity,
        book: &mut ContactBook,
        peer: &[u8; 32],
        challenge: &[u8; 16],
        clock: &impl TrustedClock,
        admission: &mut Admission,
        root: &mut StorageRoot,
    ) -> R<(VerifiedInvitation, [u8; SNAPSHOT_BYTES])> {
        let now = admission.allow(clock)?;
        Self::parse(&self.0)?;
        let local = identity.contact();
        if book.owner != local[..32] {
            return Err(E::Identity);
        }
        let i = book.index(peer)?;
        let old = book.entries[i].ok_or(E::Identity)?;
        let signer = VerifyingKey::from_bytes(peer).map_err(|_| E::Identity)?;
        let sig = Signature::from_bytes(self.0[64..].try_into().map_err(|_| E::Invalid)?);
        signer
            .verify_strict(&message(&self.0[..64], &old.record, &local), &sig)
            .map_err(|_| E::Signature)?;
        let number = |a, b| u64::from_le_bytes(self.0[a..b].try_into().unwrap_or([0; 8]));
        let counter = number(8, 16);
        let issued = number(16, 24);
        let expires = number(24, 32);
        if issued > now || expires < now || expires < issued || expires - issued > MAX_TTL {
            return Err(E::Expired);
        }
        if *challenge == [0; 16] || self.0[32..48] != *challenge || self.0[48..64] == [0; 16] {
            return Err(E::Replay);
        }
        if counter == 0 || counter == u64::MAX || counter <= old.received {
            return Err(E::Replay);
        }
        book.entries[i].as_mut().ok_or(E::Identity)?.received = counter;
        let snapshot = match book.persist(root) {
            Ok(s) => s,
            Err(e) => {
                book.entries[i] = Some(old);
                return Err(e);
            }
        };
        let nonce = self.0[48..64].try_into().map_err(|_| E::Invalid)?;
        Ok((
            VerifiedInvitation {
                source: *peer,
                nonce,
                kind: if self.0[1] == 1 {
                    Kind::Offer
                } else {
                    Kind::Accept
                },
                alias: old.alias,
                alias_len: old.alias_len,
                wire: self.0,
            },
            snapshot,
        ))
    }
}
/// Requires a private verified-invitation token and rechecks the local signature.
/// Parsed untrusted bytes alone cannot authorize a call-context construction.
pub fn call_context(
    local: &Identity,
    book: &ContactBook,
    issued: &Invitation,
    received: &VerifiedInvitation,
) -> R<[u8; 32]> {
    let me = local.contact();
    if book.owner != me[..32] {
        return Err(E::Identity);
    }
    let peer = book.entries[book.index(&received.source)?].ok_or(E::Identity)?;
    let sig = Signature::from_bytes(issued.0[64..].try_into().map_err(|_| E::Invalid)?);
    local
        .signing
        .verifying_key()
        .verify_strict(&message(&issued.0[..64], &me, &peer.record), &sig)
        .map_err(|_| E::Signature)?;
    let (offer, accept) = if issued.0[1] == Kind::Offer as u8 {
        (&issued.0, &received.wire)
    } else {
        (&received.wire, &issued.0)
    };
    if offer[1] != Kind::Offer as u8
        || accept[1] != Kind::Accept as u8
        || offer[48..64] != accept[48..64]
    {
        return Err(E::State);
    }
    let mut h = Blake2s256::new();
    h.update(b"quietlink accepted call v1");
    h.update(offer);
    h.update(accept);
    Ok(h.finalize().into())
}
