//! Reference tooling is a subprocess boundary. The call path uses codec's narrow wrapper.
use crate::{Result, check, wall};
use codec::{Decoder, Encoder, MAX_PACKET, SAMPLES, float_to_pcm, synthetic};
use opus_rs::OpusDecoder;
use std::{
    fs::{self, File},
    io::{BufReader, BufWriter, Read, Write},
    path::Path,
    process::Command,
};

const VECTOR_PACKET_MAX: usize = 1500;

fn packets(path: &Path, mut visit: impl FnMut(&[u8]) -> Result<()>) -> Result<()> {
    let mut input = BufReader::new(File::open(path)?);
    let mut header = [0; 8];
    let mut packet = [0; VECTOR_PACKET_MAX];
    while input.read(&mut header[..1])? != 0 {
        input.read_exact(&mut header[1..])?;
        let length = u32::from_be_bytes(header[..4].try_into()?) as usize;
        check(length <= packet.len(), "oversized reference packet")?;
        input.read_exact(&mut packet[..length])?;
        visit(&packet[..length])?;
    }
    Ok(())
}

fn pcm_file(path: &Path, pcm: &[i16]) -> Result<()> {
    let mut file = BufWriter::new(File::create(path)?);
    for sample in pcm {
        file.write_all(&sample.to_le_bytes())?;
    }
    file.flush()?;
    Ok(())
}

fn successful(command: &mut Command) -> Result<()> {
    check(
        command.status()?.success(),
        &format!("command failed: {command:?}"),
    )
}

pub fn interop(reference: &Path, out: &Path) -> Result<()> {
    fs::create_dir_all(out)?;
    let demo = reference.join("opus_demo");
    let mut encoder = Encoder::new()?;
    let mut packet = [0; MAX_PACKET];
    let rust_packets = out.join("rust.bit");
    let mut file = BufWriter::new(File::create(&rust_packets)?);
    for slot in 0..100 {
        let pcm = synthetic(true, slot);
        let len = encoder.encode(&pcm, &mut packet)?;
        file.write_all(&(len as u32).to_be_bytes())?;
        file.write_all(&0u32.to_be_bytes())?; // skip C range check for this generated container
        file.write_all(&packet[..len])?;
    }
    file.flush()?;
    let c_pcm = out.join("c.pcm");
    successful(
        Command::new(&demo)
            .args(["-d", "16000", "1"])
            .arg(&rust_packets)
            .arg(&c_pcm),
    )?;
    let samples = fs::read(c_pcm)?
        .as_chunks::<2>()
        .0
        .iter()
        .map(|&bytes| i16::from_le_bytes(bytes))
        .collect::<Vec<_>>();
    check(
        samples.len() == SAMPLES * 100,
        "libopus returned incorrect duration",
    )?;
    let from_rust = out.join("rust-to-libopus.wav");
    wall::write_wav(&from_rust, &samples)?;
    let (right, wrong) = wall::wav_direction(&from_rust, 400.0, 700.0)?;
    check(
        right > 100_000.0 && right > wrong * 20.0,
        "libopus did not recover Rust input tone",
    )?;
    println!(
        "opus-rs -> libopus: {} samples, tone powers {right:.0} / {wrong:.0}",
        samples.len()
    );

    let source = out.join("source.pcm");
    let pcm: Vec<_> = (0..100).flat_map(|slot| synthetic(false, slot)).collect();
    pcm_file(&source, &pcm)?;
    let c_packets = out.join("libopus.bit");
    successful(
        Command::new(&demo)
            .args(["-e", "voip", "16000", "1", "24000", "-cbr"])
            .arg(&source)
            .arg(&c_packets),
    )?;
    let mut decoded = Vec::new();
    let mut decoder = Decoder::new()?;
    packets(&c_packets, |packet| {
        check(
            packet.len() == codec::CBR_BYTES,
            "reference CBR bitrate mismatch",
        )?;
        decoded.extend(decoder.audio(packet)?);
        Ok(())
    })?;
    check(
        (SAMPLES * 100..=SAMPLES * 102).contains(&decoded.len()),
        "opus-rs returned incorrect duration",
    )?;
    let from_c = out.join("libopus-to-rust.wav");
    wall::write_wav(&from_c, &decoded)?;
    let (right, wrong) = wall::wav_direction(&from_c, 700.0, 400.0)?;
    check(
        right > 100_000.0 && right > wrong * 20.0,
        "opus-rs did not recover reference tone",
    )?;
    println!(
        "libopus -> opus-rs: {} samples, tone powers {right:.0} / {wrong:.0}",
        decoded.len()
    );
    Ok(())
}

pub fn vectors(reference: &Path, vectors: &Path, out: &Path) -> Result<()> {
    fs::create_dir_all(out)?;
    let mut failures = Vec::new();
    for index in 1..=12 {
        let name = format!("testvector{index:02}");
        println!("{name}: RUNNING");
        let result = (|| -> Result<()> {
            let path = out.join(format!("{name}.pcm"));
            let mut file = BufWriter::new(File::create(&path)?);
            // Conformance exercises the same opus-rs decoder at call rate.
            // The independent vector harness accepts RFC packet geometries beyond the wire profile.
            let mut decoder = OpusDecoder::new(16_000, 1)?;
            let mut pcm = [0.0; 1920];
            packets(&vectors.join(format!("{name}.bit")), |packet| {
                let samples = decoder.decode(packet, pcm.len(), &mut pcm)?;
                for &sample in &pcm[..samples] {
                    file.write_all(&float_to_pcm(sample).to_le_bytes())?;
                }
                Ok(())
            })?;
            file.flush()?;
            for suffix in ["", "m"] {
                let status = Command::new(reference.join("opus_compare"))
                    .args(["-r", "16000"])
                    .arg(vectors.join(format!("{name}{suffix}.dec")))
                    .arg(&path)
                    .status()?;
                if status.success() {
                    return Ok(());
                }
            }
            Err("opus_compare rejected both RFC reference decodes".into())
        })();
        match result {
            Ok(()) => println!("{name}: PASS"),
            Err(error) => {
                println!("{name}: FAIL ({error})");
                failures.push(name);
            }
        }
    }
    check(
        failures.is_empty(),
        &format!("RFC 8251 decoder vectors failed: {}", failures.join(", ")),
    )
}
