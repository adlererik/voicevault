# VoxBastion test screenshots

Actual browser captures of phase-two evidence from 2026-11-10. The VoxBastion capture presents the original results in the renamed interface; older screenshots preserve the Quietlink Lab branding.

| Capture | Meaning |
|---|---|
| [VoxBastion test results](voxbastion-tests.jpg) | Renamed dashboard with searchable outcomes from the same recorded run; no new test campaign implied. |
| [VoxBastion pairing tests](voxbastion-pairing.jpg) | Three actual enrollment/confirmation/capacity/replay outcomes selected through search. |
| [Individual test results](phase2-tests-visible.jpg) | Searchable reported cases and 40 verification checks, added after the completed run. |
| [Original completed suite](phase2-overview.jpg) | All eleven required groups passed in the original results view. |
| [Live progress](phase2-live.jpg) | Captured during lifecycle fuzzing, before the final groups completed. |
| [Authenticated malformed audio](phase2-authenticated-peer.jpg) | A valid peer's malformed Opus is rejected after authentication, with loss concealment. All eleven groups have passed. |

These are actual browser captures of test events. The dashboard shows running checks, then can replay saved sends, drops, tampering and receiver responses. Streaming pauses during native timing measurements. It contains descriptions and verdicts, not secret keys or plaintext voice samples.

The older `dashboard-overview.jpg`, `authenticated-peer-rejection.jpg` and `fragment-flood.jpg` remain historical captures of the earlier nine-group run. They do not represent the phase-two suite. See [current recorded results](../RESULTS.md).
