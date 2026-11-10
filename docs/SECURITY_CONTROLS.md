# Security control register

This is the attack-to-mechanism map for VoiceVault. The attacker may have NSA-class control of both phones and telecommunications, including compromise through zero-click/zero-day exploits. Supply-chain attacks are excluded. Endpoints, independent identity verification and device-local authorities are trusted assumptions in the software model.

**Runtime** means the mechanism is exercised by executable endpoint code. **Model** means policy is tested with abstract device-local hardware/state. **Planned** means it is not delivered yet. A passing test supports its specified behavior; it is not a claim that no future exploit exists.

## Identity, signaling and session establishment

| ID | Threat and control | Status / implementation | Evidence and limit |
|---|---|---|---|
| I1 | Replace an identity's DH key: Ed25519 signs the separate Ed25519/X25519 public-key binding | Runtime: [contact/Pin code](../crates/protocol/src/lib.rs) | [Protocol tests](../crates/protocol/tests/security.rs); the expected signer must be independently authenticated |
| I2 | Enroll an impersonator through a hostile phone: Noise XX, exact message bounds, signed-record/static-key agreement, full transcript comparison and mutual confirmation | Model/runtime policy: [enrollment](../crates/protocol/src/enrollment.rs) | [Lifecycle tests](../crates/protocol/tests/lifecycle.rs), [enrollment fuzzing](../fuzz/fuzz_targets/enrollment.rs), ARM path; physical UI/transport not built |
| I3 | Use a self-signed record as proof of a person's name: only locally enrolled/OOB-verified records create trusted pins | Runtime/model: [enrolled contact](../crates/protocol/src/enrollment.rs), [book](../crates/protocol/src/contacts.rs) | Substitution, wrong signer, local-approval and MITM tests; human verification remains essential |
| I4 | Spoof or replay an invitation: sign both peers, recipient boot challenge, counter, expiry and fresh call nonce | Runtime: [invitations](../crates/protocol/src/invitation.rs) | Peer/recipient/challenge/time/replay and restored-counter tests; [lifecycle fuzzing](../fuzz/fuzz_targets/lifecycle.rs) |
| I5 | Display an unverified caller name or consume replay state on storage failure: release a private verified token and persist before success | Runtime/model: [invitation verification](../crates/protocol/src/invitation.rs) | Unavailable-store and counter-recovery tests; protected persistence itself is abstract |
| I6 | Attach another accepted call to the handshake: ordered signed offer/acceptance bound into Noise's prologue | Runtime: [call context](../crates/protocol/src/invitation.rs), [native connect](../crates/lab-runner/src/wall.rs) | Context mismatch and accepted-invitation/fresh-session tests |
| I7 | Impersonate a pinned peer during a call: Noise KK with static pins and fresh ephemerals | Runtime: [handshake](../crates/protocol/src/lib.rs), [secret-owning adapters](../crates/protocol/src/randomness.rs) | Actual-adapter [KK/XX known-answer tests](../crates/protocol/tests/vectors.rs), wrong-peer and tampered-handshake tests |

## Media, consent and hostile delivery

| ID | Threat and control | Status / implementation | Evidence and limit |
|---|---|---|---|
| M1 | Read or modify media: ChaCha20-Poly1305 under Noise's distinct directional keys | Runtime: [records](../crates/protocol/src/lib.rs) | Known answers, tag/ciphertext tamper and direction/reflection tests; endpoints and primitives remain trusted |
| M2 | Start a mic through remote signaling: local consent plus encrypted Confirm/Ready before media | Runtime state: [call-state](../crates/call-state/src/lib.rs) | Early-media/unsupported-command tests and bounded consent Kani proof; physical audio gate is planned |
| M3 | Replay packets or forge a huge counter: authenticate and check state, padding and local slots before committing the replay window | Runtime: [receive](../crates/protocol/src/lib.rs), [bitmap](../crates/call-state/src/lib.rs) | Forged-counter/duplicate tests, set-model property check, replay Kani proof, [record fuzzing](../fuzz/fuzz_targets/record.rs) |
| M4 | Reuse a key/nonce after reconnect: monotonic sending, reserved control sequences and new handshake before counter restart | Runtime: [session](../crates/protocol/src/lib.rs) | Fresh-session, old-packet rejection and opposite-direction tests; no resumption is implemented |
| M5 | Infer speech/mute from packet size: fixed 128-byte records, 24 kbit/s CBR Opus, DTX off and encrypted filler | Runtime: [codec](../crates/codec/src/lib.rs), [scheduler](../crates/device-core/src/lib.rs) | Silence/CBR and deterministic virtual trace checks; metadata, timing misses and traffic correlation remain |
| M6 | Delay/stall traffic and force a backlog burst: absolute deadlines, bounded queues, expiry and discard missed slots | Runtime: [device-core](../crates/device-core/src/lib.rs), [native timing](../crates/lab-runner/src/wall.rs) | Idle/contention/overload/blocked-phone [measurements](evidence/phase2/timing.json); denial of service remains possible |
| M7 | Exploit compressed audio, including from a valid peer: authenticate first, enforce packet/channel/duration bounds, use bounded jitter/PLC | Runtime: [codec gate](../crates/codec/src/lib.rs), [playout](../crates/device-core/src/lib.rs) | Malicious authenticated peer scenario, codec fuzzing, both libopus directions and twelve official decoder vectors; not a proof of decoder safety |
| M8 | Flood or confuse fragments: bounded lengths, eight assemblies, expiration and bounded ingress work | Runtime: [link](../crates/link/src/lib.rs), [radio port](../crates/protocol/src/radio.rs) | Fragment flood, reordering, duplicate, expiration, queue/rate and reset tests |

