#![no_main]

use libfuzzer_sys::fuzz_target;
use protocol::{PAYLOAD, fixtures};

fuzz_target!(|data: &[u8]| {
    let (mut a, mut b) = fixtures::sessions(1).unwrap();
    if data.first().is_some_and(|flags| flags & 1 == 0) {
        fixtures::activate(&mut a, &mut b).unwrap();
    }
    if let Some(header) = data.get(..10) {
        let sequence = if header[0] & 2 == 0 {
            u64::from(header[1] % 12)
        } else {
            u64::from_le_bytes(header[1..9].try_into().unwrap())
        };
        if let Ok(wire) = fixtures::peer_record(
            &a,
            sequence,
            header[9] % 9,
            &data[10..data.len().min(10 + PAYLOAD)],
        ) {
            let _ = b.receive(&wire, 0..8);
            let _ = b.receive(&wire, 0..8);
        }
    }
    let _ = b.receive(data, 0..8);
});
