//! Deterministic non-secret lab fixtures. Never select these for wall-clock calls.
use crate::{Error, Handshake, Identity, Pin, Session};
use call_state::Control;

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
