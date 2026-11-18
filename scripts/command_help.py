"""Shared, standard-library-only command parsers and terminal manuals.

Help must work without Rust, Renode, the private Python environment or a live
dashboard. Runtime launchers use these same parsers so options do not drift.
"""
import argparse
from pathlib import Path
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
FORMAT = argparse.RawDescriptionHelpFormatter


def text(value):
    return textwrap.dedent(value).strip()


def command(sub, topics, name, summary, description, examples):
    parser = sub.add_parser(
        name, help=summary, description=text(description),
        epilog="Examples:\n" + textwrap.indent(text(examples), "  "),
        formatter_class=FORMAT,
    )
    topics[name] = parser
    return parser


def finish(parser, sub, topics, program):
    helper = sub.add_parser(
        "help", help="read the main help or a command's detailed help",
        description="Show help only. No build, test, emulator or server is started.",
        formatter_class=FORMAT,
    )
    helper.add_argument("topic", nargs="?", choices=tuple(topics),
                        help=f"command to explain, for example: {program} help device"
                        if "device" in topics else f"command to explain, for example: {program} help watch")
    return parser, topics


def show_help(args, parser, topics, field):
    if getattr(args, field) not in (None, "help"):
        return False
    topic = getattr(args, "topic", None)
    (topics[topic] if topic else parser).print_help()
    return True


