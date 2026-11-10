# Quietlink Lab build specification

This preserves the initial implementation brief. The authorized second phase below supersedes conflicting details, particularly the earlier 30-second fuzz minimum and nine-group count.

Build the full software-only secure voice lab in this repository. Continue
existing work and inspect previous failures. Implement, run available tests,
fix failures, and document the results and limitations. Keep tooling and
files in this account. Use no sudo, system package installs, physical phone,
real BLE, real microphones, real contacts, Nostr deployment, paid APIs,
or public listeners. Use development network access for official docs,
dependencies, reference vectors and advisories. Simulated calls stay local.

Implement an executable ./lab. ./lab and ./lab help show usage. ./lab test
runs the full automated suite. ./lab watch runs that same suite with a live
browser dashboard. ./lab status shows the last verdict and failure reasons.
./lab replay opens an offline dashboard for a saved run. ./lab demo runs
a short call and saves the received WAVs. Accept --out ABS_DIR for test
and watch. Resolve the project path and local tool environment inside ./lab
so it works from a fresh shell. Lock dependencies, use VOICE_LAB_RUST as
the initial exact stable pin, and preserve a compatible existing pin.

Use the existing six-crate architecture when present. Use safe Rust for
trusted parsing, call state and replay code, with fixed bounds and narrow
codec, clock, entropy, UI and transport interfaces. Simulate out-of-band
pinning of signed Ed25519 contact records bound to separate static X25519
keys. Use Snow with Noise_KK_25519_ChaChaPoly_BLAKE2s, fresh ephemeral keys
per call, Noise split directional keys, and stateless transport. Use an
explicit sequence as the nonce and update the bounded replay window only
after authentication. Require mutual confirmation and local consent before
audio. Use OS entropy for wall-clock runs and fixed seeds for deterministic
tests. Reject early media, remote pairing, mic activation, debug and update
commands. Test reset and reconnect for key-and-nonce reuse.

Use real opus-rs, 16 kHz mono, 20 ms frames, initial 24 kbit/s CBR and DTX
off. Emit exactly one 128-byte record per active slot per direction before
link overhead. Encode silence normally and send encrypted filler on mute
or codec underrun if the scheduler can still emit. Authenticate before
decode. Bound Opus frame length and duration, queues, fragmentation,
reassembly, and playout. Handle jitter and loss with bounded buffering and
loss concealment. Check interoperability with upstream libopus in both
directions and run applicable official decoder vectors. Build the reference
codec locally from pinned vendored source using the existing C toolchain.

Provide deterministic virtual-clock tests and a release-mode wall-clock
run with Alice, Bob, Phone A, Phone B and Relay as separate processes.
Treat both phones and the relay as hostile. Give them bounded IPC only.
Use an unprivileged Linux sandbox, such as existing bubblewrap or a
documented seccomp allowlist with only required inherited IPC descriptors.
Test that hostile processes cannot open files, create network connections
or inspect endpoint memory. Fail closed if isolation cannot be enforced.
Test packet loss, delay, duplication, reordering, replay, tampering,
injection, fragmentation, flooding, backpressure, collusion and reset.
Test forged counters and crafted Opus from a malicious authenticated
peer. Verify distinct recovered synthetic audio and correct direction
in both WAVs.

Automate formatting, Clippy, unit and integration tests, Noise vectors,
proptest, Opus interop, isolation tests, cargo-deny, cargo-fuzz and Kani.
Run fuzzing for at least 30 seconds each on handshake, authenticated
record handling and codec targets. Use Kani on the actual replay and
call-state code. Continue independent groups on failures and report
dependent groups as BLOCKED. Show a terminal PASS/FAIL/BLOCKED table with
reasons and log paths. Exit nonzero unless every required group passes.
Use real results and keep all required checks enabled.

Build a browser dashboard using inline HTML/CSS/JS and a loopback-only,
read-only event stream. Show both devices, both phones and the relay.
Animate sends, drops, tampering, replays and receiver responses from
actual test events. Show PASS/FAIL and expected versus observed behavior.
Support pause, step, replay and filtering by test. Use the same events
and verdicts as the CLI. Keep keys and plaintext out of dashboard data.
Open the existing browser when possible and print the local URL. Save
a self-contained offline replay. Test event and verdict mapping.

