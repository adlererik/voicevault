# Hybrid v2 verification

`./lab watch` completed with exit status 0. All 11 required groups and 48 checks passed. The journal reports 68 named Rust, Opus and Kani outcomes. The 80 ML-KEM ACVP cases run inside two Rust tests.

The run began at 2026-11-11T01:39:23.179664+01:00. The source manifest identifies the exact runtime and test inputs. Two unchanged upstream lockfiles used by the integrity checks were subsequently tracked. Both source integrity checks were also repeated against a fresh Git archive.

[Raw verdict](verdict.json) · [Event journal](events.ndjson) · [Timing](timing.json) · [Cortex-M33](platform/platform.json) · [Source manifest](tested-source-manifest.json) · [Summary](summary.json)

## Instrumented fuzzing

| Target | Executions | Seconds |
|---|---:|---:|
| [handshake](logs/fuzz-handshake.log) | 6,606 | 121 |
| [record](logs/fuzz-record.log) | 5,677 | 121 |
| [codec](logs/fuzz-codec.log) | 59,501 | 121 |
| [enrollment](logs/fuzz-enrollment.log) | 10,413 | 121 |
| [lifecycle](logs/fuzz-lifecycle.log) | 6,514 | 121 |
| [update-radio](logs/fuzz-update-radio.log) | 63,924 | 121 |
| [hybrid-kem](logs/fuzz-hybrid-kem.log) | 6,442 | 121 |
| [startup](logs/fuzz-startup.log) | 3,360,300 | 121 |

All eight campaigns used the 120-second minimum and recorded 3,519,377 executions in total. [Five bounded Kani harnesses](logs/kani.log) passed. These runs cover the tested inputs and encoded proof bounds.

## Native calls and embedded execution

The altered-startup test records the responder's authentication rejection and the initiator's timeout before either device opens audio. Normal and induced-fault calls recovered synthetic audio in both directions. [Startup attack](logs/live-startup-tamper.log) · [Normal call](live/) · [Induced media faults](live-faults/)

| Scenario | Alice to Bob p99 send error | Bob to Alice p99 send error | Missed slots A / B |
|---|---:|---:|---:|
| idle | 1.193 ms | 0.905 ms | 0 / 0 |
| contention | 1.700 ms | 0.724 ms | 0 / 0 |
| overload | 15.194 ms | 15.936 ms | 50 / 50 |
| blocked-phone | 0.196 ms | 0.268 ms | 145 / 0 |

The existing idle and contention gates require at most 5 ms p99 send error and 0.1% missed slots per direction. Overload and blocked-phone tests require bounded queues and no catch-up bursts.

The Cortex-M33 probe completed both hybrid startup flights and recovered 32 Opus frames. Its linked image was 863,104 bytes of the 983,040-byte slot. It used 552,324 bytes of static RAM including the reserved heap, 13,816 bytes of cumulative diagnostic heap allocation and 84,876 bytes of observed stack. The model leaves 37,500 bytes after explicit reservations. The evidence is scoped to QEMU and the listed capacity assumptions. [Platform limits](../../PLATFORM.md)

The first attempted run exposed an unmaintained dependency in libcrux's dormant proof-extraction configuration and a compiler error in the handshake fuzz target. The completed run uses the corrected fuzz target and scans the actual supported target graphs and the embedded build host. The advisory policy is unchanged. [Dependency check scope](../../DEVELOPMENT.md)
