# Development and reproducing the lab

The native laboratory currently targets **Linux x86-64**. Calls are synthetic and local. The ARM target is a separate diagnostic, not deployable firmware. No real microphone, physical phone, BLE network or cloud calling API is required.

## Start with a short call

Clone the repository using your normal GitHub access, then run:

```sh
git clone https://github.com/adlererik/voicevault.git
cd voicevault
./lab help
./lab demo
```

Install Rust through rustup and make the exact pin in [`rust-toolchain.toml`](../rust-toolchain.toml) available. Python 3.11+ and Linux connected Unix datagrams/seccomp support are needed. A missing or unavailable check is reported instead of being treated as a pass.

`demo` builds the release runner, opens the fixed dashboard and runs two isolated eight-second calls: normal delivery and deliberate media corruption/loss. It saves recovered synthetic WAVs and a demo-only verdict. It is smaller than the full verification suite. For a visible complete run:

```sh
./lab watch --out /absolute/path/to/an/empty/directory
./lab ui
./lab status
./lab replay
```

`test` runs the same required suite without the live dashboard. `--out` must be an empty absolute directory. The launcher resolves its own source directory and sets account-local Cargo/Kani/cache paths, so the checkout need not keep its original folder name.

## Full-suite prerequisites

| Tool/input | Purpose |
|---|---|
| Pinned Rust `1.99.1`, rustfmt and Clippy | Native code, checks and release runner |
| `nightly-2026-08-21` | Instrumented fuzzing and the recorded proof tooling environment |
| cargo-fuzz `0.13.2` | Eight fuzz targets, at least 120 seconds each |
| cargo-deny `0.20.2` | Advisories, dependency bans, licenses and allowed sources |
| kani-verifier `0.68.0` with setup completed | Five bounded state/counter harnesses; recorded CBMC is 6.11.0 |
| C/C++ toolchain, make and ar | Upstream libopus reference build and fuzz runtime |
| ARM Rust target `thumbv8m.main-none-eabihf` | Freestanding trusted-core build/link |
| Official QEMU with `mps2-an505`, plus `arm-none-eabi-size` | Cortex-M33 execution and section/memory gates |
| Internet access for development inputs when uncached | Rust dependencies, official vectors and advisory updates; calls themselves remain local |

Exact observed versions are in [the evidence snapshot](evidence/phase2/tool-versions.json). The recorded host used account-local Zig 0.17.1 and xPack QEMU 9.2.4-1 without system-wide installation. This repository is not a complete general-purpose installer for those tools.

Example account-local Rust-tool setup, after rustup is installed:

```sh
rustup toolchain install 1.99.1 --component rustfmt --component clippy
rustup toolchain install nightly-2026-08-21
rustup target add thumbv8m.main-none-eabihf --toolchain 1.99.1

export CARGO_HOME="$PWD/.lab-cache/cargo"
export KANI_HOME="$PWD/.lab-cache/kani"
export PATH="$CARGO_HOME/bin:$PATH"
cargo install --locked --version 0.13.2 cargo-fuzz
cargo install --locked --version 0.20.2 cargo-deny
cargo install --locked --version 0.68.0 kani-verifier
cargo kani setup
```

Provide a supported C/C++ toolchain and QEMU separately from their official sources. `QEMU_SYSTEM_ARM` can name an installed emulator path. [ARM setup and limits](PLATFORM.md)

The preserved [`bootstrap-original.sh`](../scripts/bootstrap-original.sh) contains historical source-generation instructions and targets the old folder name. **Do not run it to regenerate an existing checkout.** The current code runs independently of the AI tooling used to develop it.

## What the full run checks

| Group | Required work |
|---|---|
| unit | Formatting of three workspaces, Clippy, Rust tests and release build |
| protocol | Actual-resolver KK/XX vectors, negative/property tests, virtual attacks and two live full-duplex calls |
| lifecycle | Enrollment, contacts, invitations, storage, entropy, radio and update fault tests |
| platform | Actual no_std link/execution and explicit capacity gates |
| codec | CBR/framing, constructor equivalence, patch integrity, libopus interop and official vectors |
| isolation | Hostile-role syscall/IPC containment probes |
| fuzz | Eight instrumented campaigns with recorded durations and unchanged lockfile. [Target inputs and checks](FUZZING.md) |
| kani | Five bounded harnesses with unchanged lockfile |
| dependencies | Native, fuzz and ARM dependency graphs |
| timing | Idle, CPU contention, overload and blocked phone, with retained gates |
| dashboard | Read-only loopback stream, controls, parsing and verdict mapping |

The dashboard's **Checks** view shows high-level verification progress. **Individual results** shows named outcomes actually printed by supported test/proof/vector harnesses; a group pass does not manufacture case passes. Search filters those lists. **Trace scenario** independently filters event replay. During live calls, endpoint states and media events arrive before process exit. Rust tests run with a single test thread so starts and multi-line outcomes can be associated. Fuzz campaigns show reported execution rates/counts and proofs report each harness. Timing graphics stay still while check/elapsed progress continues; benchmark packets emitted after a scenario are labeled recorded. [Dashboard operation and telemetry limits](LIVE_DASHBOARD.md)

## Evidence and snapshots

A run produces raw verdicts, log paths, timing, source/input hashes where recorded, recovered synthetic WAVs, an event stream, saved dashboard and ARM report. The ARM ELF uses public fixture keys and is named accordingly. Do not deploy it.

The committed phase-two snapshot records a past run, not current CI status. For a runtime change, run the affected checks and complete the required suite before recording a new full pass. For documentation or presentation changes, preserve the old evidence and state any separate validation. Exact host timings and OS-random handshakes naturally differ across runs.

## Growing the repository

Keep protocol/state logic separate from device drivers and untrusted carriers. Add a hardware or firmware component when its implementation and ownership exist, rather than duplicating protocol logic into a parallel stack. Preserve bounded inputs, explicit local authority and independently testable interfaces. Future production build/release, board, peripheral and relay components belong to the [roadmap](ROADMAP.md), not the current evidence claims.

The repository is now VoiceVault, previously VoxBastion and originally Quietlink Lab. Historical crates, diagnostics and authenticated wire domains retain `quietlink` identifiers intentionally. Clones should use the new remote; an existing checkout can update it with `git remote set-url origin https://github.com/adlererik/voicevault.git`.


Dependency checks use the locked graphs for the supported Linux host, fuzzing host and Cortex-M33 target, with host build units included in the ARM scan. Cargo's unfiltered metadata also resolves libcrux's optional `cfg(hax)` proof-extraction tooling. That dormant graph triggers a RustSec unmaintained notice for `proc-macro-error2`. Cargo does not include that tool in either supported build graph. The scans retain the same advisory, ban, license and source policy. [RustSec advisory](https://rustsec.org/advisories/RUSTSEC-2026-0173.html)
