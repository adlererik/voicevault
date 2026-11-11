# Assurance case

The project makes checkable, bounded claims. The adversary is NSA-capability hostile phones plus telecommunications control. Supply-chain attacks are excluded. The trusted endpoint, initial trust anchors and device-local peripherals remain assumptions. Test verdicts describe the exact implemented model.

| Property | Mechanism and evidence | What the evidence does not establish |
|---|---|---|
| Wrong peers cannot silently become trusted contacts | Signed identity/DH binding; Noise XX full-fingerprint local comparison; mutual encrypted confirmation; MITM and malformed-enrollment tests | A usable short SAS, trusted physical display drivers, users comparing correctly |
| A relay cannot choose a trusted caller name or replay an accepted invitation | Pinned contacts; signed recipient/challenge/counter/expiry; storage-before-release; context-bound hybrid KK; lifecycle tests and signaling fuzzing | Private invitation metadata, durable hardware storage, resistance to telecom denial of service |
| A call requires hybrid establishment | Fixed suite and exact flights, legacy downgrade rejection, byte-by-byte tamper cases, authenticated KEM faults, bounded startup parser and Kani order check | Cryptographic proof of the experimental integration, active quantum authentication or availability |
| Media is gated by consent and confirmation | Same call-state implementation in native/ARM; negative tests; bounded Kani consent harness | Correct physical microphone wiring or the entire program formally verified |
| Forged/replayed records do not poison reception | Authentication before replay commit, strict slot/counter checks, reference vectors, replay property tests, Kani replay harness, record fuzzing | Unbreakability of primitives or absence of parser/compiler/kernel vulnerabilities |
| Close and restart have bounded key use | Irreversible close, owned cipher-key destruction, five-minute epoch limit, fresh handshake tests, closed-state Kani harness | Complete Snow/stack erasure, live device key extraction resistance, seamless ratchet or post-compromise recovery |
| Stored state cannot be rolled back under the protected-root assumption | AEAD snapshots tied to owner/current protected generation; tamper, replay, revocation, unavailable-root tests | Real secure-element transactional behavior, persistence or endurance; lost-latest-snapshot availability |
| Radio ingress has no privileged update/consent command | Narrow data opcode, bounded queue/rate/expiry, all-opcode/reset/update-mode tests, radio fuzzing, native ingress integration | Hardware bus/DMA/MPU isolation or real BLE stack exploits |
| Offline images are authenticated and cannot boot below the protected version | Signed exact envelope, readback, inactive bank/header-last writes, rollback floor, power-cut/torn-write tests and counter Kani harness | Real flash physics, immutable root provisioning, signing-key custody; the entire updater is not model checked |
| Entropy failure does not fall back to phone input | Onboard-only source interface, two-source policy, monotonic generation, injected stuck/failure tests | A measured min-entropy bound, independent sources, a complete hardware RNG health test standard |
| Active voice does not change record length | CBR Opus, DTX off, fixed encrypted padding/filler; codec and deterministic trace tests | Hidden call boundaries, no correlation, perfectly constant observed timing under every load |
| Tested critical code fits a reference MCU capacity | no_std linked Cortex-M33 ELF, QEMU execution, ELF sections, heap and stack watermark, explicit reserves | Real-time MCU performance, worst-case stack, hardware drivers, actual TrustZone isolation or a final part choice |

## Evidence discipline

Every full run emits `verdict.json`, diagnostic logs, timing results, an ARM capacity report, recovered synthetic WAVs and an event-backed dashboard. A required failure or unavailable tool prevents the full run from passing. Timing thresholds are retained; failed checks are fixed or reported rather than removed. Reports from an earlier source state remain historical evidence and cannot be relabeled as a newer run.

Fuzzing is a reproducible smoke campaign with finite inputs and time. Five Kani harnesses verify their encoded properties and bounds; cryptographic libraries, arbitrary execution traces and hardware are outside those proofs. Published vectors demonstrate compatibility with known answers, not a cryptographic audit. Independent review must cover the experimental HFS call integration, secret ownership and erasure, and in-place Opus initialization.

## Remaining decision gates

Before a hardware commitment, obtain independent protocol and implementation review, expand long-running fuzzing and state exploration, establish a complete memory/secret erasure policy, choose supported secure-element operations, design atomic durable storage, and specify usable pairing and invitation discovery. Long calls currently stop at the epoch limit; seamless renewal is unfinished. The v2 hybrid design addresses recorded-call confidentiality under the assumptions in the [protocol document](POST_QUANTUM.md).

Hardware reliance additionally requires capture/playback and interrupt timing, worst-case RAM/stack analysis, radio-controller containment, flash power-failure tests, entropy measurements, trusted UI checks, acoustic leakage tests and power measurements. Those tasks are not silently waived because the software diagnostic fits.
