# ./firmware-lab command reference

For a plain-language walkthrough, read [Using both labs](../../docs/LABS_GUIDE.md).

**Availability:** this reference describes the configured local C1 firmware laboratory. This documentation update does not publish its executable runtime, board snapshot or cached tools. A fresh GitHub clone cannot run that lab until those components are released and configured.

The following help is generated from `scripts/command_help.py`, the same command definitions used by the local launchers. `YOUR_CHECKOUT` stands for the checkout folder. Asking for help starts no build, test, emulator or server.

## Contents

- [Main help](#main-help)
- [device](#device)
- [screen](#screen)
- [test](#test)
- [run](#run)
- [build](#build)
- [debug](#debug)
- [doctor](#doctor)
- [ui](#ui)

## Main help

```text
usage: ./firmware-lab [-h] COMMAND ...

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

positional arguments:
  COMMAND
    device    run the VoiceVault device prototype with pairing and calls
    screen    run the separate display/touch diagnostic, or stop a session
    test      run all 14 base peripheral and failure scenarios
    run       execute a diagnostic or your linked ARM ELF for a finite time
    build     compile a small diagnostic and print its ELF path
    debug     inspect ARM instructions, memory and breakpoints with GDB
    doctor    check installed references, target hashes and Renode version
    ui        start the page service if needed and print the firmware URL
    help      read the main help or a command's detailed help

options:
  -h, --help  show this help message and exit

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

Beginner guide: YOUR_CHECKOUT/docs/LABS_GUIDE.md
Command reference: YOUR_CHECKOUT/hardware/firmware-lab/CLI.md
More detail: ./firmware-lab COMMAND --help or ./firmware-lab help COMMAND
```

## device

```text
usage: ./firmware-lab device [-h] [--out NEW_DIR] [--self-test | --auto-call]
                             [--wall-seconds SECONDS]
                             [--attack {none,tamper,downgrade}]

Build and execute the SRAM-only VoiceVault application on the C1 model.
ARM code draws the screen and reads the modeled touch controller. Bob is
an independent native test process; its local approval/acceptance is an
explicit test fixture. The call uses real cryptography and Opus, with
synthetic audio and public deterministic keys, not private conversations.

Start the page service with ./firmware-lab ui, then run this command.
Controls: PAIR, compare all 64 fingerprint digits, MATCH, CALL, MUTE, END.
One pairing/call is supported per session. Restart for a fresh session.
Click Listen to hear buffered, actual received speech. Choose the ARM
device or native test peer. The emulator can run slower than real time;
this monitor is not a latency measurement. Received WAVs remain afterward.
--auto-call verifies the fixture pairing and starts a call automatically,
then leaves it running for listening and local MUTE/END controls.

Stop with Ctrl+C, or ./firmware-lab screen --stop in another terminal.
--wall-seconds is elapsed host time, not emulated MCU time. Default: 3600;
allowed device-session range: greater than 0, at most 43200 seconds.

--self-test drives local test touches and checks the displayed fingerprint,
signed invitation, hybrid handshake, two-way decoded PCM, mute and END.
--attack deliberately changes traffic. EXPECTED rejection is success only
for the named negative test; it is not a production-security verdict.

PUBLIC TEST KEYS: DO NOT FLASH. Missed audio slots remain visible.

options:
  -h, --help            show this help message and exit
  --out NEW_DIR         save this run in a directory that does not exist yet;
                        default: a new folder under .lab-runs/firmware-lab
  --self-test           automatically exercise pairing, fingerprint pixels,
                        call establishment, audio, mute and END
  --auto-call           automatically verify test pairing/start a speech call,
                        then leave it running for listening and local controls
  --wall-seconds SECONDS
                        maximum real elapsed session time; default: 3600,
                        maximum: 43200
  --attack {none,tamper,downgrade}
                        none: normal forwarding; tamper: corrupt/repeat media;
                        downgrade: truncate the hybrid response; default: none

Examples:
  ./firmware-lab ui
  ./firmware-lab device
  ./firmware-lab device --auto-call --attack tamper --wall-seconds 600
  ./firmware-lab device --wall-seconds 600
  ./firmware-lab device --self-test --wall-seconds 300
  ./firmware-lab device --self-test --attack tamper --wall-seconds 300
  ./firmware-lab device --self-test --attack downgrade --wall-seconds 300
  ./firmware-lab device --out "$PWD/.lab-runs/firmware-lab/device-01"
```

## screen

```text
usage: ./firmware-lab screen [-h] [--out NEW_DIR] [--stop] [--elf ELF]
                             [--self-test] [--touch-nack] [--bad-width]
                             [--wall-seconds SECONDS]

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

options:
  -h, --help            show this help message and exit
  --out NEW_DIR         save this run in a directory that does not exist yet;
                        default: a new folder under .lab-runs/firmware-lab
  --stop                stop the currently owned interactive screen/device
                        session; do not start another emulator
  --elf ELF             load your linked ARM executable instead of building
                        the screen diagnostic
  --self-test           run the finite display/touch checks instead of waiting
                        for browser input
  --touch-nack          inject an unresponsive touch controller; expected-
                        rejection test
  --bad-width           build the diagnostic with the wrong 8-bit SPI width;
                        expected-rejection test
  --wall-seconds SECONDS
                        maximum real elapsed interactive time; default: 3600

Examples:
  ./firmware-lab screen
  ./firmware-lab screen --self-test
  ./firmware-lab screen --self-test --touch-nack
  ./firmware-lab screen --self-test --bad-width
  ./firmware-lab screen --elf /absolute/path/to/your/firmware.elf
  ./firmware-lab screen --stop
```

## test

```text
usage: ./firmware-lab test [-h] [--out NEW_DIR]

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

options:
  -h, --help     show this help message and exit
  --out NEW_DIR  save this run in a directory that does not exist yet;
                 default: a new folder under .lab-runs/firmware-lab

Examples:
  ./firmware-lab screen --stop
  ./firmware-lab test
  ./firmware-lab test --out "$PWD/.lab-runs/firmware-lab/base-01"
```

## run

```text
usage: ./firmware-lab run [-h] [--elf ELF] [--seconds VIRTUAL_SECONDS]
                          [--report-symbol SYMBOL] [--out NEW_DIR]
                          [--audio-fixture] [--power-fixture]

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

options:
  -h, --help            show this help message and exit
  --elf ELF             linked ARM32 executable; default: build/use the
                        baseline diagnostic
  --seconds VIRTUAL_SECONDS
                        virtual execution time, greater than 0 and at most 10;
                        default: 0.03
  --report-symbol SYMBOL
                        symbol for the included nine-field firmware diagnostic
                        report layout
  --out NEW_DIR         save this run in a directory that does not exist yet;
                        default: a new folder under .lab-runs/firmware-lab
  --audio-fixture       enable/feed the known-sample digital SAI fixture; use
                        a compatible audio diagnostic ELF
  --power-fixture       enable the ngspice RC supply/load/reset coupling
                        fixture

Examples:
  ./firmware-lab run
  ./firmware-lab run --elf /absolute/path/to/your/firmware.elf --seconds 0.05
  ./firmware-lab build --features audio-fixture
  ./firmware-lab run --elf /absolute/path/to/audio-diagnostic.elf --audio-fixture
  ./firmware-lab run --power-fixture --seconds 0.03
```

## build

```text
usage: ./firmware-lab build [-h] [--features FEATURES] [--st-driver]

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

options:
  -h, --help           show this help message and exit
  --features FEATURES  Rust diagnostic feature name(s), comma-separated;
                       default: baseline with no features
  --st-driver          compile the ST LL DMA C example using the installed
                       local ARM compiler

Examples:
  ./firmware-lab build
  ./firmware-lab build --features touchscreen
  ./firmware-lab build --features audio-fixture
  ./firmware-lab build --st-driver
```

## debug

```text
usage: ./firmware-lab debug [-h] [--elf ELF] [--out NEW_DIR] [--smoke]

Run GDB against Renode inside a private loopback-only network namespace.
This debugs the emulated CPU, not a connected physical board. The baseline
diagnostic is used unless --elf is supplied. Stop other firmware sessions.
A missing namespace/tool fails instead of exposing a public debug port.

At the GDB prompt: break FUNCTION, continue, stepi, info registers, and
x/i $pc inspect execution. Type quit to leave the debugger.
--smoke performs an automated ST LL DMA interrupt breakpoint check and
saves gdb.log; it does not leave an interactive debugger running.

options:
  -h, --help     show this help message and exit
  --elf ELF      linked ARM executable to debug; default: baseline, or ST LL
                 example with --smoke
  --out NEW_DIR  save this run in a directory that does not exist yet;
                 default: a new folder under .lab-runs/firmware-lab
  --smoke        automatically verify a DMA interrupt breakpoint, save its
                 log, then exit

Examples:
  ./firmware-lab debug
  ./firmware-lab debug --elf /absolute/path/to/your/firmware.elf
  ./firmware-lab debug --smoke
```

## doctor

```text
usage: ./firmware-lab doctor [-h]

Read/check the configured C1 PCB, wiring, pinned header, SVD and Renode
version. Print a JSON target/declaration report. No firmware is executed.
This checks required references, not every possible tool or real hardware.
If a hash differs, review the target/model mapping; do not edit the lock
simply to make a failed check disappear.

options:
  -h, --help  show this help message and exit

Examples:
  ./firmware-lab doctor
```

## ui

```text
usage: ./firmware-lab ui [-h]

Ensure the fixed loopback dashboard service is available, then print
http://127.0.0.1:8765/firmware. Open that URL in your browser.
This command starts no emulator, call or test suite. Use 'device',
'screen' or 'test' in the terminal to produce the activity you want.
An unrelated application on port 8765 causes an explicit failure;
the tool does not choose a random replacement port or a public address.

options:
  -h, --help  show this help message and exit

Examples:
  ./firmware-lab ui
  ./firmware-lab device
```

## Help command

Use `./firmware-lab help` for the main page and `./firmware-lab help COMMAND` for one command. `./firmware-lab COMMAND --help` has the same detailed help. Type the program name before `--help`.
