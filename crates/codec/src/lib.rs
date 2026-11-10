#![cfg_attr(not(feature = "std"), no_std)]
#![forbid(unsafe_code)]

use opus_rs::{Application, OpusDecoder, OpusEncoder};
pub use opus_rs::{OpusDecoder as DecoderStorage, OpusEncoder as EncoderStorage};

pub trait Encode {
    fn encode(&mut self, pcm: &Pcm, out: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str>;
}
pub trait Decode {
    fn audio(&mut self, packet: &[u8]) -> Result<Pcm, &'static str>;
    fn conceal(&mut self) -> Pcm;
}
impl<T: Encode + ?Sized> Encode for &mut T {
    fn encode(&mut self, p: &Pcm, o: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str> {
        (**self).encode(p, o)
    }
}
impl<T: Decode + ?Sized> Decode for &mut T {
    fn audio(&mut self, p: &[u8]) -> Result<Pcm, &'static str> {
        (**self).audio(p)
    }
    fn conceal(&mut self) -> Pcm {
        (**self).conceal()
    }
}
pub struct EncoderRef<'a>(&'a mut OpusEncoder);
pub struct DecoderRef<'a>(&'a mut OpusDecoder);
fn configure(codec: &mut OpusEncoder) {
    codec.bitrate_bps = BITRATE;
    codec.use_cbr = true;
    codec.use_inband_fec = false;
    codec.complexity = 5;
}
fn encode(
    codec: &mut OpusEncoder,
    pcm: &Pcm,
    out: &mut [u8; MAX_PACKET],
) -> Result<usize, &'static str> {
    let n = codec.encode_i16(pcm, SAMPLES, out)?;
    if n != CBR_BYTES || !admissible(&out[..n]) {
        return Err("unexpected Opus framing or bitrate");
    }
    Ok(n)
}
fn decode(codec: &mut OpusDecoder, packet: &[u8]) -> Result<Pcm, &'static str> {
    let mut pcm = [0.0; SAMPLES];
    if codec.decode(packet, SAMPLES, &mut pcm)? != SAMPLES {
        return Err("unexpected decoded duration");
    }
    Ok(pcm.map(float_to_pcm))
}
#[cfg(not(feature = "std"))]
pub fn encoder_in_place(
    slot: &mut core::mem::MaybeUninit<EncoderStorage>,
) -> Result<EncoderRef<'_>, &'static str> {
    let codec = OpusEncoder::init_voip16k(slot)?;
    configure(codec);
    Ok(EncoderRef(codec))
}
pub fn decoder_in_place(
    slot: &mut core::mem::MaybeUninit<DecoderStorage>,
) -> Result<DecoderRef<'_>, &'static str> {
    Ok(DecoderRef(OpusDecoder::init(slot, RATE as i32, 1)?))
}
impl Encode for EncoderRef<'_> {
    fn encode(&mut self, p: &Pcm, o: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str> {
        encode(self.0, p, o)
    }
}
impl Decode for DecoderRef<'_> {
    fn audio(&mut self, p: &[u8]) -> Result<Pcm, &'static str> {
        if !admissible(p) {
            return Err("Opus requires a bounded mono 20 ms packet");
        }
        decode(self.0, p)
    }
    fn conceal(&mut self) -> Pcm {
        decode(self.0, &[]).unwrap_or([0; SAMPLES])
    }
}

pub const RATE: usize = 16_000;
pub const SAMPLES: usize = 320;
pub const BITRATE: i32 = 24_000;
pub const CBR_BYTES: usize = 60;
pub const MAX_PACKET: usize = 102;
pub type Pcm = [i16; SAMPLES];

pub struct Encoder(OpusEncoder);
pub struct Decoder(OpusDecoder);

impl Encoder {
    pub fn new() -> Result<Self, &'static str> {
        let mut codec = OpusEncoder::new(RATE as i32, 1, Application::Voip)?;
        configure(&mut codec);
        // opus-rs has no DTX enable control. Its SILK default leaves DTX off.
        Ok(Self(codec))
    }

    pub fn encode(&mut self, pcm: &Pcm, out: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str> {
        encode(&mut self.0, pcm, out)
    }
}

/// Gate packet size, channel count and total duration before invoking Opus.
/// The codec handles the internal length and padding syntax after this gate.
pub fn admissible(packet: &[u8]) -> bool {
    if !(2..=MAX_PACKET).contains(&packet.len()) {
        return false;
    }
    let toc = packet[0];
    if toc & 4 != 0 {
        return false;
    }
    let config = toc >> 3;
    // Duration units of 2.5 ms, from RFC 6716 table 2.
    let units = match config {
        0..=11 => [4, 8, 16, 24][usize::from(config & 3)],
        12..=15 => [4, 8][usize::from(config & 1)],
        _ => [1, 2, 4, 8][usize::from(config & 3)],
    };
    let frames = match toc & 3 {
        0 => 1,
        1 | 2 => 2,
        _ => packet[1] & 63,
    };
    u16::from(frames) * units == 8
}