def firmware_parser():
    parser = argparse.ArgumentParser(
        prog="./firmware-lab", formatter_class=FORMAT,
        description=text("""
            VoiceVault firmware lab: run ARM device code on the simulated C1 board.

            Start here:
              ./firmware-lab ui       Start the local page service and print its URL.
              ./firmware-lab device   Build and run the interactive device prototype.

            Open http://127.0.0.1:8765/firmware in your browser. Keep the device
            terminal running. PAIR -> compare the full fingerprint -> MATCH -> CALL.
            MUTE sends encrypted filler; END stops this call. Restart for another.

            Which program should I use?
              ./lab           Broad voice/security tests in local Linux processes.
              ./firmware-lab  ARM execution, touchscreen and board-model experiments.
            They reuse trusted Rust code but have different test results. A pass
            in one does not mean the other passed. Neither qualifies a real board.
        """),
        epilog=text(f"""
            Common tasks:
              ./firmware-lab device --help       Full device controls and options.
              ./firmware-lab help test           Explain the 14 peripheral scenarios.
              ./firmware-lab screen --stop       Stop the owned device/screen session.
              ./firmware-lab device --self-test  Test pairing, calls, mute and END.
              ./firmware-lab test                Run the separate peripheral suite.

            Practical notes:
              Only one firmware emulator runs at once. Stop it before another run.
              Interactive sessions default to 3600 real seconds. Ctrl+C stops them.
              The page shows progress; commands must be started in a terminal.
              --out chooses a NEW directory; omit it for an automatic run folder.
              Runs: .lab-runs/firmware-lab/  |  Tools/builds: .lab-cache/firmware-lab/

            Important limits:
              PUBLIC TEST KEYS. DO NOT FLASH these SRAM-only development images.
              Device audio is synthetic. The native test peer is a host process.
              Audio deadlines still miss; fixed timing and hardware are unqualified.
              No command buys parts, orders a board or programs physical hardware.

            Beginner guide: {ROOT / 'docs/LABS_GUIDE.md'}
            Command reference: {ROOT / 'hardware/firmware-lab/CLI.md'}
            More detail: ./firmware-lab COMMAND --help or ./firmware-lab help COMMAND
        """),
    )
    sub = parser.add_subparsers(dest="action", metavar="COMMAND")
    topics = {}

    def output(p):
        p.add_argument("--out", type=Path, metavar="NEW_DIR",
                       help="save this run in a directory that does not exist yet; default: a new folder under .lab-runs/firmware-lab")

    p = command(sub, topics, "device", "run the VoiceVault device prototype with pairing and calls", """
        Build and execute the SRAM-only VoiceVault application on the C1 model.
        ARM code draws the screen and reads the modeled touch controller. Bob is
        an independent native test process; its local approval/acceptance is an
        explicit test fixture. The call uses real cryptography and Opus, with
        synthetic audio and public deterministic keys, not private conversations.

        Start the page service with ./firmware-lab ui, then run this command.
        Controls: PAIR, compare all 64 fingerprint digits, MATCH, CALL, MUTE, END.
        One pairing/call is supported per session. Restart for a fresh session.
        The firmware page does not currently play the decoded audio in a browser.

        Stop with Ctrl+C, or ./firmware-lab screen --stop in another terminal.
        --wall-seconds is elapsed host time, not emulated MCU time. Default: 3600;
        allowed device-session range: greater than 0, at most 43200 seconds.

        --self-test drives local test touches and checks the displayed fingerprint,
        signed invitation, hybrid handshake, two-way decoded PCM, mute and END.
        --attack deliberately changes traffic. EXPECTED rejection is success only
        for the named negative test; it is not a production-security verdict.

        PUBLIC TEST KEYS: DO NOT FLASH. Missed audio slots remain visible.
    """, """
        ./firmware-lab ui
        ./firmware-lab device
        ./firmware-lab device --wall-seconds 600
        ./firmware-lab device --self-test --wall-seconds 300
        ./firmware-lab device --self-test --attack tamper --wall-seconds 300
        ./firmware-lab device --self-test --attack downgrade --wall-seconds 300
        ./firmware-lab device --out "$PWD/.lab-runs/firmware-lab/device-01"
    """)
    output(p)
    p.add_argument("--self-test", action="store_true", help="automatically exercise pairing, fingerprint pixels, call establishment, audio, mute and END")
    p.add_argument("--wall-seconds", type=float, default=3600, metavar="SECONDS", help="maximum real elapsed session time; default: 3600, maximum: 43200")
    p.add_argument("--attack", choices=["none", "tamper", "downgrade"], default="none", help="none: normal forwarding; tamper: corrupt/repeat media; downgrade: truncate the hybrid response; default: none")

    p = command(sub, topics, "screen", "run the separate display/touch diagnostic, or stop a session", """
        Run a small ARM display/touch diagnostic on the C1 model. This checks
        SPI display writes and I2C touch reads, including five contacts.
        Its CALL/MUTE buttons are a UI demonstration: no voice call is made.
        Use 'device' for the integrated VoiceVault call application.

        --self-test checks pixels, press/repaint, release, five contact IDs and
        coordinates, and drag. --touch-nack and --bad-width are intentional faults.
        An explicit rejection is expected; a crash is not a passing rejection.

        --elf loads a linked ARM32 executable using the supported bus subset.
        The included diagnostic report/startup checks are not a generic BSP.
        Unsupported clock/peripheral modes still fail. This is not flash loading.

        --stop stops the owned interactive screen OR device session. It does not
        stop unrelated programs or the persistent dashboard service.
    """, """
        ./firmware-lab screen
        ./firmware-lab screen --self-test
        ./firmware-lab screen --self-test --touch-nack
        ./firmware-lab screen --self-test --bad-width
        ./firmware-lab screen --elf /absolute/path/to/your/firmware.elf
        ./firmware-lab screen --stop
    """)
    output(p)
    p.add_argument("--stop", action="store_true", help="stop the currently owned interactive screen/device session; do not start another emulator")
    p.add_argument("--elf", type=Path, metavar="ELF", help="load your linked ARM executable instead of building the screen diagnostic")
    p.add_argument("--self-test", action="store_true", help="run the finite display/touch checks instead of waiting for browser input")
    p.add_argument("--touch-nack", action="store_true", help="inject an unresponsive touch controller; expected-rejection test")
    p.add_argument("--bad-width", action="store_true", help="build the diagnostic with the wrong 8-bit SPI width; expected-rejection test")
    p.add_argument("--wall-seconds", type=float, default=3600, metavar="SECONDS", help="maximum real elapsed interactive time; default: 3600")

    p = command(sub, topics, "test", "run all 14 base peripheral and failure scenarios", """
        Build and run the base C1 model regression suite. Checks cover clocks,
        GPIO/UART, memory transfers and real modeled interrupts; absent clocks,
        invalid addresses, stalled transfers and missing interrupts; chip-identity
        mismatch; explicit digital SAI samples; blocked flash writes; preserved
        SRAM gates; ST's LL DMA driver; and the ngspice RC/reset fixture.

        This command does NOT run the separate device call tests, screen tests,
        or ./lab's eleven-group security suite. Run those separately.
        Negative cases pass only after the intended rejection is observed.
        Results are written to summary.json, per-case report.json and raw logs.
        Stop the interactive device/screen before starting this suite.
    """, """
        ./firmware-lab screen --stop
        ./firmware-lab test
        ./firmware-lab test --out "$PWD/.lab-runs/firmware-lab/base-01"
    """)
    output(p)

    p = command(sub, topics, "run", "execute a diagnostic or your linked ARM ELF for a finite time", """
        Load an ARM32 little-endian executable into declared C1 memory banks and
        run the supported model. With no --elf, build/use the small peripheral
        diagnostic. This does not start the interactive VoiceVault application.

        --seconds is VIRTUAL MCU time; default 0.03, greater than 0 and at most 10.
        This can take longer than that number of seconds on the computer.
        ELF architecture, entry and memory ranges are checked before execution.
        Missing peripheral behavior, unexpected accesses and model errors fail.

        EXECUTED means execution ended without a detected model violation. A custom
        ELF without a checked application report has not proved correctness.
        --report-symbol expects the included nine-field diagnostic report layout;
        it is not an arbitrary success variable or a production validation tool.

        Audio and power flags enable explicit TEST fixtures. They do not model a
        qualified physical codec, regulator, battery or brownout circuit.
    """, """
        ./firmware-lab run
        ./firmware-lab run --elf /absolute/path/to/your/firmware.elf --seconds 0.05
        ./firmware-lab build --features audio-fixture
        ./firmware-lab run --elf /absolute/path/to/audio-diagnostic.elf --audio-fixture
        ./firmware-lab run --power-fixture --seconds 0.03
    """)
    p.add_argument("--elf", type=Path, metavar="ELF", help="linked ARM32 executable; default: build/use the baseline diagnostic")
    p.add_argument("--seconds", type=float, default=.03, metavar="VIRTUAL_SECONDS", help="virtual execution time, greater than 0 and at most 10; default: 0.03")
    p.add_argument("--report-symbol", metavar="SYMBOL", help="symbol for the included nine-field firmware diagnostic report layout")
    output(p)
    p.add_argument("--audio-fixture", action="store_true", help="enable/feed the known-sample digital SAI fixture; use a compatible audio diagnostic ELF")
    p.add_argument("--power-fixture", action="store_true", help="enable the ngspice RC supply/load/reset coupling fixture")

    p = command(sub, topics, "build", "compile a small diagnostic and print its ELF path", """
        Compile the baseline Rust SRAM diagnostic without starting the emulator.
        This command does not build the integrated VoiceVault device application;
        'device' builds its own application and native peer automatically.

        --features selects Rust diagnostic features. Available features include
        touchscreen, screen-bad-width, audio-fixture, uart-rx, missing-clock,
        unknown-register, bad-dma, flash-write and sram-clock-disable. Several
        deliberately cause rejection: their names are not production features.
        --st-driver builds the independent C diagnostic with ST's LL DMA functions
        instead of the Rust example; Rust --features do not apply in this mode.

        Output: the exact diagnostic ELF path, build log and build.json under
        .lab-cache/firmware-lab/. An ELF is a development executable, not a release.
    """, """
        ./firmware-lab build
        ./firmware-lab build --features touchscreen
        ./firmware-lab build --features audio-fixture
        ./firmware-lab build --st-driver
    """)
    p.add_argument("--features", default="", metavar="FEATURES", help="Rust diagnostic feature name(s), comma-separated; default: baseline with no features")
    p.add_argument("--st-driver", action="store_true", help="compile the ST LL DMA C example using the installed local ARM compiler")

    p = command(sub, topics, "debug", "inspect ARM instructions, memory and breakpoints with GDB", """
        Run GDB against Renode inside a private loopback-only network namespace.
        This debugs the emulated CPU, not a connected physical board. The baseline
        diagnostic is used unless --elf is supplied. Stop other firmware sessions.
        A missing namespace/tool fails instead of exposing a public debug port.

        At the GDB prompt: break FUNCTION, continue, stepi, info registers, and
        x/i $pc inspect execution. Type quit to leave the debugger.
        --smoke performs an automated ST LL DMA interrupt breakpoint check and
        saves gdb.log; it does not leave an interactive debugger running.
    """, """
        ./firmware-lab debug
        ./firmware-lab debug --elf /absolute/path/to/your/firmware.elf
        ./firmware-lab debug --smoke
    """)
    p.add_argument("--elf", type=Path, metavar="ELF", help="linked ARM executable to debug; default: baseline, or ST LL example with --smoke")
    output(p)
    p.add_argument("--smoke", action="store_true", help="automatically verify a DMA interrupt breakpoint, save its log, then exit")

    command(sub, topics, "doctor", "check installed references, target hashes and Renode version", """
        Read/check the configured C1 PCB, wiring, pinned header, SVD and Renode
        version. Print a JSON target/declaration report. No firmware is executed.
        This checks required references, not every possible tool or real hardware.
        If a hash differs, review the target/model mapping; do not edit the lock
        simply to make a failed check disappear.
    """, "./firmware-lab doctor")
    command(sub, topics, "ui", "start the page service if needed and print the firmware URL", """
        Ensure the fixed loopback dashboard service is available, then print
        http://127.0.0.1:8765/firmware. Open that URL in your browser.
        This command starts no emulator, call or test suite. Use 'device',
        'screen' or 'test' in the terminal to produce the activity you want.
        An unrelated application on port 8765 causes an explicit failure;
        the tool does not choose a random replacement port or a public address.
    """, """
        ./firmware-lab ui
        ./firmware-lab device
    """)
    return finish(parser, sub, topics, "./firmware-lab")


