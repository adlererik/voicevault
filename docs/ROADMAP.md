# Roadmap from laboratory to device

This is a sequence of evidence gates, not a delivery-date promise. Hardware construction is deferred until the software design is sufficiently reviewed and measured. Passing finite tests never produces absolute certainty.

## 1. Working adversarial laboratory — established baseline

The repository has native full-duplex synthetic calls, two hostile phone processes plus a relay, actual Opus/Noise, confirmed enrollment, signed invitations, stored-state/radio/entropy/update policy models, a test dashboard and a Cortex-M33 diagnostic. The recorded baseline passed eleven required groups. [Evidence](RESULTS.md)

Keep this baseline reproducible: retain raw results and hashes, protocol known answers, codec references, dependency locks, meaningful negative tests and failure verdicts. Preserve original evidence when branding, documentation or presentation changes.

## Recommended next software milestone

**Make a reviewed long-call lifecycle the next feature gate.** Keep the five-minute fail-closed limit until a reviewed design replaces it. First obtain independent review of the existing Noise adapters, invitation/prologue binding, nonce/replay rules and unsafe codec initialization. Then design fresh authenticated key establishment during an ongoing call, old-key retirement, loss/reorder recovery, explicit failure behavior and reset handling. A symmetric rekey alone does not introduce fresh DH entropy or automatically provide recovery after key exposure. The Noise specification describes rekeying and application responsibilities; seamless renewal here still needs a concrete reviewed integration. [Noise advanced features and responsibilities](https://noiseprotocol.org/noise_rev34.html)

Run that work through the existing live UI as an observation tool: display epoch transitions, rejected old-epoch packets, controlled reconnection and any interruption to audio. Test short artificial epochs under faults before testing long calls. Define key and audio-buffer ownership/lifetimes and investigate dependency, stack, allocator and crash remnants alongside renewal.

**Broaden assurance before adding deployment features.** Seed full-size hybrid messages and structured fragment sequences, extend the campaigns beyond the current two-minute checks, retain minimized corpora and track coverage. Add model/property checks for persistence failures around renewal, revocation and update transitions. Independent review must include malformed authenticated audio, the local crypto integration and the initialization-only codec patch. [Current fuzz targets and gaps](FUZZING.md)

**Write the concrete platform contract while remaining software-only.** Select a candidate MCU capacity/layout and map secure-element operations, protected generations, radio isolation, display buffering and offline-update transactions to required capabilities. Link those proposed memory reservations before committing to a PCB. The next hardware gate, when separately authorized, is a small development-board measurement of real codec deadlines, worst-case stack, interrupt/DMA load and power—not an immediate custom board. A tool such as probe-rs can run/debug real targets and report instrumentation, but choosing it does not establish device isolation or timing. [probe-rs](https://probe.rs/)

Defer public signaling, Nostr and polished production hardware until the endpoint lifecycle and platform contract survive these gates. The current live dashboard is useful for finding and explaining failures; it is not independent security review.

## 2. Strengthen software assurance — before board commitment

| Work | Exit evidence |
|---|---|
| Independent protocol and integration review | Findings resolved or explicitly accepted with a recorded rationale; scope includes local crypto adapters and unsafe codec initialization |
| Longer fuzzing and state exploration | Sustained campaigns, minimized regressions, malformed inputs from unauthenticated and authenticated peers |
| Complete key/audio erasure policy | Defined lifetimes and review of dependency, stack, allocator, crash and audio-buffer remnants |
| Long-call key lifecycle | Reviewed seamless authenticated renewal, loss/reorder handling, old-key retirement and reset/nonce invariants; current five-minute stop remains until replaced |
| Durable contact/counter state | Transaction and recovery design matched to actual protected storage and endurance limits |
| Trusted pairing UX | Chosen out-of-band transport, full comparison or reviewed short-SAS ceremony, attempt/error rules and user tests |
| Discovery and invitations | Defined untrusted-carrier interface, authenticated names, expiry/time/challenge behavior and metadata analysis |
| Reproducible release process | Independently rebuilt payload comparison, separated release signatures, documented environment and release-key custody |
| Recorded-call protection | Implemented v2 hybrid call establishment for the recorded-call goal. Independently review HFS, erasure and actual MCU behavior before reliance. [Protocol](POST_QUANTUM.md) |

## 3. Choose and validate the platform

Select an actual MCU, secure elements, radio processor, audio interface and display strategy. Map each required signature, DH, counter and storage operation to a supported chip capability. Check the chosen SRAM/ECC configuration, memory protection, debug policy, flash-bank layout and root-verifier provisioning.

The current 768 KiB main-RAM / 960 KiB image-slot gate is a reference capacity test. It reserves 64 KiB for future display/DMA/drivers and assumes partial rendering. A full Safe 7-sized framebuffer alone exceeds that reserve. Link the whole planned firmware, not only a protocol sample, and replace observed diagnostic stack use with a stronger worst-case analysis.

## 4. Controlled hardware prototype

Conceptual schematic work can proceed alongside the software checks. Use the [hardware plan](HARDWARE_PLAN.md) to define interfaces and simulation scope. The physical prototype starts with a development board and measurement of the relevant workloads before custom PCB layout. Initial hardware success requires:

- Capture and playback meeting real 20 ms deadlines under worst relevant interrupt/codec load, with measured latency and power.
- BLE MTU, retries, fragmentation, backpressure, reconnect and flooding tests at the actual phone-visible boundary.
- Radio containment tests showing no access to trusted keys, audio, flash, clock/entropy or consent through buses, DMA or privileged commands.
- Independent entropy measurements and source-failure behavior; secure-element transactions and endurance checks.
- Trusted display/input, mic disconnect, headset/analog path and acoustic leakage validation.
- Real flash power-loss, boot-signature, rollback, debug-lock and protected-root behavior tests.

The phone microphone/speaker removal requirement and remaining acoustic pickup paths must be evaluated against specific host hardware. Enclosure/glitter-photo ideas remain a separate physical study, without adding supply-chain claims to the present software evidence.

## 5. Review before sensitive use

Independent review must cover the actual assembled endpoint, firmware configuration and operational instructions. Resolve findings, document residual metadata/availability/acoustic risks, establish release and vulnerability-handling procedures, and verify that users can authenticate contacts correctly. A prototype passing its own tests is not a production security approval.

## Decisions intentionally still open

The exact bill of materials, secure-element key residency, physical pairing transport, display/PCB/enclosure details, seamless renewal construction, hardware side-channel assessment, Nostr/other relay adapters, production release licensing and distribution model remain open. Repository organization can grow into firmware, drivers, hardware and release tooling when those components exist; empty directories or dates are not evidence of progress.
