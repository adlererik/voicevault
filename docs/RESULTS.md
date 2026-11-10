# Earlier verification results (before phase two)

This historical native run on 2026-11-10 passed all nine required software groups. The CLI exited zero. The original supplied report verifier also accepted every required status and artifact. A [machine-readable summary](verification-summary.json) records the measured results.

| Group | Result | Checks |
| --- | --- | ---: |
| unit | PASS | 5 |
| protocol | PASS | 2 |
| codec | PASS | 6 |
| isolation | PASS | 1 |
| fuzz | PASS | 6 |
| kani | PASS | 3 |
| dependencies | PASS | 2 |
| timing | PASS | 4 |
| dashboard | PASS | 2 |

The unit group includes formatting of both workspaces, Clippy with warnings denied, unit tests, and the release build. Protocol checks include the Noise KK reference vector, property tests, reconnect/key-direction tests, and deterministic hostile-link scenarios. All 12 applicable RFC 8251 mono decoder vectors passed at 16 kHz, and audio interoperated with libopus in both directions. Kani verified both harnesses on the actual replay and call-state implementation. Both locked dependency graphs passed the advisory, license, bans, and source checks.

## Timing

The host was Fedora Linux 44, kernel `7.2.13-200.fc44.x86_64`, with `Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz` and 8 logical CPUs. The exact stable Rust pin was `1.99.1`. Idle and CPU contention each ran for 30 seconds with 1,500 slots per direction. Both directions met the unchanged gates: p99 absolute send error ≤ 5 ms and missed slots ≤ 0.1%.

| Scenario | Direction | p99 send error (ms) | Missed / scheduled | Catch-up bursts |
| --- | --- | ---: | ---: | ---: |
| idle | Alice → Bob | 0.374 | 0/1500 | 0 |
| idle | Bob → Alice | 0.525 | 0/1500 | 0 |
| contention | Alice → Bob | 2.010 | 0/1500 | 0 |
| contention | Bob → Alice | 1.217 | 0/1500 | 0 |
| overload | Alice → Bob | 15.791 | 50/150 | 0 |
| overload | Bob → Alice | 15.187 | 50/150 | 0 |
| blocked-phone | Alice → Bob | 0.141 | 145/150 | 0 |
| blocked-phone | Bob → Alice | 0.679 | 0/150 | 0 |

The overload and blocked-phone runs deliberately induce missed output. Their gates require bounded queues and zero catch-up bursts. Every missed slot index is recorded in the detailed timing artifacts. The received WAV checks confirmed Bob's 700 Hz tone at Alice and Alice's 400 Hz tone at Bob.

## Fuzzing

All targets ran with instrumentation and AddressSanitizer, a fixed seed, bounded input length, and a 30-second minimum. The final run found no crashes.

| Target | Seconds | Executions |
| --- | ---: | ---: |
| handshake | 31 | 2,116 |
| record | 31 | 1,905 |
| codec | 31 | 20,012 |

The original empty-input panic was in the handshake fuzz harness. Its mutation tail now uses checked slicing, and the final fuzz run includes empty input. The account-local C++ adapter handles Zig's target spelling and runtime linking without system package installation.

## Dashboard and scope

The live read-only dashboard reports each check as it starts and finishes, shows the five-node call path, and shares verdicts with the CLI. Pause, Step, Replay, and test filtering were exercised in the browser. Opening it during timing now shows the paused measurement state. Automated checks cover loopback binding, read-only HTTP, stream pause/resume, the event schema, and the saved report's verdict mapping. Each full run saves a self-contained offline replay.

This run validates local synthetic software calls. MCU timing, physical BLE, microphones, speakers, acoustic leakage, and radio/power side channels require the separate hardware validation described in the [threat model](THREAT_MODEL.md). The trusted executable, host OS, and initial loader are part of the trusted base.
