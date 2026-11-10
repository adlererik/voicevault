# VoiceVault live device laboratory

The dashboard is a read-only view of actual test-runner output and endpoint telemetry. It represents the intended separate devices while the project remains entirely software-only. All audio is generated test audio; the screen does not expose voice samples, secret keys, contact secrets or raw arbitrary subprocess output.

## One address for every run

Open **http://127.0.0.1:8765/**. This is a fixed loopback address on the development computer, not a public server or a remotely reachable static LAN address.

```sh
./lab watch --out /absolute/path/to/an/empty/directory
./lab ui
./lab demo
```

`watch` runs all eleven required verification groups. `ui` opens the persistent dashboard without launching tests. `demo` runs two eight-second calls and clearly identifies itself as a demonstration, not a full verification campaign. Both commands publish to the same address. Automatic watch/demo opening happens once per service process so repeated runs do not accumulate browser tabs; `./lab ui` explicitly opens the page again. The service remains available after completion and follows the next published run. It can be started again with `./lab ui` after a restart of the computer.

There is no random-port fallback. If another program owns port 8765, the command reports an address conflict. Health checks distinguish this checkout's service from other applications or incompatible service versions. Existing clones can keep their original folder names; the source checkout is resolved by the launcher.

## What the display means

| Display | Source and meaning |
|---|---|
| Verification now | Current child process, elapsed run time, and incremental reported progress. Starting is not passing. |
| Checks | Every scheduled check, with pending/running/pass/fail/blocked state. Optional setup checks appear if actually needed. |
| Individual results | Rust test starts and outcomes, official Opus vector outcomes, and individual Kani harness results. A check/group pass never fabricates case passes. |
| Fuzz progress | Execution totals, execution rate and process memory as libFuzzer reports them; elapsed time continues between reports. These are executions, not separate security proofs. |
| Alice and Bob | Actual lifecycle messages and send/authenticate/reject/playout events in the dedicated live call scenarios. The cards are software endpoint representations, not connected physical products. |
| Hostile phones and relay | Real separate transport processes and their launch status. Intermediate hops do not have independent live packet observations. Animations only connect event endpoints actually reported. |
| Device counters | Cumulative observations within the current run. A new published run resets them. Accepted means authenticated and buffered, not a proof of eventual audible delivery. |
| Activity feed | Recent actual events, with a bounded display history. Full events and raw diagnostic logs remain in the run directory. |
| Required groups | The same eleven verdicts written by the CLI. A demo marks these not run. |
| Connection status | Server heartbeat and reconnect state. A lost connection is not a test success. |
| Trace inspection | Pause, step, scenario filter and explicit replay, independently of ongoing check collection. Replay is marked; it does not turn a saved event into a live observation. |

The normal live call exercises actual signed invitations, Noise authentication, simulated local approval, encrypted full-duplex Opus, bounded framing/jitter handling and recovered-tone direction checks. The fault call deliberately drops selected media fragments and changes ciphertext in Phone A. Bob must reject records and exercise loss concealment; both call artifacts retain metrics and WAVs. Its full-run check fails if rejection/concealment is not observed. The demonstrations use OS randomness for fresh identities and handshakes. The native harness supplies the simulated preverified contact and local consent; the separate lifecycle tests exercise Noise XX enrollment and confirmation. There is no physical pairing or remote UI consent action here.

## Timing measurements remain distinguishable

Streaming every packet and rendering animations adds workload. Therefore the scored 30-second idle/contention and overload/blocked-phone scenarios keep the existing endpoint buffering: they do not print live packet events from the timing path. Their check progress and elapsed time remain visible; the graphic is held still. Packet traces released after a timing scenario are prefixed `recorded-` and labeled **Recorded benchmark trace**. Idle/contention gates remain p99 absolute send error ≤ 5 ms and missed slots ≤ 0.1% per direction. Overload gates retain bounded queues and zero catch-up bursts.

The separate `live` and `live-faults` calls stream while running and are not substitutes for those scored timing measurements. Their telemetry itself can affect timing. Device cards retain the last observed call when other checks are running and say that no live call is active. They do not manufacture call activity during compilation, proofs or fuzzing.

## How incremental reporting works

1. The suite starts each child with a pipe and reads available bytes continuously. A bounded incremental parser recognizes partial Rust test prefixes, multi-line single-threaded outcomes, vector starts/results, Kani harnesses and libFuzzer statistics. Output is also preserved in the raw log.
2. Supported structured events are schema checked. Only permitted fields, nodes, actions, statuses and bounded text reach the dashboard. Compilation/progress descriptions are sanitized summaries; arbitrary log text is not forwarded.
3. The trusted runner appends events to a local journal. A separate persistent service follows the journal, so slow browser clients do not block the child output pipe. The journal still incurs local I/O, which is why packet telemetry is confined to unscored calls.
4. Read-only server-sent events carry run identifiers and cursors. Reconnect resumes within a run; the next run resets the display. Refresh reconstructs current results. An interrupted runner is labeled interrupted, not completed.
5. The suite saves the same event set and verdict mapping in its offline HTML artifact. `./lab replay` opens that saved evidence; no server is needed.

The HTTP service binds only 127.0.0.1, checks the Host header, has no HTTP test-launch or write interface, caps simultaneous event clients at eight and applies a restrictive content policy. The local files and development host remain trusted. This is an observation tool, not an adversarially isolated control plane or a production device management API.

Regression tests cover starts arriving before child exit, split test outcomes, fuzz progress, bounded parsing, journal persistence/partial writes/new runs, completion/reconnect, address ownership, read-only HTTP, escaping and exact group-verdict mapping. Browser captures in the [gallery](screenshots/README.md) show the actual interface and their run context.
