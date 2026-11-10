#![no_main]

use libfuzzer_sys::fuzz_target;
use protocol::{HANDSHAKE, fixtures};

fuzz_target!(|data: &[u8]| {
    let (mut a, mut b) = fixtures::handshakes(1).unwrap();
    let first = a.send().unwrap();
    if data.first().is_some_and(|flag| flag & 1 == 0) {
        let _ = b.receive(data);
    } else {
        b.receive(&first).unwrap();
        let mut response = b.send().unwrap();
        for pair in data
            .get(1..)
            .unwrap_or_default()
            .chunks_exact(2)
            .take(HANDSHAKE)
        {
            response[usize::from(pair[0]) % HANDSHAKE] ^= pair[1];
        }
        let _ = a.receive(&response);
    }
});
