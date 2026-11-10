#![forbid(unsafe_code)]

use opus_rs::{Application, OpusDecoder, OpusEncoder};

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
        codec.bitrate_bps = BITRATE;
        codec.use_cbr = true;
        codec.use_inband_fec = false;
        codec.complexity = 5;
        // opus-rs has no DTX enable control. Its SILK default leaves DTX off.
        Ok(Self(codec))
    }

    pub fn encode(&mut self, pcm: &Pcm, out: &mut [u8; MAX_PACKET]) -> Result<usize, &'static str> {
        let bytes = self.0.encode_i16(pcm, SAMPLES, out)?;
        if bytes != CBR_BYTES || !admissible(&out[..bytes]) {
            return Err("unexpected Opus framing or bitrate");
        }
        Ok(bytes)
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
        let mut pcm = [0.0; SAMPLES];
        if self.0.decode(packet, SAMPLES, &mut pcm)? != SAMPLES {
            return Err("unexpected decoded duration");
        }
        Ok(pcm.map(float_to_pcm))
    }
}

pub fn float_to_pcm(sample: f32) -> i16 {
    (sample * 32768.0).round() as i16
}

/// Generated tones are deliberately far apart to detect swapped output.
pub fn synthetic(alice: bool, slot: u64) -> Pcm {
    let frequency = if alice { 400.0 } else { 700.0 };
    let phase = (slot % 50) as f32 * SAMPLES as f32;
    std::array::from_fn(|index| {
        let time = (phase + index as f32) / RATE as f32;
        let carrier = (std::f32::consts::TAU * frequency * time).sin();
        let envelope = 0.23 + 0.06 * (std::f32::consts::TAU * 3.0 * time).sin();
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
