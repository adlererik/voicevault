# Verification results: phase two

The fresh complete native run on **2026-11-10** passed all **11 required groups** and exited zero. Run ID: `quietlink-phase2-final`. Tested implementation commit: `52aa06c`. The [machine-readable summary](verification-summary.json), [raw verdict](evidence/phase2/verdict.json), [timing data](evidence/phase2/timing.json) and [ARM report](evidence/phase2/platform/platform.json) identify the measurements and limits. Earlier interrupted development attempts are not counted as successful runs.

| Group | Result | Checks |
|---|---|---:|
| unit | PASS | 6 |
| protocol | PASS | 2 |
| lifecycle | PASS | 1 |
| platform | PASS | 1 |
| codec | PASS | 8 |
| isolation | PASS | 1 |
| fuzz | PASS | 9 |
| kani | PASS | 3 |
| dependencies | PASS | 3 |
| timing | PASS | 4 |
| dashboard | PASS | 2 |

The checks include formatting, Clippy with warnings denied, Rust tests, the release build, actual KK and XX resolver/reference vectors, virtual adversarial calls, 18 lifecycle test functions (including two 256-case property checks), Linux worker isolation, native call measurements, upstream libopus interoperability, all twelve applicable official mono decoder vectors, the constructor comparison and vendored-source integrity, three locked dependency graphs, four Kani harnesses, six extended fuzz campaigns and dashboard/verdict agreement. Raw per-check logs are linked through the verdict.

## Native call timing

Host: `Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz`; kernel `7.2.13-200.fc44.x86_64`; exact Rust pin `1.99.1`. Idle and CPU contention each run for 30 seconds and 1,500 slots per direction. Gates remain p99 absolute send error ≤ 5 ms and missed slots ≤ 0.1%. Overload and blocked-phone scenarios deliberately cause misses; their gates require bounded queues and zero catch-up bursts. The new signed invitation/accepted-context path and bounded radio ingress are active in these calls.

| Scenario | Direction | p99 send error (ms) | Missed / scheduled | Catch-up bursts |
|---|---|---:|---:|---:|
| idle | Alice → Bob | 1.497 | 0/1500 | 0 |
| idle | Bob → Alice | 1.028 | 0/1500 | 0 |
| contention | Alice → Bob | 2.829 | 0/1500 | 0 |
| contention | Bob → Alice | 1.027 | 0/1500 | 0 |
| overload | Alice → Bob | 15.169 | 50/150 | 0 |
| overload | Bob → Alice | 15.155 | 50/150 | 0 |
| blocked-phone | Alice → Bob | 0.160 | 145/150 | 0 |
| blocked-phone | Bob → Alice | 1.134 | 0/150 | 0 |

Recovered WAVs contain the opposite endpoint's expected generated tone. Digital playout timing excludes a real headset, ADC/DAC and radio path; it is not total hardware mouth-to-ear latency. Full per-direction values, queues, CPU times and missed-slot indices are in the timing artifact.

## Extended fuzzing and bounded proofs

All six campaigns ran with instrumentation/AddressSanitizer, bounded input size and seed 870321. No campaign reported a crash in this run. This is finite smoke fuzzing, not an audit or exhaustive exploration.

| Target | Seconds | Executions |
|---|---:|---:|
| handshake | 121 | 4,626 |
| record | 121 | 3,965 |
| codec | 121 | 34,630 |
| enrollment | 121 | 6,055 |
| lifecycle | 121 | 7,257 |
| update-radio | 121 | 55,948 |

Kani verified four harnesses: replay duplicate/preflight behavior, consent plus mutual confirmation before activity, closed-call irreversibility over the encoded ten-step trace, and monotonic security counter advancement for symbolic 64-bit values. The consent trace has seven steps. These checks cover the actual small state/counter implementation, not cryptographic primitives, all updater branches, the kernel or all arbitrary-length executions. [Raw Kani log](evidence/phase2/logs/kani.log)

## Linked Cortex-M33 fit

The diagnostic executes actual Opus, Noise, fragmentation/reassembly and playout plus selected enrollment, invitation, sealed storage, entropy, radio and offline boot/update paths. It processes 32 echo-fixture audio frames with nonzero recovered PCM. It uses public fixture keys, and must never be deployed.

| Measurement or allowance | Bytes |
|---|---:|
| Linked image | 707,168 |
| Image slot budget | 983,040 |
| Static RAM including 32 KiB heap reservation | 552,324 |
| Reserved guarded stack | 131,072 |
| Observed stack high-water mark | 85,092 |
| Observed cumulative allocations | 3,328 |
| Future display/DMA/driver reserve | 65,536 |
| Unassigned RAM after reservations | 37,500 |
| Main RAM budget | 786,432 |

The ELF hash and section listing are in the [ARM report](evidence/phase2/platform/platform.json). QEMU MPS2 AN505 models the CPU, not STM32 peripherals. The capacity reference is STM32U585-class main SRAM with ECC off. The 64 KiB display/driver reserve assumes partial rendering. Actual MCU throughput, worst-case stack, BLE, interrupts, secure elements, entropy quality, power, acoustic leakage and physical isolation remain unmeasured. [Platform details](PLATFORM.md)

## Assurance limits

The assumed attacker controls both phones and telecommunications, including phone compromise by zero-day or zero-click exploits. Supply-chain attacks are excluded. This lab starts with already-compromised phones and trusted endpoint software. It does not emulate an NSA exploit chain or establish protection from all future endpoint vulnerabilities.

The implemented five-minute media epoch stops and drops its owned transport keys, then requires a fresh authenticated handshake. Seamless renewal is unfinished. Long-lived key owners are zeroizing, but complete Snow KDF/stack and audio-buffer erasure has not been established. Secure-element storage, flash and protected counters are software abstractions. Independent review and hardware validation remain decision gates. [Assurance case](ASSURANCE.md)

## Dashboard follow-up

After the full run, the dashboard gained visible searchable lists for individual outcomes and verification checks. Its 49 named outcomes are extracted from the original logs: Rust cases (some repeated under different build profiles), twelve official Opus vectors and four Kani proofs. The original 40 check results and eleven group verdicts are retained. No test pass is inferred merely from a group passing.

The follow-up passed the dashboard self-test (including pass/fail/ignored and missing-proof parsing), original event/verdict mapping, and browser checks of the 49-result list, 40-check list and search. The live suite now emits these case outcomes when each check completes. The original full-run snapshot remains unchanged; this is separate presentation verification, not a new full security run.