## Device-local state and firmware

| ID | Threat and control | Status / implementation | Evidence and limit |
|---|---|---|---|
| D1 | Tamper with or swap contact storage: separate-key AEAD snapshot, owner binding and signed records | Model: [contacts](../crates/protocol/src/contacts.rs) | Tamper, wrong-device and signature tests; eight fixed slots and bounded aliases |
| D2 | Restore old revocations or signaling counters: snapshot generation must equal the protected current generation | Model: [protected storage root](../crates/protocol/src/contacts.rs) | Old-snapshot rejection and replay-after-restore tests; secure-element atomicity/endurance unresolved |
| D3 | Continue using a revoked contact: book pin/invitation lookup rejects revoked entries | Runtime/model: [contact lookup](../crates/protocol/src/contacts.rs) | Revocation survives modeled restoration; local control must separately close an already active call |
| D4 | Reactivate a closed call or use media keys indefinitely: irreversible close, 15,000-slot epoch, drop owned transport keys and restart with fresh handshake | Runtime: [session](../crates/protocol/src/lib.rs), [closed state](../crates/call-state/src/lib.rs) | Close/expiry/restart tests and ten-step closed-call Kani proof; seamless renewal and complete erasure are open |
| D5 | Make the phone supply key entropy: only onboard source interfaces, protected generation and at least two passing sources | Model: [entropy pool](../crates/protocol/src/entropy.rs) | Stuck, failure-mask and generation tests; basic sanity checks do not measure actual entropy or independence |
| D6 | Abuse the radio as a command processor: one bounded data opcode; no consent, contacts, time, entropy, flash or debug authority | Runtime/model: [radio](../crates/protocol/src/radio.rs), [native ingress](../crates/lab-runner/src/wall.rs) | All-opcode, queue/flood/reset/update-mode tests, [update/radio fuzzing](../fuzz/fuzz_targets/update_radio.rs); physical bus/interrupt isolation is planned |
| D7 | Push an online firmware update: no update opcode; require local physical-approval authority for the offline model | Model: [offline policy](../crates/protocol/src/update.rs) | Denied-local-action and unsupported remote-command tests; SD/flash/immutable-root drivers not implemented |
| D8 | Install corrupt, forged, wrong-target or old firmware: signature over versioned target/security version/length/digest, readback and protected floor | Model: [boot verifier](../crates/protocol/src/update.rs) | Wrong signer/target/hash/version tests and symbolic monotonic-counter Kani proof; trusted root/key provisioning assumed |
| D9 | Lose power during install or hide a bank behind a read error: inactive-bank update, header last, propagate storage errors, verify before handoff | Model: [two-bank install/boot](../crates/protocol/src/update.rs) | Every modeled write cut, selected torn writes, corrupted-new-image and failed-read/commit-before-erase tests |
| D10 | Extract an owned secret buffer after ordinary destruction: zeroizing key owners and explicit session-key lifetime | Runtime hygiene: [identity](../crates/protocol/src/lib.rs), [adapters](../crates/protocol/src/randomness.rs) | Code-level ownership and lifecycle checks; complete KDF/stack/audio erasure and physical extraction resistance are not established |

## Containment and verification discipline

| ID | Threat and control | Status / implementation | Evidence and limit |
|---|---|---|---|
| V1 | Let simulated hostile roles read endpoint files/memory or create connections: inherited connected IPC, empty environment and default-deny seccomp after setup | Native model: [worker confinement](../crates/lab-runner/src/sandbox.rs) | Live escape probes for each hostile role; trusted host kernel/loader and pre-confinement setup assumed |
| V2 | Hide a failing/unavailable check: eleven required groups, explicit PASS/FAIL/BLOCKED, unchanged timing gates and nonzero failed-suite exit | Implemented: [runner](../scripts/lab.py) | [Recorded raw verdict](evidence/phase2/verdict.json); no full pass is inferred from a screenshot |
| V3 | Drift from the selected protocol/codec or accidentally change unsafe initialization: published vectors, reference codec and exact local-patch checks | Implemented: [vectors](../crates/protocol/tests/vectors.rs), [vendor integrity](../scripts/check_vendor.py) | KK/XX answers, libopus interop, official vectors, 100-frame constructor comparison, upstream-file/field coverage |
| V4 | Outgrow the intended embedded capacity unnoticed: no_std target graph, actual ELF link and execution, RAM/flash gates and guarded stack | Diagnostic: [ARM probe](../platform), [fit checker](../scripts/platform_check.py) | [Actual capacity report](evidence/phase2/platform/platform.json); no hardware throughput or worst-case stack proof |
| V5 | Confuse a group verdict with individual test evidence: incremental starts/outcomes from actual process output, separate check and case views | Implemented: [dashboard](../scripts/dashboard.py) | required check and individual-result views, parser/mapping tests, split-output and before-exit regressions, persistent fixed-address stream and browser checks; [telemetry contract](LIVE_DASHBOARD.md) |

## What these controls cannot promise

The attacker can prevent delivery, reveal cellular identity/location and correlate call timing. An intact phone microphone, another nearby device or the other participant can record speech. Constant-sized active records do not remove these paths. A real radio/driver/codec vulnerability could still violate the eventual endpoint boundary; finite fuzzing and memory-safe application code do not eliminate that risk.

Protected storage, entropy sources, flash and counters are models. Complete erasure, seamless renewal, a production pairing UI, decentralized discovery and post-quantum protection remain open. Physical audio, BLE isolation, trusted UI, hardware entropy, timing, power and acoustic behavior must pass their own gates. [Threat model](THREAT_MODEL.md) · [Assurance case](ASSURANCE.md) · [Hardware roadmap](ROADMAP.md)
