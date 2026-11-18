# ./lab command reference

For a plain-language walkthrough, read [Using both labs](LABS_GUIDE.md).

The following help is generated from `scripts/command_help.py`, the same command definitions used by the local launchers. `YOUR_CHECKOUT` stands for the checkout folder. Asking for help starts no build, test, emulator or server.

## Contents

- [Main help](#main-help)
- [demo](#demo)
- [watch](#watch)
- [test](#test)
- [ui](#ui)
- [status](#status)
- [replay](#replay)

## Main help

```text
usage: ./lab [-h] COMMAND ...

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

positional arguments:
  COMMAND
    demo      watch short synthetic calls and save the recovered audio
    watch     run the complete security suite with live dashboard progress
    test      run the same complete suite without the live dashboard
    ui        open the native lab's persistent dashboard
    status    read the most recent full-suite verdict
    replay    open a saved offline dashboard without rerunning tests
    help      read the main help or a command's detailed help

options:
  -h, --help  show this help message and exit

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
Beginner guide: YOUR_CHECKOUT/docs/LABS_GUIDE.md
Technical setup: YOUR_CHECKOUT/docs/DEVELOPMENT.md
More detail: ./lab COMMAND --help or ./lab help COMMAND
```

## demo

```text
usage: ./lab demo [-h] [--out ABS_DIR] [--seconds 8..30]

Build the release runner and run two independent full-duplex calls:
normal forwarding, then deliberate media corruption/loss. The fixed
dashboard opens and shows actual endpoint events as the calls run.
--seconds is the duration PER call, not the total build/run time.
Enable Listen live in the page for decoded synthetic sound; it is off
by default. No microphone is recorded. This is not the full test suite.
The output contains WAVs, traces, logs and demo-verdict.json.

options:
  -h, --help       show this help message and exit
  --out ABS_DIR    save artifacts in an empty absolute directory; default: a
                   new directory under .lab-runs
  --seconds 8..30  seconds for EACH of the two live calls; default: 8,
                   allowed: 8 through 30

Examples:
  ./lab demo
  ./lab demo --seconds 30
  ./lab demo --seconds 30 --out "$PWD/.lab-runs/my-demo-01"
```

## watch

```text
usage: ./lab watch [-h] [--out ABS_DIR]

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

options:
  -h, --help     show this help message and exit
  --out ABS_DIR  save artifacts in an empty absolute directory; default: a new
                 directory under .lab-runs

Examples:
  ./lab watch
  ./lab watch --out "$PWD/.lab-runs/full-suite-01"
  ./lab status
```

## test

```text
usage: ./lab test [-h] [--out ABS_DIR]

Run all eleven required verification groups, with the same checks,
fuzz durations and timing gates as 'watch'. This command does not
start the live dashboard. Saved reports/dashboard artifacts remain
available afterward. Use watch for live progress or demo for a short call.
Missing prerequisites produce BLOCKED, not a fabricated pass.

options:
  -h, --help     show this help message and exit
  --out ABS_DIR  save artifacts in an empty absolute directory; default: a new
                 directory under .lab-runs

Examples:
  ./lab test
  ./lab test --out "$PWD/.lab-runs/full-suite-02"
  ./lab status
  ./lab replay
```

## ui

```text
usage: ./lab ui [-h]

Ensure the local dashboard service exists and open/print
http://127.0.0.1:8765/. This does not start calls or rerun tests.
The page shows the latest published native run, which may be historical
or interrupted. Use demo or watch to start fresh activity.

options:
  -h, --help  show this help message and exit

Examples:
  ./lab ui
```

## status

```text
usage: ./lab status [-h]

Read the latest full verification run's verdict.json and print PASS,
FAIL or BLOCKED for all required groups, with failure reasons/log paths.
No test is rerun. A recent demo does not become a full-suite verdict.
With no saved full run yet, start test/watch first. Exit status is zero
only when all required groups in that saved verdict passed.

options:
  -h, --help  show this help message and exit

Examples:
  ./lab status
  ./lab watch
```

## replay

```text
usage: ./lab replay [-h] [run]

Open dashboard.html from a saved run or a supplied HTML file. With no
argument, use the latest full run. Pause/filter/step through saved events.
Replay is historical: it neither makes a fresh call nor creates new passes.

positional arguments:
  run         saved run directory or dashboard.html; default: latest full run

options:
  -h, --help  show this help message and exit

Examples:
  ./lab replay
  ./lab replay /absolute/path/to/a/saved/run
  ./lab replay /absolute/path/to/dashboard.html
```

## Help command

Use `./lab help` for the main page and `./lab help COMMAND` for one command. `./lab COMMAND --help` has the same detailed help. Type the program name before `--help`.
