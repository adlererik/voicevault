#![cfg_attr(not(feature = "std"), no_std)]
#![forbid(unsafe_code)]

extern crate alloc;
pub mod contacts;
pub mod enrollment;
pub mod entropy;
pub mod invitation;
mod kem;
pub mod radio;
mod randomness;
pub mod update;

use call_state::{CallState, Control, FIRST_MEDIA, HandshakeGate, Replay};
use curve25519_dalek::montgomery::MontgomeryPoint;
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use snow::{Builder, HandshakeState, StatelessTransportState};
use zeroize::Zeroizing;

pub const PATTERN: &str = "Noise_KKhfs_25519+MLKEM768_ChaChaPoly_BLAKE2s";
const DOMAIN: &[u8; 24] = b"quietlink contact v1 edx";
const PROLOGUE: &[u8] = b"VoiceVault hybrid call v2";
pub const HANDSHAKE_FIRST: usize = 1248;
pub const HANDSHAKE_SECOND: usize = 1152;
pub const HANDSHAKE: usize = HANDSHAKE_FIRST;
pub const CONTACT: usize = 128;
pub const RECORD: usize = 128;
pub const PAYLOAD: usize = 102;
/// A transport key is never used beyond five minutes of active slots.
pub const MAX_EPOCH_SLOTS: u64 = 15_000;
const PLAIN: usize = RECORD - 8 - 16;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PolicyError {
    Invalid,
    State,
    Signature,
    Identity,
    LocalApproval,
    Storage,
    Rollback,
    Entropy,
    Expired,
    Replay,
    Busy,
    Unsupported,
    Counter,
    Target,
    Full,
    Clock,
}
impl core::fmt::Display for PolicyError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{self:?}")
    }
}
impl core::error::Error for PolicyError {}
pub type PolicyResult<T> = Result<T, PolicyError>;

#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    Entropy,
    Contact,
    Handshake,
    Auth,
    Size,
    Replay,
    Counter,
    State,
    Command,
    Expired,
}

impl core::fmt::Display for Error {
    fn fmt(&self, formatter: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(formatter, "{self:?}")
    }
}
impl core::error::Error for Error {}

pub trait Entropy {
    fn seed(&mut self) -> Result<[u8; 32], Error>;
}

#[cfg(feature = "std")]
pub struct OsEntropy;
#[cfg(feature = "std")]
impl Entropy for OsEntropy {
    fn seed(&mut self) -> Result<[u8; 32], Error> {
        let mut seed = [0; 32];
        getrandom::fill(&mut seed).map_err(|_| Error::Entropy)?;
        Ok(seed)
    }
}

pub struct Identity {
    signing: SigningKey,
    static_secret: Zeroizing<[u8; 32]>,
}

fn signed_message(fields: &[u8]) -> [u8; 88] {
    let mut message = [0; 88];
    message[..24].copy_from_slice(DOMAIN);
    message[24..].copy_from_slice(fields);
    message
}

impl Identity {
    pub fn new(entropy: &mut impl Entropy) -> Result<Self, Error> {
        let signing = SigningKey::from_bytes(&Zeroizing::new(entropy.seed()?));
        Ok(Self {
            signing,
            static_secret: Zeroizing::new(entropy.seed()?),
        })
    }

    pub fn contact(&self) -> [u8; CONTACT] {
        let mut out = [0; CONTACT];
        out[..32].copy_from_slice(self.signing.verifying_key().as_bytes());
        out[32..64]
            .copy_from_slice(MontgomeryPoint::mul_base_clamped(*self.static_secret).as_bytes());
        let signature = self.signing.sign(&signed_message(&out[..64]));
        out[64..].copy_from_slice(&signature.to_bytes());
        out
    }

    #[cfg(feature = "std")]
    pub fn handshake(&self, peer: &Pin, initiator: bool) -> Result<Handshake, Error> {
        self.handshake_with_entropy(peer, initiator, &mut OsEntropy, None)
    }

