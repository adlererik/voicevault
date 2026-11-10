//! Noise XX enrollment with full 256-bit transcript comparison on both trusted
//! displays. This is deliberately NOT a home-grown short authentication string.
use crate::{CONTACT, Entropy, Identity, Pin, PolicyError as E, PolicyResult as R};
use snow::{Builder, HandshakeState, StatelessTransportState};

pub const MAX_ENROLLMENT_MESSAGE: usize = 256;
pub const CONFIRM_BYTES: usize = 48;

#[derive(Clone, Copy)]
pub struct EnrolledContact {
    pub(crate) record: [u8; CONTACT],
}
impl EnrolledContact {
    /// The expected signer and approval must originate in the trusted local UI.
    pub fn verified_oob(record: [u8; CONTACT], signer: &[u8; 32], local_approval: bool) -> R<Self> {
        if !local_approval {
            return Err(E::LocalApproval);
        }
        Pin::verify(&record, signer).map_err(|_| E::Identity)?;
        Ok(Self { record })
    }
    pub fn record(&self) -> &[u8; CONTACT] {
        &self.record
    }
}

pub struct Enrollment {
    noise: HandshakeState,
    local: [u8; CONTACT],
    peer: Option<[u8; CONTACT]>,
    initiator: bool,
    writes: u8,
    reads: u8,
    failed: bool,
}
impl Enrollment {
    pub fn new(identity: &Identity, initiator: bool, entropy: &mut impl Entropy) -> R<Self> {
        let resolver =
            crate::randomness::SeedResolver::new(entropy.seed().map_err(|_| E::Entropy)?);
        let builder = Builder::with_resolver(
            "Noise_XX_25519_ChaChaPoly_BLAKE2s"
                .parse()
                .map_err(|_| E::Invalid)?,
            alloc::boxed::Box::new(resolver),
        )
        .local_private_key(identity.static_secret.as_ref())
        .map_err(|_| E::Invalid)?
        .prologue(b"quietlink enrollment v1")
        .map_err(|_| E::Invalid)?;
        let noise = if initiator {
            builder.build_initiator()
        } else {
            builder.build_responder()
        }
        .map_err(|_| E::State)?;
        Ok(Self {
            noise,
            local: identity.contact(),
            peer: None,
            initiator,
            writes: 0,
            reads: 0,
            failed: false,
        })
    }
    pub fn write(&mut self, out: &mut [u8; MAX_ENROLLMENT_MESSAGE]) -> R<usize> {
        if self.failed {
            return Err(E::State);
        }
        let payload = if self.initiator && self.writes == 0 {
            &[][..]
        } else {
            &self.local[..]
        };
        match self.noise.write_message(payload, out) {
            Ok(n) => {
                self.writes += 1;
                Ok(n)
            }
            Err(_) => {
                self.failed = true;
                Err(E::State)
            }
        }
    }
    pub fn read(&mut self, wire: &[u8]) -> R<()> {
        if self.failed {
            return Err(E::State);
        }
        let expected = if self.initiator {
            224
        } else if self.reads == 0 {
            32
        } else {
            192
        };
        if wire.len() != expected {
            self.failed = true;
            return Err(E::Invalid);
        }
        let mut record = [0; CONTACT];
        let n = match self.noise.read_message(wire, &mut record) {
            Ok(n) => n,
            Err(_) => {
                self.failed = true;
                return Err(E::Signature);
            }
        };
        self.reads += 1;
        if n == CONTACT {
            let signer: [u8; 32] = record[..32].try_into().map_err(|_| E::Invalid)?;
            if signer == self.local[..32]
                || Pin::verify(&record, &signer).is_err()
                || self.noise.get_remote_static() != Some(&record[32..64])
            {
                self.failed = true;
                return Err(E::Identity);
            }
            self.peer = Some(record);
        } else if n != 0 {
            self.failed = true;
            return Err(E::Invalid);
        }
        Ok(())
    }
    pub fn finish(self) -> R<Pairing> {
        if self.failed || !self.noise.is_handshake_finished() {
            return Err(E::State);
        }
        let fingerprint = self
            .noise
            .get_handshake_hash()
            .try_into()
            .map_err(|_| E::State)?;
        let peer = self.peer.ok_or(E::Identity)?;
        let noise = self
            .noise
            .into_stateless_transport_mode()
            .map_err(|_| E::State)?;
        Ok(Pairing {
            noise,
            peer,
            fingerprint,
            local: false,
            remote: false,
            failed: false,
        })
    }
}
pub struct Pairing {
    noise: StatelessTransportState,
    peer: [u8; CONTACT],
    fingerprint: [u8; 32],
    local: bool,
    remote: bool,
    failed: bool,
}
impl Pairing {
    pub fn fingerprint(&self) -> [u8; 32] {
        self.fingerprint
    }
    pub fn confirm_local(&mut self, compared: &[u8; 32], approved: bool) -> R<[u8; CONFIRM_BYTES]> {
        if self.failed || self.local {
            return Err(E::State);
        }
        if !approved || compared != &self.fingerprint {
            self.failed = true;
            return Err(E::LocalApproval);
        }
        let mut out = [0; CONFIRM_BYTES];
        if self
            .noise
            .write_message(0, &self.fingerprint, &mut out)
            .map_err(|_| E::State)?
            != CONFIRM_BYTES
        {
            self.failed = true;
            return Err(E::State);
        }
        self.local = true;
        Ok(out)
    }
    pub fn receive_confirmation(&mut self, wire: &[u8]) -> R<()> {
        if self.failed || self.remote {
            return Err(E::State);
        }
        let mut fp = [0; 32];
        if wire.len() != CONFIRM_BYTES
            || self.noise.read_message(0, wire, &mut fp).ok() != Some(32)
            || fp != self.fingerprint
        {
            self.failed = true;
            return Err(E::Signature);
        }
        self.remote = true;
        Ok(())
    }
    pub fn complete(self) -> R<EnrolledContact> {
        if self.failed || !self.local || !self.remote {
            return Err(E::LocalApproval);
        }
        Ok(EnrolledContact { record: self.peer })
    }
}
