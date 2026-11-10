# Security status and reporting

VoiceVault is experimental software for a future dedicated voice device. There is no production hardware release or supported sensitive-calling deployment. The current scope is defined in the [threat model](docs/THREAT_MODEL.md), [control register](docs/SECURITY_CONTROLS.md) and [assurance case](docs/ASSURANCE.md).

For a non-sensitive bug, use a repository issue with a synthetic reproducer, exact source revision, expected/observed behavior and relevant check output. For a potentially exploitable issue, use GitHub's private vulnerability-reporting option if available, or arrange a private channel with the maintainer before sharing exploit-sensitive details. Do not publish private keys, identities, recordings or unnecessary personal/system data.

Report whether the issue affects trusted parsing, authentication, replay/state, nonce/key lifetime, storage/update policy, codec handling, radio containment, the native lab or a proposed hardware boundary. A flaw in an assumption is useful to report even when no crash occurs.

Passing tests and bounded proofs are evidence for specified properties, not a certification or guarantee against an intelligence agency. Supply-chain attacks are excluded from the current requested threat model. Physical BLE/audio/entropy/isolation and complete memory erasure remain unvalidated. The diagnostic ELF deliberately uses public test keys and must never be treated as production firmware.
