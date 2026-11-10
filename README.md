# Quietlink Lab

A software-only secure voice lab with synthetic audio, hostile phone and relay processes, protocol checks, and replayable reports. See the [build specification](docs/BUILD_SPEC.md), [threat model](docs/THREAT_MODEL.md), and [verification results](docs/RESULTS.md).

```sh
./lab help
./lab demo
./lab test
./lab watch --out /absolute/path/to/an/empty/directory
./lab status
./lab replay                 # last full run
./lab replay /path/to/run   # saved run
```

`test` and `watch` use the same suite. `watch` prints a loopback URL and attempts to open it in the current graphical session. The read-only live trace and animation pause during measurements. The saved HTML embeds the trace and works offline, including the test filter, step and replay controls. A full run exits zero only when every required group passes. The default report directory is under `.lab-runs/`. Each report includes `verdict.json`, `timing.json`, `events.ndjson`, `dashboard.html`, received WAVs when a call completed, and per-check diagnostic logs.

The launcher resolves the workspace from its own location. The compatible exact stable pin in `rust-toolchain.toml` was initialized from `VOICE_LAB_RUST=1.99.1`. The workspace and fuzz graph each have a Cargo lockfile. The full suite requires Linux x86-64, Python 3.11+, rustup, the pinned stable with rustfmt and Clippy, the pinned fuzz nightly, cargo-deny, cargo-fuzz, Kani and its setup, and the account's C/C++ toolchain. Existing account-local binaries in `.lab-cache/` and `~/.cargo/bin` are on the launcher's PATH. On this account Zig supplies the C++ toolchain for fuzzing. Reference libopus builds from the vendored archive, and the RFC vectors download from Xiph.Org if absent.

Timing runs use separate Alice, Phone A, Relay, Phone B and Bob processes connected by bounded Unix datagrams. The endpoint processes use absolute `CLOCK_MONOTONIC` deadlines. Idle and contention each measure 1,500 slots per direction. The contention scenario pins a busy xorshift worker to each endpoint's assigned CPU. Overload injects absolute deadline stalls, and the blocked-phone scenario leaves Alice's downstream IPC unread. The reports contain slot errors and misses, queue and memory peaks, CPU/codec/crypto time, and digital playout time relative to the nominal source slot. Trace records are buffered in memory during measurements. Alice's WAV contains Bob's 700 Hz tone and Bob's WAV contains Alice's 400 Hz tone.

Calls use generated audio, local Unix datagrams, and simulated link fragmentation. The original bootstrap script is preserved in `scripts/bootstrap-original.sh`.
