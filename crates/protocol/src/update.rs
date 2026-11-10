//! A software model of an immutable verifier + two raw-image banks and a protected
//! security-version floor. No USB/BLE updater, filesystem, or OpenPGP parser.
use crate::{PolicyError as E, PolicyResult as R};
use blake2::{Blake2s256, Digest};
use ed25519_dalek::{Signature, VerifyingKey};

pub const HEADER: usize = 128;
pub const MAX_IMAGE: usize = 2 * 1024 * 1024;
pub const CHUNK: usize = 512;
const MAGIC: &[u8; 8] = b"QLFWv001";
const DOMAIN: &[u8] = b"quietlink firmware v1";

pub trait FlashBanks {
    fn capacity(&self) -> usize;
    fn read(&self, bank: usize, offset: usize, out: &mut [u8]) -> R<()>;
    fn erase(&mut self, bank: usize) -> R<()>;
    fn write(&mut self, bank: usize, offset: usize, bytes: &[u8]) -> R<()>;
}
pub trait ProtectedVersion {
    fn current(&self) -> R<u64>;
    fn advance(&mut self, version: u64) -> R<()>;
}
#[derive(Default)]
pub struct VersionFloor {
    floor: call_state::SecurityCounter,
    unavailable: bool,
}
impl VersionFloor {
    pub fn set_unavailable(&mut self, failed: bool) {
        self.unavailable = failed;
    }
}
impl ProtectedVersion for VersionFloor {
    fn current(&self) -> R<u64> {
        if self.unavailable {
            Err(E::Storage)
        } else {
            Ok(self.floor.value())
        }
    }
    fn advance(&mut self, v: u64) -> R<()> {
        if self.unavailable {
            return Err(E::Storage);
        }
        if v == self.floor.value() {
            return Ok(());
        }
        if self.floor.advance(v) {
            Ok(())
        } else {
            Err(E::Rollback)
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BootImage {
    pub bank: usize,
    pub version: u64,
    pub payload_bytes: usize,
    pub hash: [u8; 32],
}
pub struct BootPolicy {
    target: u32,
    release_key: VerifyingKey,
}
impl BootPolicy {
    pub fn new(target: u32, release_public_key: [u8; 32]) -> R<Self> {
        Ok(Self {
            target,
            release_key: VerifyingKey::from_bytes(&release_public_key).map_err(|_| E::Signature)?,
        })
    }
    fn header(&self, h: &[u8; HEADER]) -> R<(u64, usize, [u8; 32])> {
        if &h[..8] != MAGIC || h[12..16] != [0; 4] {
            return Err(E::Invalid);
        }
        if u32::from_le_bytes(h[8..12].try_into().map_err(|_| E::Invalid)?) != self.target {
            return Err(E::Target);
        }
        let version = u64::from_le_bytes(h[16..24].try_into().map_err(|_| E::Invalid)?);
        let len = u64::from_le_bytes(h[24..32].try_into().map_err(|_| E::Invalid)?);
        if version == 0 || version == u64::MAX || len == 0 || len > MAX_IMAGE as u64 {
            return Err(E::Invalid);
        }
        let sig = Signature::from_bytes(h[64..128].try_into().map_err(|_| E::Invalid)?);
        let mut digest = Blake2s256::new();
        digest.update(DOMAIN);
        digest.update(&h[..64]);
        self.release_key
            .verify_strict(&digest.finalize(), &sig)
            .map_err(|_| E::Signature)?;
        Ok((
            version,
            len as usize,
            h[32..64].try_into().map_err(|_| E::Invalid)?,
        ))
    }
    pub fn verify_envelope(&self, wire: &[u8]) -> R<BootImage> {
        let header: &[u8; HEADER] = wire
            .get(..HEADER)
            .ok_or(E::Invalid)?
            .try_into()
            .map_err(|_| E::Invalid)?;
        let (version, len, hash) = self.header(header)?;
        if wire.len() != HEADER + len
            || <[u8; 32]>::from(Blake2s256::digest(&wire[HEADER..])) != hash
        {
            return Err(E::Invalid);
        }
        Ok(BootImage {
            bank: 0,
            version,
            payload_bytes: len,
            hash,
        })
    }
    fn verify_bank(&self, flash: &impl FlashBanks, bank: usize) -> R<BootImage> {
        let mut header = [0; HEADER];
        flash.read(bank, 0, &mut header)?;
        let (version, len, hash) = self.header(&header)?;
        if HEADER + len > flash.capacity() {
            return Err(E::Invalid);
        }
        let mut offset = 0;
        let mut buf = [0; CHUNK];
        let mut digest = Blake2s256::new();
        while offset < len {
            let n = CHUNK.min(len - offset);
            flash.read(bank, HEADER + offset, &mut buf[..n])?;
            digest.update(&buf[..n]);
            offset += n;
        }
        if <[u8; 32]>::from(digest.finalize()) != hash {
            return Err(E::Invalid);
        }
        Ok(BootImage {
            bank,
            version,
            payload_bytes: len,
            hash,
        })
    }
    pub fn boot(&self, flash: &impl FlashBanks, floor: &mut impl ProtectedVersion) -> R<BootImage> {
        let minimum = floor.current()?;
        let mut best: Option<BootImage> = None;
        for bank in 0..2 {
            match self.verify_bank(flash, bank) {
                Ok(image)
                    if image.version >= minimum
                        && best.is_none_or(|old| image.version >= old.version) =>
                {
                    best = Some(image)
                }
                // A device read failure is not evidence of an invalid/empty bank.
                // Propagate it so installation cannot erase an unrecognized active bank.
                Err(E::Storage) => return Err(E::Storage),
                _ => {}
            }
        }
        let best = best.ok_or(E::Rollback)?;
        // Completing this advancement also recovers a power loss between writing
        // a fully verified new bank and committing its protected version.
        floor.advance(best.version)?;
        Ok(best)
    }
    pub fn install_local_sd(
        &self,
        wire: &[u8],
        physical_approval: bool,
        flash: &mut impl FlashBanks,
        floor: &mut impl ProtectedVersion,
    ) -> R<BootImage> {
        if !physical_approval {
            return Err(E::LocalApproval);
        }
        let candidate = self.verify_envelope(wire)?;
        let minimum = floor.current()?;
        if candidate.version <= minimum {
            return Err(E::Rollback);
        }
        if wire.len() > flash.capacity() {
            return Err(E::Full);
        }
        let active = match self.boot(flash, floor) {
            Ok(image) => Some(image),
            Err(E::Rollback) if minimum == 0 => None,
            Err(e) => return Err(e),
        };
        if candidate.version <= floor.current()? {
            return Err(E::Rollback);
        }
        let bank = active.map_or(0, |image| 1 - image.bank);
        flash.erase(bank)?;
        // Header is written last. A torn payload cannot become a valid candidate.
        for (i, chunk) in wire[HEADER..].chunks(CHUNK).enumerate() {
            flash.write(bank, HEADER + i * CHUNK, chunk)?;
        }
        flash.write(bank, 0, &wire[..HEADER])?;
        let verified = self.verify_bank(flash, bank)?;
        if verified.version != candidate.version || verified.hash != candidate.hash {
            return Err(E::Invalid);
        }
        floor.advance(verified.version)?;
        Ok(verified)
    }
}

/// Release signing is confined to fixtures/tools, never linked into production policy.
#[cfg(feature = "fixtures")]
pub fn fixture_image(
    payload: &[u8],
    target: u32,
    version: u64,
    signer: &ed25519_dalek::SigningKey,
) -> alloc::vec::Vec<u8> {
    use ed25519_dalek::Signer;
    let mut wire = alloc::vec![0;HEADER+payload.len()];
    wire[..8].copy_from_slice(MAGIC);
    wire[8..12].copy_from_slice(&target.to_le_bytes());
    wire[16..24].copy_from_slice(&version.to_le_bytes());
    wire[24..32].copy_from_slice(&(payload.len() as u64).to_le_bytes());
    wire[32..64].copy_from_slice(&Blake2s256::digest(payload));
    let mut digest = Blake2s256::new();
    digest.update(DOMAIN);
    digest.update(&wire[..64]);
    wire[64..128].copy_from_slice(&signer.sign(&digest.finalize()).to_bytes());
    wire[HEADER..].copy_from_slice(payload);
    wire
}