    pub fn handshake_with_entropy(
        &self,
        peer: &Pin,
        initiator: bool,
        entropy: &mut impl Entropy,
        context: Option<&[u8; 32]>,
    ) -> Result<Handshake, Error> {
        // Acquire all entropy fallibly before constructing a Noise state. The
        // KEM seed is independent of the classical ephemeral and encapsulation.
        let noise = Zeroizing::new(entropy.seed()?);
        let mut key = Zeroizing::new([0; 64]);
        key[..32].copy_from_slice(&Zeroizing::new(entropy.seed()?)[..]);
        key[32..].copy_from_slice(&Zeroizing::new(entropy.seed()?)[..]);
        let enc = Zeroizing::new(entropy.seed()?);
        self.build(
            peer,
            initiator,
            randomness::SeedResolver::hybrid(*noise, key, enc),
            context,
            None,
        )
    }

    /// Public deterministic lab fixtures only. Never use for actual calls.
    #[cfg(feature = "fixtures")]
    pub fn fixture_handshake(
        &self,
        peer: &Pin,
        initiator: bool,
        ephemeral: &[u8; 32],
    ) -> Result<Handshake, Error> {
        self.fixture_handshake_fault(peer, initiator, ephemeral, None)
    }

    #[cfg(feature = "fixtures")]
    pub fn fixture_handshake_fault(
        &self,
        peer: &Pin,
        initiator: bool,
        ephemeral: &[u8; 32],
        fault: Option<alloc::boxed::Box<fixtures::KemFault>>,
    ) -> Result<Handshake, Error> {
        use blake2::{Blake2s256, Digest};
        let derive = |index: u8| -> [u8; 32] {
            let mut h = Blake2s256::new();
            h.update(b"PUBLIC VoiceVault hybrid fixture v2");
            h.update(ephemeral);
            h.update([index]);
            h.finalize().into()
        };
        let mut key = Zeroizing::new([0; 64]);
        key[..32].copy_from_slice(&derive(0));
        key[32..].copy_from_slice(&derive(1));
        self.build(
            peer,
            initiator,
            randomness::SeedResolver::hybrid(*ephemeral, key, Zeroizing::new(derive(2)))
                .with_fault(fault),
            None,
            Some(ephemeral),
        )
    }

    fn build(
        &self,
        peer: &Pin,
        initiator: bool,
        resolver: randomness::SeedResolver,
        context: Option<&[u8; 32]>,
        fixture: Option<&[u8; 32]>,
    ) -> Result<Handshake, Error> {
        // Canonical roles bind both verified Ed25519 identities in addition to
        // Noise's pinned X25519 keys, full transcript and exact suite name.
        let local = self.signing.verifying_key().to_bytes();
        let (first, second) = if initiator {
            (&local, &peer.1)
        } else {
            (&peer.1, &local)
        };
        let mut prologue = alloc::vec::Vec::with_capacity(PROLOGUE.len() + 97);
        prologue.extend_from_slice(PROLOGUE);
        prologue.extend_from_slice(first);
        prologue.extend_from_slice(second);
        prologue.push(u8::from(context.is_some()));
        if let Some(context) = context {
            prologue.extend_from_slice(context);
        }
        let mut builder = Builder::with_resolver(
            PATTERN.parse().map_err(|_| Error::Handshake)?,
            alloc::boxed::Box::new(resolver),
        )
        .local_private_key(self.static_secret.as_ref())
        .map_err(|_| Error::Handshake)?
        .remote_public_key(&peer.0)
        .map_err(|_| Error::Handshake)?
        .prologue(&prologue)
        .map_err(|_| Error::Handshake)?;
        if let Some(ephemeral) = fixture {
            builder = builder.fixed_ephemeral_key_for_testing_only(ephemeral);
        }
        let inner = if initiator {
            builder.build_initiator()
        } else {
            builder.build_responder()
        };
        Ok(Handshake {
            inner: Some(inner.map_err(|_| Error::Handshake)?),
            gate: HandshakeGate::new(initiator),
            initiator,
        })
    }
}

/// Constructed only from a signature verified against an out-of-band identity.
pub struct Pin([u8; 32], [u8; 32]);

