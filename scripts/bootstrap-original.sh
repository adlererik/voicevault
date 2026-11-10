bash <<'VOICE_LAB'
set -euo pipefail
umask 077

if (( EUID == 0 )); then
  echo "Run this from your regular Fedora test account." >&2
  exit 1
fi

export PATH="$HOME/.local/bin:${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
unset OPENAI_API_KEY CODEX_API_KEY RUSTUP_TOOLCHAIN

missing=()
for tool in git curl python3 cc c++ ar; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if (( ${#missing[@]} )); then
  printf 'BLOCKED. Missing existing Fedora tools: %s\n' "${missing[*]}" >&2
  exit 1
fi

project="$HOME/src/secure-voice-lab"
if [[ -e "$project" || -L "$project" ]]; then
  if [[ ! -d "$project" || -L "$project" ]] ||
     [[ ! -f "$project/.secure-voice-lab" &&
        ! ( -f "$project/Cargo.toml" &&
            -f "$project/docs/THREAT_MODEL.md" &&
            -d "$project/crates/device-core" ) ]]; then
    echo "Unrecognized existing directory: $project" >&2
    exit 1
  fi
else
  mkdir -p -- "$HOME/src"
  mkdir -- "$project"
  git -C "$project" init -q
  touch "$project/.secure-voice-lab"
fi
cd -- "$project"
[[ "$(git rev-parse --show-toplevel)" == "$(pwd -P)" ]]

export CARGO_HOME="$PWD/.lab-cache/cargo"
export KANI_HOME="$PWD/.lab-cache/kani"
export PATH="$CARGO_HOME/bin:$PWD/.lab-cache/bin:$HOME/.cargo/bin:$PATH"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
mkdir -p -- "$CARGO_HOME" "$KANI_HOME" .lab-cache/bin .lab-runs
for pattern in /.lab-cache/ /.lab-runs/; do
  grep -Fxq -- "$pattern" .gitignore 2>/dev/null ||
    printf '\n%s\n' "$pattern" >> .gitignore
done

if ! command -v codex >/dev/null; then
  curl -fsSL --proto '=https' https://chatgpt.com/codex/install.sh -o .lab-cache/install-codex.sh
  CODEX_INSTALL_DIR="$PWD/.lab-cache/bin" CODEX_NON_INTERACTIVE=1 \
    sh .lab-cache/install-codex.sh </dev/null
fi
login="$(codex login status 2>&1 || true)"
if [[ "$login" != *"Logged in using ChatGPT"* ]]; then
  codex -c 'forced_login_method="chatgpt"' login </dev/tty
fi

if ! command -v rustup >/dev/null; then
  curl -fsSL --proto '=https' --tlsv1.2 https://sh.rustup.rs -o .lab-cache/install-rustup.sh
  sh .lab-cache/install-rustup.sh -y --default-toolchain none --no-modify-path </dev/null
fi
if ! rustup run stable rustc --version >/dev/null 2>&1; then
  rustup toolchain install stable --profile minimal
fi
rust_version="$(rustup run stable rustc --version)"
rust_version="${rust_version#rustc }"
export VOICE_LAB_RUST="${rust_version%% *}"
if ! rustup run "$VOICE_LAB_RUST" rustc --version >/dev/null 2>&1; then
  rustup toolchain install "$VOICE_LAB_RUST" --profile minimal
fi
rustup component add --toolchain "$VOICE_LAB_RUST" rustfmt clippy
cargo "+$VOICE_LAB_RUST" --version

if ! rustup run nightly rustc --version >/dev/null 2>&1; then
  rustup toolchain install nightly --profile minimal ||
    echo "Nightly setup failed. The fuzz check may be blocked." >&2
fi
for tool in cargo-fuzz cargo-deny kani-verifier; do
  bin="$tool"
  [[ "$tool" != kani-verifier ]] || bin=cargo-kani
  if [[ ! -x "$CARGO_HOME/bin/$bin" ]]; then
    cargo "+$VOICE_LAB_RUST" install --locked --root "$CARGO_HOME" "$tool" ||
      printf 'Tool setup failed for %s. The related check may be blocked.\n' "$tool" >&2
  fi
done
if [[ -x "$CARGO_HOME/bin/cargo-kani" ]]; then
  cargo kani setup || echo "Kani setup failed. The proof check may be blocked." >&2
fi

codex -a never exec --model gpt-6.1-sol --sandbox workspace-write \
  -c 'model_provider="openai"' \
  -c 'model_reasoning_effort="xhigh"' \
  -c 'forced_login_method="chatgpt"' \
  -c 'sandbox_workspace_write.network_access=true' - <<'CODEX_TASK'
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
CODEX_TASK

test -x ./lab
./lab help
report="$(mktemp -d "$PWD/.lab-runs/run.XXXXXXXX")"
printf '\nRun reports: %s\n' "$report"
watch_status=0
./lab watch --out "$report" || watch_status=$?
python3 - "$report" "$watch_status" <<'VERIFY_RESULT'
import json
from pathlib import Path
import sys

report = Path(sys.argv[1])
if int(sys.argv[2]):
    sys.exit(f"FAIL. See the results in {report}")

groups = (
    "unit", "protocol", "codec", "isolation", "fuzz",
    "kani", "dependencies", "timing", "dashboard",
)
artifacts = (
    "timing.json", "events.ndjson", "dashboard.html",
    "alice-received.wav", "bob-received.wav",
)
try:
    result = json.loads((report / "verdict.json").read_text())
    bad_groups = [name for name in groups if result.get(name) != "pass"]
    missing = [name for name in artifacts
               if not (report / name).is_file() or not (report / name).stat().st_size]
except (OSError, ValueError, AttributeError) as error:
    sys.exit(f"FAIL. Invalid verification report in {report}: {error}")
if bad_groups or missing:
    sys.exit(f"FAIL. Nonpassing groups: {bad_groups}. Missing files: {missing}. See {report}")
print(f"PASS. All required software checks passed. Reports: {report}")
VERIFY_RESULT
VOICE_LAB