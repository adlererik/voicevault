//! Fixed-capacity, locally enrolled contacts. Sealed snapshots are bound to a
//! protected monotonic generation. StorageRoot models a secure-element boundary;
//! it is not an implementation of a particular chip or physical tamper defense.
use crate::{
    CONTACT, Entropy, Pin, PolicyError as E, PolicyResult as R, enrollment::EnrolledContact,
};
use chacha20poly1305::{ChaCha20Poly1305, KeyInit, aead::AeadInPlace};
use zeroize::Zeroizing;

pub const CONTACT_SLOTS: usize = 8;
pub const ALIAS_BYTES: usize = 32;
const ENTRY_BYTES: usize = 179;
const BOOK_BYTES: usize = 32 + CONTACT_SLOTS * ENTRY_BYTES;
pub const SNAPSHOT_BYTES: usize = 8 + BOOK_BYTES + 16;

pub struct StorageRoot {
    key: Zeroizing<[u8; 32]>,
    generation: u64,
    unavailable: bool,
}
impl StorageRoot {
    pub fn new(entropy: &mut impl Entropy) -> R<Self> {
        Ok(Self {
            key: Zeroizing::new(entropy.seed().map_err(|_| E::Entropy)?),
            generation: 0,
            unavailable: false,
        })
    }
    pub fn generation(&self) -> u64 {
        self.generation
    }
    /// Fault injection belongs to the simulator's trusted harness, never radio ingress.
    pub fn set_unavailable(&mut self, unavailable: bool) {
        self.unavailable = unavailable;
    }
}
#[derive(Clone, Copy)]
pub(crate) struct Entry {
    pub record: [u8; CONTACT],
    pub alias: [u8; ALIAS_BYTES],
    pub alias_len: u8,
    pub revoked: bool,
    pub received: u64,
    pub sent: u64,
}
pub struct ContactBook {
    pub(crate) owner: [u8; 32],
    pub(crate) entries: [Option<Entry>; CONTACT_SLOTS],
}
impl ContactBook {
    pub fn new(owner: [u8; 32]) -> Self {
        Self {
            owner,
            entries: [None; CONTACT_SLOTS],
        }
    }
    pub fn install(&mut self, contact: EnrolledContact, alias: &str) -> R<()> {
        if alias.is_empty()
            || alias.len() > ALIAS_BYTES
            || !alias.bytes().all(|c| c.is_ascii_graphic() || c == b' ')
        {
            return Err(E::Invalid);
        }
        let id: [u8; 32] = contact.record[..32].try_into().map_err(|_| E::Invalid)?;
        if id == self.owner {
            return Err(E::Identity);
        }
        let pos = self
            .entries
            .iter()
            .position(|e| e.is_some_and(|e| e.record[..32] == id))
            .or_else(|| self.entries.iter().position(Option::is_none))
            .ok_or(E::Full)?;
        let old = self.entries[pos];
        let mut name = [0; ALIAS_BYTES];
        name[..alias.len()].copy_from_slice(alias.as_bytes());
        self.entries[pos] = Some(Entry {
            record: contact.record,
            alias: name,
            alias_len: alias.len() as u8,
            revoked: false,
            received: old.map_or(0, |e| e.received),
            sent: old.map_or(0, |e| e.sent),
        });
        Ok(())
    }
    pub(crate) fn index(&self, id: &[u8; 32]) -> R<usize> {
        self.entries
            .iter()
            .position(|e| e.is_some_and(|e| !e.revoked && e.record[..32] == *id))
            .ok_or(E::Identity)
    }
    pub fn pin(&self, id: &[u8; 32]) -> R<Pin> {
        let e = self.entries[self.index(id)?].ok_or(E::Identity)?;
        Pin::verify(&e.record, id).map_err(|_| E::Identity)
    }
    pub fn revoke(&mut self, id: &[u8; 32]) -> R<()> {
        let i = self.index(id)?;
        self.entries[i].as_mut().ok_or(E::Identity)?.revoked = true;
        Ok(())
    }
    pub fn persist(&self, root: &mut StorageRoot) -> R<[u8; SNAPSHOT_BYTES]> {
        if root.unavailable {
            return Err(E::Storage);
        }
        let generation = root
            .generation
            .checked_add(1)
            .filter(|&x| x != u64::MAX)
            .ok_or(E::Counter)?;
        let mut out = [0; SNAPSHOT_BYTES];
        out[..8].copy_from_slice(&generation.to_le_bytes());
        let body = &mut out[8..8 + BOOK_BYTES];
        body[..32].copy_from_slice(&self.owner);
        for (slot, e) in body[32..]
            .as_chunks_mut::<ENTRY_BYTES>()
            .0
            .iter_mut()
            .zip(self.entries)
        {
            if let Some(e) = e {
                slot[0] = 1;
                slot[1..129].copy_from_slice(&e.record);
                slot[129] = e.alias_len;
                slot[130..162].copy_from_slice(&e.alias);
                slot[162] = u8::from(e.revoked);
                slot[163..171].copy_from_slice(&e.received.to_le_bytes());
                slot[171..179].copy_from_slice(&e.sent.to_le_bytes());
            }
        }
        let mut nonce = [0; 12];
        nonce[4..].copy_from_slice(&generation.to_le_bytes());
        let cipher = ChaCha20Poly1305::new(root.key.as_ref().into());
        let tag = cipher
            .encrypt_in_place_detached((&nonce).into(), b"quietlink contacts v1", body)
            .map_err(|_| E::Storage)?;
        out[8 + BOOK_BYTES..].copy_from_slice(&tag);
        // Generation advancement precedes release. Losing the new snapshot fails
        // closed on restore; old ciphertext cannot silently roll contacts back.
        root.generation = generation;
        Ok(out)
    }
    pub fn restore(bytes: &[u8], root: &StorageRoot, owner: [u8; 32]) -> R<Self> {
        if root.unavailable {
            return Err(E::Storage);
        }
        if bytes.len() != SNAPSHOT_BYTES {
            return Err(E::Invalid);
        }
        let generation = u64::from_le_bytes(bytes[..8].try_into().map_err(|_| E::Invalid)?);
        if generation == 0 || generation != root.generation {
            return Err(E::Rollback);
        }
        let mut body = Zeroizing::new([0; BOOK_BYTES]);
        body.copy_from_slice(&bytes[8..8 + BOOK_BYTES]);
        let mut nonce = [0; 12];
        nonce[4..].copy_from_slice(&generation.to_le_bytes());
        ChaCha20Poly1305::new(root.key.as_ref().into())
            .decrypt_in_place_detached(
                (&nonce).into(),
                b"quietlink contacts v1",
                &mut body[..],
                bytes[8 + BOOK_BYTES..].into(),
            )
            .map_err(|_| E::Storage)?;
        if body[..32] != owner {
            return Err(E::Identity);
        }
        let mut book = Self::new(owner);
        for (slot, entry) in body[32..]
            .as_chunks::<ENTRY_BYTES>()
            .0
            .iter()
            .zip(&mut book.entries)
        {
            if slot[0] == 0 {
                if slot.iter().any(|&b| b != 0) {
                    return Err(E::Invalid);
                }
                continue;
            }
            if slot[0] != 1
                || slot[129] == 0
                || usize::from(slot[129]) > ALIAS_BYTES
                || slot[162] > 1
            {
                return Err(E::Invalid);
            }
            let record: [u8; CONTACT] = slot[1..129].try_into().map_err(|_| E::Invalid)?;
            let id: [u8; 32] = record[..32].try_into().map_err(|_| E::Invalid)?;
            Pin::verify(&record, &id).map_err(|_| E::Identity)?;
            if id == owner {
                return Err(E::Identity);
            }
            let alias: [u8; ALIAS_BYTES] = slot[130..162].try_into().map_err(|_| E::Invalid)?;
            let n = usize::from(slot[129]);
            if !alias[..n]
                .iter()
                .all(|b| b.is_ascii_graphic() || *b == b' ')
                || alias[n..].iter().any(|&x| x != 0)
            {
                return Err(E::Invalid);
            }
            *entry = Some(Entry {
                record,
                alias,
                alias_len: slot[129],
                revoked: slot[162] == 1,
                received: u64::from_le_bytes(slot[163..171].try_into().map_err(|_| E::Invalid)?),
                sent: u64::from_le_bytes(slot[171..179].try_into().map_err(|_| E::Invalid)?),
            });
        }
        for (i, e) in book.entries.iter().enumerate() {
            if let Some(e) = e
                && book.entries[..i]
                    .iter()
                    .flatten()
                    .any(|p| p.record[..32] == e.record[..32])
            {
                return Err(E::Invalid);
            }
        }
        Ok(book)
    }
}
