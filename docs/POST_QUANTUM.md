# Post-quantum forward secrecy: feasibility study

**Likely feasible on the proposed STM32U5-class platform, but not demonstrated by VoiceVault yet.** The current X25519/Ed25519 protocol is classical. No post-quantum implementation or new assurance claim is introduced by this study. The exact final MCU, secure elements and display configuration are still open.

## Owner's clarified goal: protect recordings made today

The requirement is **harvest-now-decrypt-later resistance**: an adversary may save complete encrypted calls today and try to decrypt those recordings if a cryptanalytically relevant quantum computer becomes available later. Operation against an active quantum-capable attacker is outside this requested extension. This clarification does not assert what capabilities any intelligence agency currently has.

**Yes, this protection is possible in principle.** Use a reviewed hybrid call-establishment protocol combining X25519 with a post-quantum KEM contribution, fresh session-specific secret material, transcript/identity binding, a sound combiner, downgrade prevention and proper erasure. The goal is that subsequently breaking the classical exchange does not reveal the hybrid call key, assuming the PQ construction remains secure. A permanent KEM private key alone does not automatically preserve earlier calls after that key is stolen. [Signal PQXDH specification](https://signal.org/docs/specifications/pqxdh/)

Fresh X25519 ephemeral keys and ChaCha20-Poly1305 alone do not meet this goal: a future quantum attack on the recorded classical exchange could recover the shared secret used to derive media keys. Deleting today's X25519 secrets does not remove the public exchange from an adversary's recording. PQ protection must be present **when the call is made**. A later upgrade cannot retroactively protect previously captured classical-only calls. [Signal's explanation of recorded-traffic protection](https://signal.org/blog/spqr/)

Present-day authenticated identities can remain part of a protocol designed for this limited future-recordings goal, under the existing assumptions about authentication when the call happens. This request does not require converting every identity or firmware signature to a post-quantum signature. A continuously running PQ ratchet is also not required solely for this goal: an appropriately designed fresh hybrid handshake per call can establish the needed session secret. Within-call key-exposure containment and recovery are separate requirements, with their own ratchet/erasure design. [PQXDH security scope](https://signal.org/docs/specifications/pqxdh/), [ratchet deletion/recovery considerations](https://signal.org/docs/specifications/doubleratchet/)

## Why the hardware looks plausible

The existing CPU-emulated diagnostic establishes these capacity observations, under the documented reference configuration:

| Current reference | Observation |
|---|---:|
| Main SRAM, ECC off | 786,432 bytes |
| Static RAM including reserved heap | 552,324 bytes |
| Reserved stack | 131,072 bytes |
| Future display/DMA/driver reserve | 65,536 bytes |
| Unassigned after reservations | 37,500 bytes |
| Linked image / image-slot budget | 707,168 / 983,040 bytes |

The codec already dominates RAM. These values do not include a future PQ implementation or a complete hardware firmware stack. Full framebuffer rendering, ECC, RTOS/driver changes and production memory protection can invalidate the present budget. [Platform evidence and assumptions](PLATFORM.md)

Published pqm4 results for optimized ML-KEM-768 show roughly 0.64–0.72 million cycles per individual KEM operation and about 2.8–6.5 kB **stack** for its optimized variants; the clean variant has a larger reported stack requirement. These are Cortex-M4 C implementations, not measurements of VoiceVault's Rust code or STM32U5 peripherals. The benchmark stores keys/ciphertexts outside that measured stack, so these numbers are not total RAM demand. [pqm4 benchmark tables](https://github.com/mupq/pqm4/blob/master/benchmarks.md), [stack measurement harness](https://github.com/mupq/mupq/blob/master/crypto_kem/stack.c)

ML-KEM-768 also has a 1,184-byte public key, 2,400-byte secret key, 1,088-byte ciphertext and 32-byte shared secret. Additional copies, transcript state, fragmentation, ratchet state, temporary allocations and interrupt stack must be counted. These sizes support a feasibility hypothesis; they do not prove that the whole voice endpoint fits. [PQClean ML-KEM-768 API](https://github.com/PQClean/PQClean/blob/master/crypto_kem/ml-kem-768/clean/api.h)

Plan to execute the PQ workload on the main MCU unless the selected secure element explicitly supports the chosen construction. TROPIC01's published asymmetric features include X25519 and Ed25519; its FAQ says quantum threats are outside its currently implemented algorithm model. Do not assume it can hold and operate an arbitrary KEM private key internally. [TROPIC01 capabilities](https://www.tropicsquare.com/tropic01), [vendor FAQ](https://www.tropicsquare.com/faqs)

## Proposed software-only decision gate

1. Freeze the requested target as recorded-traffic protection against future quantum decryption. Keep active quantum impersonation outside this extension; retain the existing physical/supply-chain exclusions.
2. Review a hybrid construction before changing Noise. ML-KEM-768 is a useful benchmark candidate, not an adopted project requirement. **ML-KEM is NIST-standardized**, which conflicts with the owner's preference to avoid NIST algorithms where practical. A strict non-NIST requirement needs an independently reviewed alternative comparison. No algorithm has been silently selected here. [FIPS 203 publication](https://www.nist.gov/publications/module-lattice-based-key-encapsulation-mechanism-standard)
3. Build an isolated, pinned no_std diagnostic with official known answers, negative/implicit-rejection handling tests, bounded parsers and erasure review. Measure final linked flash, all persistent buffers, heap and observed/worst-case stack margins alongside the existing Opus workload.
4. Model larger handshake messages and bounded fragmentation. PQ public keys/ciphertexts exceed one current 128-byte media record. Define transcript binding, downgrade rejection, packet loss/reordering, reset behavior and denial-of-service budgets. Do not add a continuous PQ ratchet just to satisfy the recorded-call goal. Preserve the observable fixed media-size/cadence policy.
5. Exercise hybrid establishment, erased-secret ownership, fresh calls after reset, malformed KEM messages, downgrade attempts and loss/reordering in the hostile-phone simulator. Independently review the integration and repeat whole-firmware capacity tests before hardware commitment. Seamless renewal remains its own later milestone.
6. After software gates and separate hardware authorization, measure real MCU deadlines, interrupts, entropy, secure-element operations and side channels. CPU emulation and another project's benchmarks cannot substitute for those measurements.

The present five-minute fail-closed media epoch and current cryptographic suite remain unchanged. The live audio monitor is a synthetic-test observation feature; it provides no post-quantum protection.
