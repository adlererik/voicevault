# Security design and implementation

The security boundary is the dedicated voice endpoint. Assume NSA-class compromise of both phones and control of telecommunications. The software model gives hostile transport control of delivery, not device-local consent, identity pins, time, entropy or update authority. Supply-chain attacks are excluded. [Exact threat model](THREAT_MODEL.md)

## Enrollment and identity

An identity contains a separately generated Ed25519 signing key and static X25519 secret. The 128-byte contact record contains their 32-byte public keys and a 64-byte Ed25519 signature over a domain-separated binding. Checking a self-signature alone is insufficient: the expected identity must be independently authenticated.

`protocol::enrollment` implements `Noise_XX_25519_ChaChaPoly_BLAKE2s`, carries signed contact records inside its encrypted messages, verifies that each advertised X25519 key equals Noise's authenticated remote static, and rejects self-enrollment. Exact bounded handshake messages are 32, 224 and 192 bytes. Both trusted displays compare the full 256-bit transcript fingerprint. Both local approvals and both encrypted fingerprint confirmations are required before producing an `EnrolledContact`. Failed reads poison the enrollment state.

The full fingerprint is the implemented comparison. A convenient short SAS requires a reviewed ceremony and usability work; a six-digit truncation is not offered as equivalent protection. The five-process native call models prior out-of-band enrollment through supervisor-only sockets. The full XX ceremony runs in lifecycle tests, fuzzing and the ARM diagnostic. [Noise framework](https://noiseprotocol.org/noise.html)

## Stored contacts and signaling

`protocol::contacts` has eight fixed contact slots and bounded display aliases. Only enrolled contacts can be installed. Pins and invitations reject revoked contacts. Snapshots are authenticated and encrypted with ChaCha20-Poly1305, bound to the owner and a protected generation. Generation supplies a unique nonce under the storage key. Restore requires the current protected generation, preventing replacement with an older valid snapshot. Failure of protected storage fails closed.

`StorageRoot` is a software abstraction with an owned zeroizing key and monotonic state. Tests retain it across simulated restoration. It is not hardware-backed persistence or a secure-element driver. If the newest snapshot is lost after generation advancement, restoration rejects the old snapshot. Actual atomic transactions and write endurance need a hardware design.

`protocol::invitation` signs a fixed 128-byte offer or acceptance. Its signature binds sender/recipient key records, a monotonically increasing per-contact counter, issued/expiry times, a recipient boot challenge and the offer's fresh nonce. Counters are persisted before an invitation or successful verification is released. Storage errors roll back the in-memory counter. Trusted time rejects expiry and backwards clock movement; phone time is never authoritative. A maximum of eight verification attempts per trusted second bounds admission work. It can sacrifice availability during flooding, which hostile transport can already deny.

Only a private verified-invitation token provides the trusted contact name and can participate in accepted-call context construction. The signed offer and acceptance share a nonce, and their ordered transcript is hashed into the Noise call prologue. This prevents a relay from substituting a different accepted invitation while retaining the same authenticated session context. Invitations disclose signaling timing and public fields; they are authenticated, not encrypted by this layer.

## Call handshake, consent and keys

Calls require `Noise_KKhfs_25519+MLKEM768_ChaChaPoly_BLAKE2s`. Both verified identities and the accepted invitation are bound into the prologue. The two flights combine fresh X25519 ephemerals and a new initiator ML-KEM keypair with fresh responder encapsulation randomness. Noise authenticates both flights and uses HMAC/HKDF-BLAKE2s to mix the DH and KEM inputs and split directional keys. Wrong lengths, order and authentication poison the handshake. The native parser bounds fragment storage, work and lifetime. [Protocol and wire format](POST_QUANTUM.md)

Host calls use OS randomness. The hardware model uses MCU and two secure-element source interfaces, a protected generation, basic sanity checks and a requirement for two passing sources. A call fails if its required entropy is unavailable. All deterministic test entropy is confined to public fixtures.

The resolver clears owned entropy, X25519, ML-KEM and cipher-key buffers. Local Snow changes clear the chaining state and selected DH, KEM, HMAC and HKDF temporaries. Complete erasure through primitive internals, compiler copies and physical memory remains subject to independent review.

Local consent and encrypted Confirm/Ready gate media. Noise reserves transport nonces 0 and 1 for those controls. Closing a session irreversibly retires the owned directional keys. A 15,000-slot media epoch ends the call after five minutes and requires fresh hybrid establishment. Active quantum impersonation and recovery after a live key compromise remain separate security goals. [Erasure scope](POST_QUANTUM.md#what-is-erased)

## Media records and scheduling

| Portion | Bytes | Meaning |
|---|---:|---|
| Public sequence | 8 | Little-endian explicit Noise nonce; changing it invalidates the tag |
| Encrypted type and length | 2 | Consent/ready, audio or filler |
| Encrypted payload and zero padding | 102 | Bounded Opus frame or filler |
| Authentication tag | 16 | ChaCha20-Poly1305 integrity |
| Total | 128 | Fixed record size |

Sending is strictly monotonic. A separate 64-position incoming replay bitmap advances only after successful authentication, valid command/state and slot bounds. Forged high counters cannot move the window. Keys differ by direction and fresh session; reset requires a handshake before counters restart. Media at or after the epoch limit is rejected.

The audio profile is mono 16 kHz, 320 samples per frame, 20 ms, Opus at 24 kbit/s hard CBR, FEC off and DTX off. Encoded speech and silence are 60 bytes. Mute and missed encoding deadlines produce authenticated encrypted filler when scheduling permits. Deadlines are absolute. A stalled phone cannot make the endpoint release a catch-up burst; missed slots are counted and discarded.

One record every 20 ms is 51.2 kbit/s per direction, or 102.4 kbit/s full duplex, before link overhead. Fixed size and intended local cadence reduce speech/silence leakage at the device boundary. They do not hide call start/stop, subscriber identity, location, routing, loss or end-to-end correlation. CPU/interrupt load can still cause observable misses. The phone controls onward delivery.

Authenticated audio passes channel/duration/length bounds before decoding. The eight-position jitter queue, four-slot nominal playout delay and Opus packet-loss concealment bound loss handling. Link fragments carry at most 32 payload bytes with eight incomplete assemblies and a three-tick lifetime. A valid but malicious peer still exposes the decoder to adversarial compressed audio; it is covered by bounds, fuzzing and interoperability evidence, not declared harmless. [Opus RFC 6716](https://www.rfc-editor.org/rfc/rfc6716), [VBR privacy considerations](https://www.rfc-editor.org/rfc/rfc6562)

## Hostile radio and offline updates

`protocol::radio` exposes one data opcode, a maximum 38-byte link fragment, eight pending entries, expiration and a 32-command per-tick budget. Reset clears the queue without resetting the budget or leaving local update mode. There is no remote consent, clock, entropy, contact, firmware or debug command. Native incoming datagrams pass through this boundary before reassembly. Hardware separation of the BLE processor, interrupts, DMA and trusted peripherals is not simulated.

`protocol::update` models a small immutable verifier, two raw flash banks and a protected security-version floor. A 128-byte signed envelope binds target ID, security version, payload length and BLAKE2s digest. Only local approval enables installation. The inactive bank receives the payload first and header last; the whole image is read back and authenticated before the protected version advances. Boot authenticates both candidates, refuses versions below the floor and completes version advancement before handoff. Interrupted writes can select only a valid old or complete new image at the allowed version. Corrupting the new image after advancing the floor causes failure rather than vulnerable rollback.

No update is received over the media or radio protocol. No microSD filesystem or OpenPGP parser is included. A future release can offer GPG signatures for people verifying downloads, while the device accepts a narrow signed binary format. The trust anchor, immutable installation, secure counter and real flash/power behavior remain hardware assumptions. These tests do not demonstrate manufacturing or supply-chain security.

## Verification and limits

The suite retains the original isolation, codec, timing and dashboard gates and adds required lifecycle and platform groups. It tests storage failures, replay after restoration, contact substitution/revocation, fingerprint mismatch, invitation context mismatch, wrong update signatures/targets, every modeled write interruption, torn writes, entropy failures, radio resets and flooding, close and fresh-key restart.

Eight instrumented fuzz targets run for at least 120 seconds each. Five Kani harnesses cover handshake order, replay, consent, closed-call and monotonic-counter properties. The crypto tests include published Noise KK/XX vectors, 80 ML-KEM-768 cases, an independent Noise HFS test transcription and a live altered-startup scenario. Opus tests include upstream libopus interoperability, all twelve applicable official mono decoder vectors, and comparison of the in-place encoder constructor with its upstream constructor. The local Opus patch only adds in-place initialization; an integrity check verifies every upstream file and field coverage. This patch and the crypto adapters still need independent review.

The linked ARM diagnostic includes actual voice and selected policy paths under explicit capacity gates. Its public keys and deterministic entropy make it unsuitable for deployment. See [platform details](PLATFORM.md), [assurance case](ASSURANCE.md) and [recorded results](RESULTS.md). Snow describes itself as unaudited; finite fuzzing, passing tests and bounded model checking are evidence for specified properties, not proof of immunity to zero-days or an intelligence agency.