def native_parser():
    parser = argparse.ArgumentParser(
        prog="./lab", formatter_class=FORMAT,
        description=text("""
            VoiceVault voice lab: simulate secure calls through hostile phones.

            Two trusted endpoints (Alice and Bob) encode/encrypt synthetic audio.
            Separate Phone A, Phone B and Relay processes carry and attack their
            traffic. The dashboard explains the events and records test outcomes.
            No physical phone, microphone, BLE connection or paid calling API is used.

            First run:
              ./lab demo --seconds 30    Watch two calls: normal and induced faults.
              ./lab watch               Run the full verification with live progress.
              ./lab ui                  Reopen http://127.0.0.1:8765/.

            Use ./firmware-lab for the separate ARM/board-model application and
            touchscreen at /firmware. ./lab does not run the finished device image.
        """),
        epilog=text(f"""
            Before running:
              Use the configured Linux x86-64 development checkout and pinned tools.
              --help starts no tests, build, emulator or dashboard.
              Native --out must be an EMPTY ABSOLUTE directory (or a new one).

            Understanding results:
              demo is a demonstration, not a full security-suite pass.
              test/watch require all eleven groups; missing checks stay BLOCKED.
              Eight fuzz campaigns alone take at least 16 minutes, plus all other
              work. Full-suite duration depends on the machine and cached tools.
              Native process tests do not qualify C1 hardware or production firmware.
              Listen live monitors synthetic audio; scored timing disables that output.

            Results: .lab-runs/ (verdicts, logs, traces, WAVs and saved dashboards).
            Beginner guide: {ROOT / 'docs/LABS_GUIDE.md'}
            Technical setup: {ROOT / 'docs/DEVELOPMENT.md'}
            More detail: ./lab COMMAND --help or ./lab help COMMAND
        """),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    topics = {}
    for name, summary, description, examples in [
        ("demo", "watch short synthetic calls and save the recovered audio", """
            Build the release runner and run two independent full-duplex calls:
            normal forwarding, then deliberate media corruption/loss. The fixed
            dashboard opens and shows actual endpoint events as the calls run.
            --seconds is the duration PER call, not the total build/run time.
            Enable Listen live in the page for decoded synthetic sound; it is off
            by default. No microphone is recorded. This is not the full test suite.
            The output contains WAVs, traces, logs and demo-verdict.json.
        """, """
            ./lab demo
            ./lab demo --seconds 30
            ./lab demo --seconds 30 --out "$PWD/.lab-runs/my-demo-01"
        """),
        ("watch", "run the complete security suite with live dashboard progress", """
            Run the same eleven required groups as 'test', publishing live progress
            at http://127.0.0.1:8765/. Groups: unit, protocol, lifecycle, platform,
            codec, isolation, fuzz, kani, dependencies, timing and dashboard.

            Includes locked builds, vectors/property tests, hostile-process checks,
            eight fuzz campaigns of at least 120 seconds each, five bounded proofs,
            the QEMU Cortex-M33 capacity diagnostic and timing experiments.
            This is substantially longer than demo; fuzzing alone takes 16 minutes.
            Native platform checks use QEMU MPS2 AN505, not the C1 Renode board model.

            Scored timing keeps packet graphics still and disables listening;
            check progress remains visible. Buffered traces are marked recorded.
            PASS requires all groups; FAIL and BLOCKED are preserved in verdict.json.
            Ctrl+C interrupts the run; do not treat partial results as a full pass.
        """, """
            ./lab watch
            ./lab watch --out "$PWD/.lab-runs/full-suite-01"
            ./lab status
        """),
        ("test", "run the same complete suite without the live dashboard", """
            Run all eleven required verification groups, with the same checks,
            fuzz durations and timing gates as 'watch'. This command does not
            start the live dashboard. Saved reports/dashboard artifacts remain
            available afterward. Use watch for live progress or demo for a short call.
            Missing prerequisites produce BLOCKED, not a fabricated pass.
        """, """
            ./lab test
            ./lab test --out "$PWD/.lab-runs/full-suite-02"
            ./lab status
            ./lab replay
        """),
    ]:
        p = command(sub, topics, name, summary, description, examples)
        p.add_argument("--out", metavar="ABS_DIR", help="save artifacts in an empty absolute directory; default: a new directory under .lab-runs")
        if name == "demo":
            p.add_argument("--seconds", type=int, choices=range(8,31), default=8, metavar="8..30", help="seconds for EACH of the two live calls; default: 8, allowed: 8 through 30")
    command(sub, topics, "ui", "open the native lab's persistent dashboard", """
        Ensure the local dashboard service exists and open/print
        http://127.0.0.1:8765/. This does not start calls or rerun tests.
        The page shows the latest published native run, which may be historical
        or interrupted. Use demo or watch to start fresh activity.
    """, "./lab ui")
    command(sub, topics, "status", "read the most recent full-suite verdict", """
        Read the latest full verification run's verdict.json and print PASS,
        FAIL or BLOCKED for all required groups, with failure reasons/log paths.
        No test is rerun. A recent demo does not become a full-suite verdict.
        With no saved full run yet, start test/watch first. Exit status is zero
        only when all required groups in that saved verdict passed.
    """, """
        ./lab status
        ./lab watch
    """)
    p = command(sub, topics, "replay", "open a saved offline dashboard without rerunning tests", """
        Open dashboard.html from a saved run or a supplied HTML file. With no
        argument, use the latest full run. Pause/filter/step through saved events.
        Replay is historical: it neither makes a fresh call nor creates new passes.
    """, """
        ./lab replay
        ./lab replay /absolute/path/to/a/saved/run
        ./lab replay /absolute/path/to/dashboard.html
    """)
    p.add_argument("run", nargs="?", help="saved run directory or dashboard.html; default: latest full run")
    return finish(parser, sub, topics, "./lab")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    family = argv.pop(0) if argv else "firmware"
    if family not in ("firmware", "native"):
        raise SystemExit("Choose firmware or native help")
    parser, topics = firmware_parser() if family == "firmware" else native_parser()
    args = parser.parse_args(argv)
    field = "action" if family == "firmware" else "command"
    if not show_help(args, parser, topics, field):
        topics[getattr(args, field)].print_help()


if __name__ == "__main__":
    main()
