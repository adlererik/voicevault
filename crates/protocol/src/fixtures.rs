//! Deterministic non-secret lab fixtures. Never select these for wall-clock calls.
use crate::{Error, Handshake, Identity, Pin, Session};
use blake2::{Blake2s256, Digest};
use call_state::Control;

/// Public deterministic diagnostic entropy. Never enable fixtures in firmware.
pub struct Seeded {
    seed: u64,
    counter: u64,
}
impl Seeded {
    pub fn new(seed: u64) -> Self {
        Self { seed, counter: 0 }
    }
}
impl crate::Entropy for Seeded {
    fn seed(&mut self) -> Result<[u8; 32], Error> {
        self.counter = self.counter.checked_add(1).ok_or(Error::Entropy)?;
        let mut h = Blake2s256::new();
        h.update(b"PUBLIC LAB FIXTURE");
        h.update(self.seed.to_le_bytes());
        h.update(self.counter.to_le_bytes());
        Ok(h.finalize().into())
    }
}

struct Seeds(u8);

impl crate::Entropy for Seeds {
    fn seed(&mut self) -> Result<[u8; 32], Error> {
        self.0 += 1;
        Ok([self.0; 32])
    }
}

pub fn handshakes(call: u8) -> Result<(Handshake, Handshake), Error> {
    let a = Identity::new(&mut Seeds(0))?;
    let b = Identity::new(&mut Seeds(10))?;
    let a_record = a.contact();
    let b_record = b.contact();
    let a_pin = Pin::verify(
        &a_record,
        a_record[..32].try_into().map_err(|_| Error::Size)?,
    )?;
    let b_pin = Pin::verify(
        &b_record,
        b_record[..32].try_into().map_err(|_| Error::Size)?,
    )?;
    let mut first = [0xa1; 32];
    let mut second = [0xb2; 32];
    first[5] = call;
    second[5] = call;
    Ok((
        a.fixture_handshake(&b_pin, true, &first)?,
        b.fixture_handshake(&a_pin, false, &second)?,
    ))
}

pub fn sessions(call: u8) -> Result<(Session, Session), Error> {
    let (mut a, mut b) = handshakes(call)?;
    b.receive(&a.send()?)?;
    a.receive(&b.send()?)?;
    Ok((a.split()?, b.split()?))
}

pub fn activate(a: &mut Session, b: &mut Session) -> Result<(), Error> {
    a.consent();
    b.consent();
    for control in [Control::Confirm, Control::Ready] {
        b.receive(&a.control(control)?, 0..0)?;
        a.receive(&b.control(control)?, 0..0)?;
    }
    Ok(())
}

/// Generate authenticated arbitrary content with the initiator's fixture key.
pub fn peer_record(
    session: &Session,
    sequence: u64,
    kind: u8,
    bytes: &[u8],
) -> Result<[u8; crate::RECORD], Error> {
    if bytes.len() > crate::PAYLOAD {
        return Err(Error::Size);
    }
    session.seal(sequence, kind, bytes)
}

/// The actual secret-owning resolver, exposed solely for public-vector checks.
pub fn resolver() -> alloc::boxed::Box<dyn snow::resolvers::CryptoResolver + Send> {
    alloc::boxed::Box::new(crate::randomness::SeedResolver::new([7; 32]))
}

/// Public fault injections for malicious authenticated-peer tests only.
#[derive(Clone, Default)]
pub struct KemFault {
    pub public_key: Option<alloc::boxed::Box<[u8; crate::kem::PUBLIC]>>,
    pub ciphertext: alloc::vec::Vec<(usize, u8)>,
}
