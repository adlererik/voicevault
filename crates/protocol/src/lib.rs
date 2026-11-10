#![cfg_attr(not(feature = "std"), no_std)]
#![forbid(unsafe_code)]

extern crate alloc;
pub mod contacts;
pub mod enrollment;
pub mod entropy;
pub mod invitation;
pub mod radio;
mod randomness;
pub mod update;

use call_state::{CallState, Control, FIRST_MEDIA, Replay};
use curve25519_dalek::montgomery::MontgomeryPoint;
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use snow::{Builder, HandshakeState, StatelessTransportState};
use zeroize::Zeroizing;

pub const PATTERN: &str = "Noise_KK_25519_ChaChaPoly_BLAKE2s";
const DOMAIN: &[u8; 24] = b"quietlink contact v1 edx";
const PROLOGUE: &[u8] = b"quietlink call v1";
pub const HANDSHAKE: usize = 48;
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
        self.build(peer, initiator, entropy.seed()?, context, None)
    }

    /// Deterministic lab fixtures only. Wall-clock callers use `handshake`.
    #[cfg(feature = "fixtures")]
    pub fn fixture_handshake(
        &self,
        peer: &Pin,
        initiator: bool,
        ephemeral: &[u8; 32],
    ) -> Result<Handshake, Error> {
        self.build(peer, initiator, *ephemeral, None, Some(ephemeral))
    }

    fn build(
        &self,
        peer: &Pin,
        initiator: bool,
        seed: [u8; 32],
        context: Option<&[u8; 32]>,
        fixture: Option<&[u8; 32]>,
    ) -> Result<Handshake, Error> {
        let mut prologue = [0u8; 64];
        prologue[..PROLOGUE.len()].copy_from_slice(PROLOGUE);
        let prologue_len = if let Some(context) = context {
            prologue[PROLOGUE.len()..PROLOGUE.len() + 32].copy_from_slice(context);
            PROLOGUE.len() + 32
        } else {
            PROLOGUE.len()
        };
        let mut builder = Builder::with_resolver(
            PATTERN.parse().map_err(|_| Error::Handshake)?,
            alloc::boxed::Box::new(randomness::SeedResolver::new(seed)),
        )
        .local_private_key(self.static_secret.as_ref())
        .map_err(|_| Error::Handshake)?
        .remote_public_key(&peer.0)
        .map_err(|_| Error::Handshake)?
        .prologue(&prologue[..prologue_len])
        .map_err(|_| Error::Handshake)?;
        if let Some(ephemeral) = fixture {
            builder = builder.fixed_ephemeral_key_for_testing_only(ephemeral);
        }
        let inner = if initiator {
            builder.build_initiator()
        } else {
            builder.build_responder()
        };
        inner.map(Handshake).map_err(|_| Error::Handshake)
    }
}

/// Constructed only from a signature verified against an out-of-band identity.
pub struct Pin([u8; 32]);

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
        Ok(Self(record[32..64].try_into().map_err(|_| Error::Size)?))
    }
}

pub struct Handshake(HandshakeState);

impl Handshake {
    pub fn send(&mut self) -> Result<[u8; HANDSHAKE], Error> {
        let mut wire = [0; HANDSHAKE];
        if self
            .0
            .write_message(&[], &mut wire)
            .map_err(|_| Error::Handshake)?
            != HANDSHAKE
        {
            return Err(Error::Size);
        }
        Ok(wire)
    }

    pub fn receive(&mut self, wire: &[u8]) -> Result<(), Error> {
        if wire.len() != HANDSHAKE {
            return Err(Error::Size);
        }
        match self.0.read_message(wire, &mut []) {
            Ok(0) => Ok(()),
            _ => Err(Error::Handshake),
        }
    }

    pub fn split(self) -> Result<Session, Error> {
        let binding: [u8; 32] = self
            .0
            .get_handshake_hash()
            .try_into()
            .map_err(|_| Error::Handshake)?;
        Ok(Session {
            noise: Some(
                self.0
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
        let mut plain = [0; PLAIN];
        plain[0] = kind;
        plain[1] = bytes.len() as u8;
        plain[2..2 + bytes.len()].copy_from_slice(bytes);
        let mut wire = [0; RECORD];
        wire[..8].copy_from_slice(&sequence.to_le_bytes());
        if self
            .noise
            .as_ref()
            .ok_or(Error::State)?
            .write_message(sequence, &plain, &mut wire[8..])
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
        let mut plain = [0; PLAIN];
        if self
            .noise
            .as_ref()
            .ok_or(Error::State)?
            .read_message(sequence, &wire[8..], &mut plain)
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
