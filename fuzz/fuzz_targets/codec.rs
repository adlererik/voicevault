#![no_main]

use codec::{Decoder, MAX_PACKET};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut decoder = Decoder::new().unwrap();
    let _ = decoder.audio(data);
    for chunk in data.chunks(MAX_PACKET).take(4) {
        let _ = decoder.audio(chunk);
    }
    let _ = decoder.conceal();
});
