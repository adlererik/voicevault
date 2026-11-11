# VoiceVault documentation

VoiceVault is a device project with a working software laboratory. The documentation separates its intended product, implemented behavior, measured evidence and unfinished work.

| Read this | To understand |
|---|---|
| [Project vision](PROJECT_VISION.md) | The future device, its purpose and the full intended scope |
| [Why a separate device?](DEVICE_RATIONALE.md) | The trust-boundary benefit and the physical audio requirements |
| [Threat model](THREAT_MODEL.md) | NSA-capability phone/network control, assumptions and exclusions |
| [Architecture](ARCHITECTURE.md) | Components, data paths, enrollment, invitations and a complete call |
| [Cryptographic choices](CRYPTOGRAPHY.md) | What each algorithm does, why it was selected and its limits |
| [Security control register](SECURITY_CONTROLS.md) | The attack-to-control-to-code/evidence mapping |
| [Detailed security design](SECURITY_DESIGN.md) | Message formats, keys, scheduling, storage, radio and update policy |
| [Assurance case](ASSURANCE.md) | Precisely which claims the evidence supports |
| [Recorded results](RESULTS.md) | Actual software runs, timing, fuzzing, proofs and raw logs |
| [Fuzzing](FUZZING.md) | What each campaign feeds into the code, asserts and leaves untested |
| [Hybrid call establishment](POST_QUANTUM.md) | Recorded-call goal, exact handshake, erasure and embedded evidence |
| [Platform fit](PLATFORM.md) | ARM linking/execution, memory budgets and hardware evidence limits |
| [Command-deck feature checks](COMMAND_DECK_CHECKS.md) | Latest UI/audio behavior and explicitly scoped validation |
| [Live device dashboard](LIVE_DASHBOARD.md) | Fixed local address, live progress, device activity and saved replay |
| [Development guide](DEVELOPMENT.md) | Setup, commands, repository layout and reproducing results |
| [Roadmap](ROADMAP.md) | Evidence gates from software through physical hardware |
| [Hardware plan](HARDWARE_PLAN.md) | Safe 7 reference, KiCad and emulation scope, microSD updates and first board measurements |
| [Screenshots](screenshots/README.md) | Actual dashboard captures and their context |

For a first visit: vision → architecture → threat model → control register → results. For security review: threat model → cryptography → detailed design → assurance → raw evidence. For implementation: development guide → source crates → tests → roadmap.

## Status terminology

**Implemented** means code exists and its scope is stated. **Tested model** means policy executes against abstract hardware interfaces; it is not a physical chip protection. **Measured** means a named run produced an observation. **Planned** means an intention or decision gate, not a delivered protection.

The recorded phase-two evidence predates the VoiceVault name. Keep those original run IDs, hashes, logs and protocol domain strings intact. A documentation, branding or presentation update does not create a new successful security run.
