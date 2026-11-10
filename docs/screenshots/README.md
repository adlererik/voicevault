# VoiceVault test screenshots

Actual browser captures, with historical and current run context kept distinct. The original phase-two evidence is from 2026-11-10. The VoxBastion capture presents the original results in the renamed interface; older screenshots preserve the Quietlink Lab branding.

| Capture | Meaning |
|---|---|
| [VoxBastion test results](voxbastion-tests.jpg) | Renamed dashboard with searchable outcomes from the same recorded run; no new test campaign implied. |
| [VoxBastion pairing tests](voxbastion-pairing.jpg) | Three actual enrollment/confirmation/capacity/replay outcomes selected through search. |
| [Individual test results](phase2-tests-visible.jpg) | Searchable reported cases and 40 verification checks, added after the completed run. |
| [Original completed suite](phase2-overview.jpg) | All eleven required groups passed in the original results view. |
| [Live progress](phase2-live.jpg) | Captured during lifecycle fuzzing, before the final groups completed. |
| [Authenticated malformed audio](phase2-authenticated-peer.jpg) | A valid peer's malformed Opus is rejected after authentication, with loss concealment. All eleven groups have passed. |

These are actual browser captures of test events. The dashboard shows running checks, then can replay saved sends, drops, tampering and receiver responses. In that historical interface, streaming paused during timing measurements. The current VoiceVault UI keeps check progress visible and labels buffered benchmark traces recorded. It contains descriptions and verdicts, not secret keys or plaintext voice samples.

The older `dashboard-overview.jpg`, `authenticated-peer-rejection.jpg` and `fragment-flood.jpg` remain historical captures of the earlier nine-group run. They do not represent the phase-two suite. See [current recorded results](../RESULTS.md).

## VoiceVault live UI

- `voicevault-live-devices.png`: live device view with Alice/Bob and the hostile forwarding path. Captured during an actual eight-second scenario, before that scenario exited.
- `voicevault-live-faults.png`: live induced corruption/loss scenario; Bob’s rejection count grows while synthetic audio is decoded or concealed. Intermediate hops have no independent live packet telemetry.

These two development captures came from `voicevault-verification-final`, which later stopped during the command session and is **not** counted as a complete passing campaign. They show genuine live behavior, not a manufactured final verdict. The latest complete-run capture and its result are identified separately.
