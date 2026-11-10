# Contributing to VoxBastion

VoxBastion is a software-first device project. Read the [vision](docs/PROJECT_VISION.md), [threat model](docs/THREAT_MODEL.md), [control register](docs/SECURITY_CONTROLS.md) and [assurance case](docs/ASSURANCE.md) before proposing security changes.

Useful contributions connect an implementation to a checkable property: a minimized parser failure, a state-machine invariant, a measured codec/resource constraint, a pairing usability result or a clearly scoped hardware test. State the attack, the intended boundary, the evidence and the remaining assumptions.

## Changes and review

- Keep trusted parsing/state code safe Rust and keep unsafe boundaries small and explained.
- Use established constructions. A different handshake, short SAS or key renewal protocol needs a design review before implementation.
- Keep all required checks and existing timing thresholds. Do not remove a failing test to create a passing report.
- Preserve lockfiles and vendored provenance. Explain local patches and compare against independent known answers/reference behavior.
- Keep secrets, private recordings and real contact data out of examples, logs and screenshots.
- Separate measured results, model assumptions, intended hardware and unresolved work. Avoid “NSA-proof,” “unhackable,” or hardware-security claims from CPU emulation.

Use synthetic reproducers and explain validation in pull requests. See [development](docs/DEVELOPMENT.md) for tools/commands and [security reporting](SECURITY.md) for sensitive findings.

## Hardware scope

No board construction, real BLE deployment, real microphones or production firmware is part of the current baseline. Hardware proposals should identify the software gate they depend on and how the relevant isolation, timing, entropy, storage, power or acoustic property will be measured.

## Licensing and distribution

A project-wide software/hardware/documentation license has not yet been selected. GitHub visibility and licensing are separate decisions. Vendored components retain their own license notices. Licensing, contributor terms and manufacturing/distribution permissions need a maintainer decision before wider distribution; this guide does not grant a new license.