impl Pin {
    pub fn verify(record: &[u8; CONTACT], expected_signer: &[u8; 32]) -> Result<Self, Error> {
        if &record[..32] != expected_signer {
            return Err(Error::Contact);
        }
        let signer = VerifyingKey::from_bytes(expected_signer).map_err(|_| Error::Contact)?;
        let signature = Signature::from_bytes(record[64..].try_into().map_err(|_| Error::Size)?);
        signer
            .verify_strict(&signed_message(&record[..64]), &signature)
            .map_err(|_| Error::Contact)?;
        Ok(Self(
            record[32..64].try_into().map_err(|_| Error::Size)?,
            *expected_signer,
        ))
    }
}

pub struct Handshake {
    inner: Option<HandshakeState>,
    gate: HandshakeGate,
    initiator: bool,
}

impl Handshake {
    fn fail<T>(&mut self, error: Error) -> Result<T, Error> {
        self.gate.fail();
        self.inner.take();
        Err(error)
    }
    pub fn send(&mut self) -> Result<alloc::vec::Vec<u8>, Error> {
        if !self.gate.permits(true) {
            return self.fail(Error::State);
        }
        let len = if self.initiator {
            HANDSHAKE_FIRST
        } else {
            HANDSHAKE_SECOND
        };
        let mut wire = alloc::vec![0;len];
        match self
            .inner
            .as_mut()
            .ok_or(Error::State)?
            .write_message(&[], &mut wire)
        {
            Ok(n) if n == len => {
                self.gate.advance(true, true);
                Ok(wire)
            }
            _ => self.fail(Error::Handshake),
        }
    }
    pub fn receive(&mut self, wire: &[u8]) -> Result<(), Error> {
        if !self.gate.permits(false) {
            return self.fail(Error::State);
        }
        let len = if self.initiator {
            HANDSHAKE_SECOND
        } else {
            HANDSHAKE_FIRST
        };
        if wire.len() != len {
            return self.fail(Error::Size);
        }
        match self
            .inner
            .as_mut()
            .ok_or(Error::State)?
            .read_message(wire, &mut [])
        {
            Ok(0) => {
                self.gate.advance(false, true);
                Ok(())
            }
            _ => self.fail(Error::Handshake),
        }
    }
    pub fn split(mut self) -> Result<Session, Error> {
        if !self.gate.complete() {
            return self.fail(Error::State);
        }
        let inner = self.inner.take().ok_or(Error::State)?;
        if !inner.is_handshake_finished() {
            return Err(Error::State);
        }
        let binding: [u8; 32] = inner
            .get_handshake_hash()
            .try_into()
            .map_err(|_| Error::Handshake)?;
        Ok(Session {
            noise: Some(
                inner
                    .into_stateless_transport_mode()
                    .map_err(|_| Error::Handshake)?,
            ),
            state: CallState::default(),
            replay: Replay::default(),
            last_sent: None,
            binding,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Frame {
    bytes: [u8; PAYLOAD],
    len: u8,
}

impl Frame {
    pub fn new(bytes: &[u8]) -> Result<Self, Error> {
        if bytes.is_empty() || bytes.len() > PAYLOAD {
            return Err(Error::Size);
        }
        let mut frame = Self {
            bytes: [0; PAYLOAD],
            len: bytes.len() as u8,
        };
        frame.bytes[..bytes.len()].copy_from_slice(bytes);
        Ok(frame)
    }

    pub fn as_slice(&self) -> &[u8] {
        &self.bytes[..usize::from(self.len)]
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Media {
    Audio(Frame),
    Filler,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Received {
    Control(Control),
    Media(u64, Media),
}

pub struct Session {
    noise: Option<StatelessTransportState>,
    state: CallState,
    replay: Replay,
    last_sent: Option<u64>,
    binding: [u8; 32],
}

impl Session {
    pub fn channel_binding(&self) -> [u8; 32] {
        self.binding
    }
    pub fn close(&mut self) {
        self.state.close();
        self.noise.take();
    }
    pub fn consent(&mut self) {
        self.state.consent();
    }

    pub fn active(&self) -> bool {
        self.state.active()
    }

    fn seal(&self, sequence: u64, kind: u8, bytes: &[u8]) -> Result<[u8; RECORD], Error> {
        if self.last_sent.is_some_and(|last| sequence <= last) || sequence == u64::MAX {
            return Err(Error::Counter);
        }
        let mut plain = Zeroizing::new([0; PLAIN]);
        plain[0] = kind;
        plain[1] = bytes.len() as u8;
        plain[2..2 + bytes.len()].copy_from_slice(bytes);
        let mut wire = [0; RECORD];
        wire[..8].copy_from_slice(&sequence.to_le_bytes());
        if self
            .noise
            .as_ref()
            .ok_or(Error::State)?
            .write_message(sequence, &plain[..], &mut wire[8..])
            .map_err(|_| Error::Auth)?
            != RECORD - 8
        {
            return Err(Error::Size);
        }
        Ok(wire)
    }

    pub fn control(&mut self, control: Control) -> Result<[u8; RECORD], Error> {
        if !self.state.can_send(control) {
            return Err(Error::State);
        }
        let sequence = u64::from(control == Control::Ready);
        let wire = self.seal(sequence, sequence as u8, &[])?;
        self.state.sent(control);
        self.last_sent = Some(sequence);
        Ok(wire)
    }

    pub fn media(&mut self, slot: u64, media: Media) -> Result<[u8; RECORD], Error> {
        if slot >= MAX_EPOCH_SLOTS {
            self.close();
            return Err(Error::Expired);
        }
        if !self.state.active() {
            return Err(Error::State);
        }
        let sequence = slot.checked_add(FIRST_MEDIA).ok_or(Error::Counter)?;
        let wire = match media {
            Media::Audio(frame) => self.seal(sequence, 2, frame.as_slice()),
            Media::Filler => self.seal(sequence, 3, &[]),
        }?;
        self.last_sent = Some(sequence);
        Ok(wire)
    }

    pub fn receive(
        &mut self,
        wire: &[u8],
        slots: core::ops::Range<u64>,
    ) -> Result<Received, Error> {
        let wire: &[u8; RECORD] = wire.try_into().map_err(|_| Error::Size)?;
        let sequence = u64::from_le_bytes(wire[..8].try_into().map_err(|_| Error::Size)?);
        if !self.replay.eligible(sequence) {
            return Err(Error::Replay);
        }
        let mut plain = Zeroizing::new([0; PLAIN]);
        if self
            .noise
            .as_ref()
            .ok_or(Error::State)?
            .read_message(sequence, &wire[8..], &mut plain[..])
            .map_err(|_| Error::Auth)?
            != PLAIN
        {
            return Err(Error::Size);
        }
        let len = usize::from(plain[1]);
        if len > PAYLOAD || plain[2 + len..].iter().any(|&byte| byte != 0) {
            return Err(Error::Size);
        }
        let received = match (plain[0], sequence, len) {
            (0, 0, 0) => Received::Control(Control::Confirm),
            (1, 1, 0) => Received::Control(Control::Ready),
            (2 | 3, FIRST_MEDIA.., _) => {
                if !self.state.active() {
                    return Err(Error::State);
                }
                let slot = sequence - FIRST_MEDIA;
                if !slots.contains(&slot) {
                    return Err(Error::Counter);
                }
                if slot >= MAX_EPOCH_SLOTS {
                    self.close();
                    return Err(Error::Expired);
                }
                let media = match (plain[0], len) {
                    (2, 1..) => Media::Audio(Frame::new(&plain[2..2 + len])?),
                    (3, 0) => Media::Filler,
                    _ => return Err(Error::Size),
                };
                Received::Media(slot, media)
            }
            _ => return Err(Error::Command),
        };
        if let Received::Control(control) = received
            && !self.state.receive(control)
        {
            return Err(Error::State);
        }
        self.replay.commit(sequence);
        Ok(received)
    }
}

#[cfg(feature = "fixtures")]
pub mod fixtures;