impl Decoder {
    pub fn new() -> Result<Self, &'static str> {
        Ok(Self(OpusDecoder::new(RATE as i32, 1)?))
    }

    pub fn audio(&mut self, packet: &[u8]) -> Result<Pcm, &'static str> {
        if !admissible(packet) {
            return Err("Opus requires a bounded mono 20 ms packet");
        }
        self.decode(packet)
    }

    pub fn conceal(&mut self) -> Pcm {
        self.decode(&[]).unwrap_or([0; SAMPLES])
    }

    fn decode(&mut self, packet: &[u8]) -> Result<Pcm, &'static str> {
        decode(&mut self.0, packet)
    }
}

impl Encode for Encoder {
    fn encode(&mut self, p: &Pcm, o: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str> {
        Encoder::encode(self, p, o)
    }
}
impl Decode for Decoder {
    fn audio(&mut self, p: &[u8]) -> Result<Pcm, &'static str> {
        Decoder::audio(self, p)
    }
    fn conceal(&mut self) -> Pcm {
        Decoder::conceal(self)
    }
}

pub fn float_to_pcm(sample: f32) -> i16 {
    libm::roundf(sample * 32768.0) as i16
}

/// Generated tones are deliberately far apart to detect swapped output.
pub fn synthetic(alice: bool, slot: u64) -> Pcm {
    let frequency = if alice { 400.0 } else { 700.0 };
    let phase = (slot % 50) as f32 * SAMPLES as f32;
    core::array::from_fn(|index| {
        let time = (phase + index as f32) / RATE as f32;
        let carrier = libm::sinf(core::f32::consts::TAU * frequency * time);
        let envelope = 0.23 + 0.06 * libm::sinf(core::f32::consts::TAU * 3.0 * time);
        float_to_pcm(carrier * envelope)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cbr_including_silence() {
        let mut encoder = Encoder::new().unwrap();
        let mut decoder = Decoder::new().unwrap();
        let mut bytes = [0; MAX_PACKET];
        for pcm in [[0; SAMPLES], synthetic(true, 0), [0; SAMPLES]] {
            let len = encoder.encode(&pcm, &mut bytes).unwrap();
            assert_eq!(len, CBR_BYTES);
            assert_eq!(decoder.audio(&bytes[..len]).unwrap().len(), SAMPLES);
        }
    }

    #[test]
    fn rejects_wrong_geometry() {
        let mut decoder = Decoder::new().unwrap();
        for packet in [&[0x18, 0][..], &[0x0c, 0], &[0x0b, 63], &[8], &[0; 103]] {
            assert!(decoder.audio(packet).is_err());
        }
    }
}

// The no-heap constructor is part of the target port's unsafe boundary. Compare
// its observable output to the upstream constructor across changing input.
#[cfg(all(test, not(feature = "std")))]
extern crate std;
#[cfg(all(test, not(feature = "std")))]
#[test]
fn in_place_matches_upstream_constructor() {
    std::thread::Builder::new()
        .stack_size(16 * 1024 * 1024)
        .spawn(|| {
            let mut original = Encoder::new().unwrap();
            let mut slot = std::boxed::Box::new(core::mem::MaybeUninit::<EncoderStorage>::uninit());
            let mut placed = encoder_in_place(&mut slot).unwrap();
            let mut ds = std::boxed::Box::new(core::mem::MaybeUninit::<DecoderStorage>::uninit());
            let mut decoder = decoder_in_place(&mut ds).unwrap();
            let mut reference = Decoder::new().unwrap();
            for slot in 0..100 {
                let pcm = if slot % 7 == 0 {
                    [0; SAMPLES]
                } else {
                    synthetic(slot % 2 == 0, slot)
                };
                let mut a = [0; MAX_PACKET];
                let mut b = [0; MAX_PACKET];
                let n = original.encode(&pcm, &mut a).unwrap();
                let m = placed.encode(&pcm, &mut b).unwrap();
                assert_eq!(n, m);
                assert_eq!(a, b);
                assert_eq!(
                    decoder.audio(&b[..m]).unwrap(),
                    reference.audio(&a[..n]).unwrap()
                );
            }
        })
        .unwrap()
        .join()
        .unwrap();
}
