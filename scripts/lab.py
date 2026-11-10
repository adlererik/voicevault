"""Suite orchestration and report generation. All calls themselves run in Rust."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib

from dashboard import GROUPS, Server, Trace, case_events, check_mapping, page, trace

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".lab-cache"
RUNS = ROOT / ".lab-runs"
RUNNER = ROOT / "target/release/lab-runner"
FUZZ_NIGHTLY = "nightly-2026-08-21"
OPUS_VERSION = "1.6.1"
SOURCE_HASH = "6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1"
VECTOR_HASH = "6b26a22f9ba87b2b836906a9bb7afec5f8e54d49553b1200382520ee6fedfa55"
VECTOR_URL = "https://opus-codec.org/docs/opus_testvectors-rfc8251.tar.gz"
EXPECTED = {
    "unit": "formatting, Clippy, Rust unit tests and release build",
    "protocol": "Noise vector, protocol integration, proptest and virtual attacks",
    "codec": "CBR and framing tests, libopus interop and RFC 8251 decoder vectors",
    "isolation": "all hostile roles restricted to inherited IPC",
    "fuzz": "six instrumented targets, at least 120 seconds each",
    "kani": "four replay, consent, closed-call and monotonic-version harnesses verified",
    "lifecycle": "enrollment, invitation, storage, entropy, offline update and radio fault tests",
    "platform": "linked no_std Cortex-M33 voice and policy diagnostic, memory gates and QEMU execution",
    "dependencies": "locked graphs pass advisory, bans, license and source checks",
    "timing": "30 seconds each idle and contention, plus overload and blocked phone",
    "dashboard": "read-only loopback stream, pause/resume and offline verdict mapping",
}


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def report_directory(value, kind):
    if value is None:
        return Path(tempfile.mkdtemp(prefix=f"{kind}.", dir=RUNS))
    directory = Path(value)
    if not directory.is_absolute():
        raise ValueError("--out requires an absolute directory")
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("--out must be empty so every artifact belongs to this run")
    return directory.resolve()


def open_browser(url):
    browser = shutil.which("xdg-open")
    if browser and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            subprocess.Popen([browser, url], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as error:
            print(f"Browser opener unavailable ({error})", file=sys.stderr)


class Suite:
    def __init__(self, out):
        self.out = out
        self.logs = out / "logs"
        self.logs.mkdir()
        self.model = Trace()
        self.groups = {group: [] for group in GROUPS}
        self.details = {}
        self.event_errors = []
        self.server = None
        self.env = os.environ.copy()
        self.env.update(CARGO_TERM_COLOR="never", RUST_BACKTRACE="1", PROPTEST_RNG_SEED="870321")

    def run(self, group, name, command, *, needs=(), timeout=120, events=False,
            cwd=ROOT, accept=None, unavailable=None, env=None):
        missing = [tool for tool in needs if not shutil.which(tool)]
        if unavailable or missing:
            reason = unavailable or f"missing {', '.join(missing)}"
            return self.record(group, name, "blocked", reason)
        logfile = self.logs / f"{name}.log"
        print(f"  RUN     {name}", flush=True)
        self.model.add(trace(name, "check", EXPECTED.get(group, "complete check"), "Running"))
        with logfile.open("wb") as log:
            log.write((f"$ {shlex.join(map(str, command))}\n").encode())
            log.flush()
            try:
                process = subprocess.Popen(command, cwd=cwd, env=env or self.env,
                                           stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as error:
                log.write(f"{error}\n".encode())
                return self.record(group, name, "blocked", str(error), logfile)
            try:
                result = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                log.write(f"Command interrupted or exceeded {timeout} seconds\n".encode())
                if isinstance(error, KeyboardInterrupt):
                    raise
                return self.record(group, name, "fail", f"timeout ({timeout}s)", logfile)
        contents = logfile.read_text(errors="replace")
        for event in case_events(name, contents):
            self.model.add(event)
        if events:
            for line in contents.splitlines():
                if line.startswith("{"):
                    try:
                        self.model.add(json.loads(line))
                    except ValueError as error:
                        self.event_errors.append(f"{name}: {error}")
        if result != 0:
            diagnostic = next((line.strip() for line in reversed(contents.splitlines()[1:])
                               if line.strip() and not line.startswith("{")), "")
            reason = f"exit {result}" + (f" ({diagnostic[:220]})" if diagnostic else "")
            missing_tool = ("is not installed" in contents or "no such command:" in contents
                            or "run `cargo kani setup`" in contents)
            return self.record(group, name, "blocked" if missing_tool else "fail", reason, logfile)
        if accept and not accept(contents):
            return self.record(group, name, "fail", "required result evidence missing", logfile)
        return self.record(group, name, "pass", "completed successfully", logfile)

    def record(self, group, name, status, reason, logfile=None):
        entry = {"check": name, "status": status, "reason": reason,
                 "log": str(logfile.relative_to(self.out)) if logfile else None}
        if group:
            self.groups[group].append(entry)
        self.model.add(trace(name, "check", EXPECTED.get(group, "complete check"), reason[:400], status))
        print(f"  {status.upper():7} {name} · {reason}", flush=True)
        return status == "pass"

    def summary(self, group):
        checks = self.groups[group]
        status = next((state for state in ("fail", "blocked")
                       if any(check["status"] == state for check in checks)), "pass")
        failures = [f'{item["check"]}: {item["reason"]}' for item in checks if item["status"] != "pass"]
        reason = "; ".join(failures) or f"{len(checks)} checks passed"
        return {"status": status, "reason": reason, "checks": checks}

    def finish_group(self, group):
        detail = self.summary(group)
        self.details[group] = detail
        self.model.add(trace(group, "group", EXPECTED[group], detail["reason"][:400], detail["status"]))

    def verdict(self):
        return {key: self.details[key]["status"] for key in GROUPS} | {
            "schema": 1, "details": self.details,
        }

    def artifacts(self):
        result = self.verdict()
        check_mapping(self.model.events, result)
        (self.out / "events.ndjson").write_text(
            "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in self.model.events))
        (self.out / "dashboard.html").write_text(page(self.model.events))
        write_json(self.out / "verdict.json", result)
        pointer = RUNS / "latest"
        temporary = RUNS / "latest.tmp"
        temporary.write_text(str(self.out) + "\n")
        temporary.replace(pointer)
        return result


def prepare_reference(suite):
    archive = ROOT / "vendor" / f"opus-{OPUS_VERSION}.tar.gz"
    root = CACHE / "reference"
    source = root / f"opus-{OPUS_VERSION}"
    marker = source / ".lab-reference-built"
    logfile = suite.logs / "reference-source.log"
    try:
        if sha256(archive) != SOURCE_HASH:
            raise ValueError("vendored libopus SHA-256 mismatch")
        logfile.write_text(f"{SOURCE_HASH}  {archive.name}\n")
        suite.record("codec", "reference-source", "pass", "verified vendored libopus", logfile)
        if not marker.is_file() or not all((source / name).is_file() for name in ("opus_demo", "opus_compare")):
            root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive) as package:
                package.extractall(root, filter="data")
            configured = suite.run("codec", "reference-configure",
                                   ["./configure", "--disable-shared", "--disable-doc"],
                                   needs=("cc", "make", "ar"), timeout=180, cwd=source)
            built = suite.run("codec", "reference-build", ["make", "-j2", "opus_demo", "opus_compare"],
                              timeout=300, cwd=source,
                              unavailable=None if configured else "reference configure did not pass")
            if not built:
                return None
            marker.write_text(SOURCE_HASH)
        else:
            suite.record("codec", "reference-build", "pass", "using local build of verified source", logfile)
        return source
    except (OSError, ValueError, tarfile.TarError) as error:
        logfile.write_text(str(error))
        suite.record("codec", "reference-source", "fail", str(error), logfile)
        return None


def prepare_vectors(suite):
    download = CACHE / "downloads" / "opus_testvectors-rfc8251.tar.gz"
    if not download.is_file():
        download.parent.mkdir(parents=True, exist_ok=True)
        partial = download.with_suffix(".partial")
        fetched = suite.run("codec", "vector-download", [
            "curl", "-fsSL", "--proto", "=https", "--retry", "2", VECTOR_URL, "-o", partial,
        ], needs=("curl",), timeout=240)
        if not fetched:
            return None
        partial.replace(download)
    logfile = suite.logs / "vector-source.log"
    try:
        if sha256(download) != VECTOR_HASH:
            raise ValueError("official vector archive SHA-256 mismatch")
        root = CACHE / "vectors"
        vectors = root / "opus_newvectors"
        if not all((vectors / f"testvector{i:02}{suffix}").is_file()
                   for i in range(1, 13) for suffix in (".bit", ".dec", "m.dec")):
            root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(download) as package:
                package.extractall(root, filter="data")
        logfile.write_text(f"{VECTOR_HASH}  {VECTOR_URL}\n")
        suite.record("codec", "vector-source", "pass", "verified official RFC 8251 vectors", logfile)
        return vectors
    except (OSError, ValueError, tarfile.TarError) as error:
        logfile.write_text(str(error))
        suite.record("codec", "vector-source", "fail", str(error), logfile)
        return None


def timing(suite, blocked):
    scenarios = {}
    if not blocked:
        suite.model.set_phase("timing")
        if suite.server:
            time.sleep(0.35)
    try:
        for mode in ("idle", "contention", "overload", "blocked-phone"):
            directory = suite.out / "timing" / mode
            passed = suite.run("timing", f"timing-{mode}", [RUNNER, "wall", directory, mode],
                               timeout=55, events=True, unavailable=blocked)
            metrics = directory / "metrics.json"
            check = suite.groups["timing"][-1]
            if metrics.is_file():
                scenarios[mode] = json.loads(metrics.read_text())
                if not passed:
                    check["reason"] = ", ".join(scenarios[mode]["reasons"]) or check["reason"]
                if mode == "idle":
                    for who in ("alice", "bob"):
                        shutil.copyfile(directory / f"{who}-received.wav", suite.out / f"{who}-received.wav")
            else:
                scenarios[mode] = {"status": check["status"], "reason": check["reason"]}
    finally:
        suite.model.set_phase("live")
    cpuinfo = Path("/proc/cpuinfo")
    model = next((line.partition(":")[2].strip() for line in cpuinfo.read_text().splitlines()
                  if line.startswith("model name")), "unknown") if cpuinfo.is_file() else "unknown"
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    pin = tomllib.loads((ROOT / "rust-toolchain.toml").read_text())["toolchain"]["channel"]
    write_json(suite.out / "timing.json", {
        "schema": 1, "host": {"kernel": platform.release(), "architecture": platform.machine(),
                              "cpu_model": model, "logical_cpus": os.cpu_count(),
                              "rust_pin": pin, "cpu_quota": cpu_max.read_text().strip() if cpu_max.is_file() else None},
        "thresholds": {"p99_absolute_send_error_ns": 5_000_000, "missed_fraction": 0.001,
                       "overload_catch_up_bursts": 0, "jitter_records": 8, "fragment_assemblies": 8},
        "scenarios": scenarios,
    })


def fuzz(suite):
    tools = ("rustup", "cargo", "cargo-fuzz")
    env = suite.env | {"CARGO_TARGET_DIR": str(ROOT / "fuzz/target")}
    locked = suite.run("fuzz", "fuzz-locked-graph", [
        "cargo", f"+{FUZZ_NIGHTLY}", "metadata", "--locked", "--manifest-path", "fuzz/Cargo.toml",
        "--format-version", "1",
    ], needs=tools, env=env)
    lock = ROOT / "fuzz/Cargo.lock"
    before = sha256(lock)
    blocked = None if locked else "locked fuzz graph unavailable"
    if not env.get("CXX") and (CACHE / "zig/zig").is_file():
        ready = suite.run("fuzz", "fuzz-cxx-runtime", [ROOT / "scripts/zig-runtime"],
                          timeout=300, unavailable=blocked)
        if ready:
            env["CXX"] = str(ROOT / "scripts/zig-cxx")
            env["LIBRARY_PATH"] = os.pathsep.join(filter(None, [str(CACHE / "cxx-runtime"), env.get("LIBRARY_PATH")]))
        else:
            blocked = blocked or "local Zig C++ runtime did not build"
    for target in ("handshake", "record", "codec", "enrollment", "lifecycle", "update-radio"):
        corpus = suite.out / "fuzz" / "corpus" / target
        crashes = suite.out / "fuzz" / "artifacts" / target
        if not blocked:
            shutil.copytree(ROOT / "fuzz" / "corpus" / target, corpus)
            crashes.mkdir(parents=True)
        suite.run("fuzz", f"fuzz-{target}", [
            "cargo", f"+{FUZZ_NIGHTLY}", "fuzz", "run", target, corpus, "--",
            "-max_total_time=120", "-timeout=5", "-max_len=512", "-seed=870321",
            f"-artifact_prefix={crashes}/",
        ], timeout=300, unavailable=blocked, env=env,
            accept=lambda log: any(int(n) >= 120 for n in re.findall(r"Done \d+ runs in (\d+) second", log)))
    unchanged = sha256(lock) == before
    suite.record("fuzz", "fuzz-lock-integrity", "pass" if unchanged else "fail",
                 "fuzz Cargo.lock unchanged" if unchanged else "fuzz tool changed Cargo.lock")


def table(report, out):
    print(f"\n{'Group':14} {'Verdict':8} Reason and diagnostic logs")
    print("-" * 72)
    for key in GROUPS:
        detail = report["details"][key]
        print(f"{key:14} {report[key].upper():8} {detail['reason']}")
        relevant = [item for item in detail["checks"] if item["status"] != "pass"]
        logs = [item["log"] for item in (relevant or detail["checks"]) if item["log"]]
        if logs:
            print(f"{'':23} {', '.join(logs)}")
    print(f"\nReport directory {out}")


def suite_run(out, watch):
    suite = Suite(out)
    print(f"Run directory {out}", flush=True)
    watch_error = None
    if watch:
        try:
            suite.server = Server(suite.model)
            suite.server.start()
            print(f"Dashboard {suite.server.url}", flush=True)
            open_browser(suite.server.url)
        except OSError as error:
            watch_error = f"loopback dashboard unavailable ({error})"
    try:
        suite.run("unit", "format", ["cargo", "fmt", "--all", "--", "--check"], needs=("cargo",))
        suite.run("unit", "format-fuzz", ["cargo", "fmt", "--manifest-path", "fuzz/Cargo.toml", "--", "--check"], needs=("cargo",))
        suite.run("unit", "format-platform", ["cargo", "fmt", "--manifest-path", "platform/Cargo.toml", "--", "--check"], needs=("cargo",))
        suite.run("unit", "clippy", ["cargo", "clippy", "--locked", "--workspace", "--all-targets",
                                    "--", "-D", "warnings"], needs=("cargo",), timeout=240)
        suite.run("unit", "unit", ["cargo", "test", "--locked", "--workspace", "--lib", "--bins"],
                  needs=("cargo",), timeout=240)
        built = suite.run("unit", "release-build", ["cargo", "build", "--locked", "--release", "-p", "lab-runner"],
                          needs=("cargo",), timeout=300)
        suite.finish_group("unit")
        unavailable = None if built else "release runner did not build"

        suite.run("protocol", "protocol-tests", ["cargo", "test", "--locked", "-p", "protocol", "--test", "security", "--test", "vectors"],
                  needs=("cargo",), timeout=240)
        suite.run("protocol", "virtual", [RUNNER, "virtual"], events=True, unavailable=unavailable)
        suite.finish_group("protocol")
        suite.run("lifecycle", "lifecycle-tests", ["cargo", "test", "--locked", "-p", "protocol", "--test", "lifecycle"],
                  needs=("cargo",), timeout=240)
        suite.finish_group("lifecycle")
        suite.run("platform", "m33-linked-execution", [sys.executable,ROOT/"scripts/platform_check.py",out/"platform"],
                  needs=("cargo",), timeout=300)
        suite.finish_group("platform")

        isolated = suite.run("isolation", "isolation", [RUNNER, "isolation"], events=True, unavailable=unavailable)
        suite.finish_group("isolation")
        timing(suite, unavailable or (None if isolated else "hostile process isolation did not pass"))
        suite.finish_group("timing")

        suite.run("codec", "codec-unit", ["cargo", "test", "--locked", "-p", "codec"], needs=("cargo",))
        suite.run("codec", "vendor-port-integrity", [sys.executable, ROOT/"scripts/check_vendor.py"])
        suite.run("codec", "inplace-constructor", ["cargo", "test", "--locked", "-p", "codec", "--no-default-features",
                                                    "in_place_matches_upstream_constructor"], needs=("cargo",),timeout=180)
        reference = prepare_reference(suite)
        vectors = prepare_vectors(suite)
        codec_blocked = unavailable or (None if reference else "libopus reference unavailable")
        suite.run("codec", "opus-interop", [RUNNER, "interop", reference, out / "interop"],
                  unavailable=codec_blocked)
        suite.run("codec", "opus-vectors", [RUNNER, "vectors", reference, vectors, out / "vectors"],
                  unavailable=codec_blocked or (None if vectors else "RFC 8251 archive unavailable"), timeout=240)
        suite.finish_group("codec")

        suite.run("dependencies", "cargo-deny", ["cargo", "deny", "--locked", "check"],
                  needs=("cargo", "cargo-deny"), timeout=240)
        suite.run("dependencies", "cargo-deny-fuzz", ["cargo", "deny", "--locked", "--manifest-path",
                                                    "fuzz/Cargo.toml", "check"],
                  needs=("cargo", "cargo-deny"), timeout=240)
        suite.run("dependencies", "cargo-deny-platform", ["cargo", "deny", "--locked", "--manifest-path",
                                                         "platform/Cargo.toml", "check"],
                  needs=("cargo", "cargo-deny"), timeout=240)
        suite.finish_group("dependencies")

        before = sha256(ROOT / "Cargo.lock")
        suite.run("kani", "kani-locked-graph", ["cargo", "metadata", "--locked", "--format-version", "1"],
                  needs=("cargo",), timeout=120)
        suite.run("kani", "kani", ["cargo", "kani", "-p", "call-state"],
                  needs=("cargo", "cargo-kani"), timeout=240,
                  accept=lambda log: "4 successfully verified harnesses, 0 failures, 4 total" in log)
        suite.record("kani", "kani-lock-integrity", "pass" if sha256(ROOT / "Cargo.lock") == before else "fail",
                     "Cargo.lock unchanged" if sha256(ROOT / "Cargo.lock") == before else "Kani changed Cargo.lock")
        suite.finish_group("kani")

        fuzz(suite)
        suite.finish_group("fuzz")

        suite.run("dashboard", "dashboard", [sys.executable, ROOT / "scripts/dashboard.py"], timeout=20,
                  unavailable=watch_error)
        mapping_log = suite.logs / "dashboard-mapping.log"
        try:
            if suite.event_errors:
                raise ValueError("; ".join(suite.event_errors))
            status = suite.summary("dashboard")["status"]
            provisional = {key: suite.details[key]["status"] for key in suite.details} | {"dashboard": status}
            candidate = trace("dashboard", "group", EXPECTED["dashboard"], "validating final report", status)
            check_mapping([*suite.model.events, candidate], provisional)
            mapping_log.write_text("Actual event stream and CLI verdicts agree.\n")
            suite.record("dashboard", "dashboard-mapping", "pass", "actual report mapping matches", mapping_log)
        except ValueError as error:
            mapping_log.write_text(str(error))
            suite.record("dashboard", "dashboard-mapping", "fail", str(error), mapping_log)
        suite.finish_group("dashboard")
        report = suite.artifacts()
        suite.model.set_phase("done")
        if suite.server:
            time.sleep(0.5)
        table(report, out)
        return 0 if all(report[key] == "pass" for key in GROUPS) else 1
    finally:
        if suite.server:
            suite.server.stop()


def latest():
    pointer = RUNS / "latest"
    if not pointer.is_file():
        raise ValueError("No completed full run. Run ./lab test or ./lab watch first.")
    return Path(pointer.read_text().rstrip("\n"))


def main():
    parser = argparse.ArgumentParser(prog="./lab", description="Local secure voice simulation and verification")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.add_parser("help", help="show this usage")
    for name, message in [("test", "run the full automated suite"),
                          ("watch", "run the same suite with the loopback dashboard"),
                          ("demo", "run a short isolated call and save WAVs")]:
        command = commands.add_parser(name, help=message)
        command.add_argument("--out", metavar="ABS_DIR", help="write to an empty absolute directory")
    commands.add_parser("status", help="show the last full suite verdict and failure reasons")
    replay = commands.add_parser("replay", help="open a saved offline dashboard")
    replay.add_argument("run", nargs="?", help="run directory or dashboard.html, defaults to last run")
    args = parser.parse_args()
    if args.command in (None, "help"):
        parser.print_help()
        return 0
    if args.command == "status":
        directory = latest()
        result = json.loads((directory / "verdict.json").read_text())
        table(result, directory)
        return 0 if all(result[key] == "pass" for key in GROUPS) else 1
    if args.command == "replay":
        saved = Path(args.run).resolve() if args.run else latest()
        html = saved / "dashboard.html" if saved.is_dir() else saved
        if not html.is_file():
            raise ValueError(f"Offline dashboard not found at {html}")
        print(html.as_uri(), flush=True)
        open_browser(html.as_uri())
        return 0

    RUNS.mkdir(exist_ok=True)
    with (RUNS / "suite.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        out = report_directory(args.out, args.command)
        if args.command != "demo":
            return suite_run(out, args.command == "watch")
        suite = Suite(out)
        if not suite.run(None, "demo-build", ["cargo", "build", "--locked", "--release", "-p", "lab-runner"],
                         needs=("cargo",), timeout=300):
            return 1
        if not suite.run(None, "demo", [RUNNER, "wall", out, "demo"], timeout=18, events=True):
            return 1
        print(f"WAVs saved in {out}")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(f"./lab: {error}")
