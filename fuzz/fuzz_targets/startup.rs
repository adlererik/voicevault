#![no_main]
use libfuzzer_sys::fuzz_target;
fuzz_target!(|data: &[u8]| {
    let flight = data.first().copied().unwrap_or(0) % 3;
    if let Some(mut parser) = link::Startup::new(flight) {
        let mut time = 0u64;
        for part in data.get(1..).unwrap_or_default().chunks(41).take(128) {
            time = time.saturating_add(u64::from(part[0]));
            let len = part.get(1).copied().unwrap_or(0) as usize % 40;
            let frame = part.get(2..).unwrap_or_default();
            if let Ok(Some(record)) = parser.push(&frame[..len.min(frame.len())], time) {
                assert_eq!(
                    record.len(),
                    if flight == 0 {
                        link::STARTUP_FIRST
                    } else {
                        link::STARTUP_SECOND
                    }
                );
                assert!(record.len() <= link::STARTUP_MAX);
            }
        }
    }
    // Exercise reachable completion as well as random rejection paths.
    let flight = flight % 2;
    let wire = [7; link::STARTUP_MAX];
    let len = if flight == 0 {
        link::STARTUP_FIRST
    } else {
        link::STARTUP_SECOND
    };
    let mut parser = link::Startup::new(flight).unwrap();
    for (packet, n) in link::startup_fragments(flight, &wire[..len]).unwrap() {
        if let Ok(Some(output)) = parser.push(&packet[..n], 0) {
            assert_eq!(output, &wire[..len]);
        }
    }
});