Use absolute monotonic 20 ms deadlines. Measure release-mode operation
for 30 seconds idle and 30 seconds under reproducible CPU contention,
plus overload and a blocked phone. Suspend dashboard streaming and
animation during measurements and replay afterward. Avoid blocking trace
I/O on timing threads. Measure per-direction p50/p95/p99/max send error,
missed slots, CPU time, codec and crypto time, peak RSS, queue peaks,
drops and digital playout latency. Record host and load details. Initial
idle and contention gates are p99 absolute send error <= 5 ms and missed
slots <= 0.1% in each direction. Under overload, require bounded queues
and zero catch-up bursts and report all misses. Document the separate
hardware validation needed for MCU timing, BLE and acoustic leakage.

Each full run writes verdict.json with top-level unit, protocol, codec,
isolation, fuzz, kani, dependencies, timing and dashboard statuses.
Use "pass" only when the corresponding checks passed. Save timing.json,
events.ndjson, dashboard.html, alice-received.wav, bob-received.wav and
diagnostic logs in the requested directory. Run checks available within
the Codex sandbox and document blockers. The outer shell will run
./lab watch natively and validate a fresh report.

## Authorized second phase: hostile-phone device model

Assume NSA-capability compromise of both phones and control of telecommunications. Supply-chain attacks are excluded. Keep the project software-only. Add confirmed Noise XX enrollment, sealed owner-bound contact state and anti-rollback generation, signed challenge/counter/expiry-bound invitations, invitation-bound Noise KK, irreversible close and bounded media-key lifetime, modeled onboard entropy failure handling, a constrained hostile-radio port, and locally authorized signed offline image verification with protected versions and power-loss recovery.

Deepen critical verification with KK and XX published vectors against the actual crypto adapters, lifecycle/fault/property tests, six fuzz targets at least 120 seconds each, and four Kani harnesses. Keep all original checks and timing gates. Add `lifecycle` and `platform` as required verdict groups. The ARM probe must link and execute actual no_std voice and policy paths, enforce flash/RAM budgets and report its observed heap/stack use. Clearly mark diagnostic keys as public. No hardware feasibility, worst-case timing, erasure or universal adversary-resistance claims may be inferred from finite software tests.

## Authorized VoiceVault live UI follow-up

The owner requested a persistent fixed address, live display of tests as they execute, visual representations of both devices and a project rename to VoiceVault. `./lab watch` and `./lab demo` publish to the read-only loopback service at **127.0.0.1:8765**. `./lab ui` reopens it. An unrelated occupied port fails explicitly; never silently choose another port or bind a public interface. Keep previous evidence and cryptographic domains intact.

This supersedes the initial requirement to suspend all streaming during timing: keep check/elapsed progress visible with graphics still. Timing-critical endpoints retain buffered traces and emit no live packet telemetry during scored measurements. Mark those traces recorded. Use two separate eight-second unscored live scenarios for continuously streamed endpoint lifecycle/media events and induced corruption/loss. Add both scenarios to the protocol group without removing any existing check or changing timing/fuzz gates. A demo completion is not a full-suite pass.

## Authorized command-deck and synthetic listening follow-up

Place live devices, graphical hostile phones, packet/rejection activity and compact check/fuzz displays before long results lists. Keep the first observation deck usable in a narrow browser pane. Add opt-in monitoring of actual post-decryption synthetic PCM at the loopback-only lab service; this is a trusted-host test output, never a phone/radio command or production feature. No microphone capture or real contacts/audio are introduced. Trace JSON remains metadata only. Scored timing modes must not create monitor files, and the HTTP monitor must refuse timing/inactive/mismatched-run access. Compare live monitor records against actual recovered WAVs.

`./lab demo --seconds 8..30` permits longer observed calls; full verification explicitly retains eight-second live scenarios and all original timing/fuzz gates. Keep historical full-suite evidence distinct from focused feature checks. Post-quantum forward secrecy is a feasibility study only; do not change the cryptographic suite without a new implementation task and reviewed design.
