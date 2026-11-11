# Cryptographic choices

VoiceVault chooses a small, fixed end-to-end suite and gives each primitive a specific job. Cryptography runs at the trusted voice endpoints. The phone is a carrier, and BLE link encryption is not the confidentiality boundary. This document explains the engineering reasons for the present choices, rather than treating algorithm names as a security certificate.

## The suite at a glance

| Operation | Selected construction | Where it is used |
|---|---|---|
| New-contact enrollment | `Noise_XX_25519_ChaChaPoly_BLAKE2s` | Encrypted signed contact exchange and transcript comparison |
| Call establishment | `Noise_KKhfs_25519+MLKEM768_ChaChaPoly_BLAKE2s` | Calls between already pinned contacts, bound to accepted invitations |
| Key agreement | X25519 | Independent static DH keys and fresh call/enrollment ephemerals |
| Post-quantum key establishment | ML-KEM-768 | Fresh initiator keypair and responder encapsulation for every call |
| Signatures | Ed25519 | Identity/DH binding, invitations and offline firmware envelopes |
| Record protection | ChaCha20-Poly1305 | Audio, consent/ready controls and contact snapshots |
| Hashing | BLAKE2s-256 | Noise suite, domain-separated application bindings, firmware payload digests and modeled entropy conditioning |
| Session derivation | Noise's HMAC/HKDF using BLAKE2s | Handshake chaining and separate directional transport keys |
| Audio representation | Opus | 16 kHz mono, 20 ms frames, 24 kbit/s CBR, DTX off |

The implementation selects this suite explicitly. There is no phone-controlled cipher negotiation. A future cryptographic migration needs a versioned protocol design and compatibility tests; changing a library flag is not a safe migration strategy.

## X25519: agree on a secret without sending it

X25519 supplies Diffie–Hellman shared secrets from a local private key and a peer public key. Compact public keys and a well-specified operation make it a practical fit for a constrained endpoint. Fresh ephemeral secrets are generated for each handshake; static DH public keys are pinned through verified contact records. The local adapter rejects all-zero shared results.

X25519 does not establish a human identity by itself. Without authenticated keys, an attacker could conduct separate exchanges with both parties. Noise authenticates the call against the pinned static keys, and the enrollment ceremony establishes which contact to pin. The signing and DH keys are generated separately; the project does not reuse one private key for both operations. [X25519 specification, RFC 7748](https://www.rfc-editor.org/rfc/rfc7748)

## Ed25519: authorize identities and statements

Ed25519 signs the binding between an identity public key and its separate X25519 public key. It also authenticates invitation fields and the offline firmware envelope. Public verification means a recipient can check a statement without possessing the private signing key. Deterministic signing avoids requiring a separately generated random nonce for each signature, although secret-key creation still needs trustworthy randomness.

A valid self-signature proves control of that signing key; it does not prove that the signer is the person named Bob. A contact becomes trusted only after independent enrollment or verified out-of-band pinning. Ed25519 uses SHA-512 internally. [EdDSA specification, RFC 8032](https://www.rfc-editor.org/rfc/rfc8032)

Firmware signing has a different authority from contact signing. In production, the device's trusted release-verification key must be provisioned independently; a caller cannot authorize firmware merely by being an authenticated contact. Tests use explicitly public release-key fixtures, never production release secrets.

## ChaCha20-Poly1305: privacy and integrity together

ChaCha20 encrypts the contents, and Poly1305 authenticates them. The combination lets a receiver reject altered data before accepting it as media or stored state. The selected AEAD uses a 256-bit key, a 96-bit nonce and a 128-bit tag. Encrypting alone would not supply this authenticity property. [AEAD specification, RFC 8439](https://www.rfc-editor.org/rfc/rfc8439)

The choice suits a software-first, portable implementation and the owner's preference for these primitives. It does not depend on an AES accelerator being available. This is not a claim that it will outperform hardware AES on the eventual MCU; real throughput and energy need measurement. RustCrypto documents architecture-dependent constant-time multiplication requirements, so target-specific timing and side-channel review remains necessary. [RustCrypto security notes](https://docs.rs/chacha20poly1305/0.10.1/chacha20poly1305/#security-notes)

Nonce handling is essential. Noise transport uses a 64-bit sequence encoded in the 96-bit nonce with its specified fixed prefix. Each direction has a different key. Sending counters increase; controls reserve sequences 0 and 1; media starts at 2. A fresh handshake is required before a reset can start a new sequence space. The public sequence changes the AEAD nonce, so tampering with it invalidates the tag.

Stored-contact snapshots use a separate key and protected generation as their nonce source. They are not encrypted under media keys. Generation advancement precedes snapshot release; losing the latest snapshot can therefore fail closed rather than silently reuse old state.

## BLAKE2s: hashing with an embedded-oriented profile

BLAKE2s provides a 256-bit digest and is oriented toward 32-bit platforms. It is part of the chosen Noise suite and also hashes versioned, domain-separated application statements. Firmware signatures bind the payload digest as well as target, version and exact length. Hashing alone is not firmware authorization: a trusted signature is also required. [BLAKE2 specification, RFC 7693](https://www.rfc-editor.org/rfc/rfc7693)

Different jobs use different domain labels. Contact identity binding, accepted invitations, contact storage and firmware images must not be interchangeable statements. The historical `quietlink` labels remain unchanged during the repository rename, preserving compatibility and recorded vector results.

The entropy model hashes contributions from onboard sources with a protected generation and source identifiers. This conditions inputs; it cannot create unpredictability if the contributing hardware sources are predictable. Stuck/uniform checks and the two-source policy do not establish a measured entropy bound.

## HMAC/HKDF: derive keys inside the established protocol

The handshake needs more than a raw DH result. Noise specifies the transcript processing, chaining key and HMAC/HKDF operations that turn handshake secrets into the appropriate cipher keys. VoiceVault uses that schedule and Noise's directional transport keys. It does not add a competing application key schedule or directly use an X25519 output as an audio key. [Noise cryptographic functions and processing rules](https://noiseprotocol.org/noise_rev34.html), [HKDF background, RFC 5869](https://www.rfc-editor.org/rfc/rfc5869)

A signature, a hash and a DH operation are not a complete authenticated protocol merely because each is sound separately. Their composition, key confirmation, identity binding and state transitions are why Noise is used.

## Why XX for enrollment and hybrid KK for calls?

**XX** supports exchanging static public keys during first enrollment. The model carries signed identity records inside encrypted handshake messages, verifies that the record's DH key equals Noise's authenticated remote static key, then compares the full 256-bit transcript fingerprint through the trusted local ceremony. Each side also sends an encrypted fingerprint confirmation. Both local approvals and both confirmations are required.

**KKhfs** extends the known-peer KK pattern with a fresh ML-KEM-768 contribution. The pinned static DH keys authenticate the exchange. The prologue binds both verified Ed25519 identities and the signed offer and acceptance. The experimental HFS modifier mixes the KEM secret into Noise’s existing key schedule. Local consent and encrypted Confirm/Ready still gate audio. [Protocol and wire format](POST_QUANTUM.md)

The full fingerprint is deliberate. A six-digit truncation is not an equivalent replacement; a shorter human comparison needs a reviewed ceremony, appropriate commitment/attempt controls and usability tests. Physical key-transfer pads, QR exchange or other enrollment transport are future decisions. Physical proximity alone does not authenticate arbitrary bytes supplied by a compromised phone.

Snow implements the Noise state machine. The project adds narrow secret-owning DH/cipher adapters using curve25519-dalek and RustCrypto; published KK and XX vectors exercise those adapters. This is established cryptography with local integration code that still needs review. Snow's project states that it has not received a formal audit. [Snow source and documentation](https://docs.rs/snow/0.10.0/snow/)

## Forward secrecy, lifetime and erasure

Fresh ephemerals and correct erasure are intended to protect completed calls if long-term identity keys are stolen later. This does not protect a live call after its current endpoint/media secrets are extracted, or heal a compromised device automatically.

A media epoch is limited to 15,000 local 20 ms slots. At expiry this version closes, drops its owned transport-key objects and requires a fresh authenticated handshake. It does not yet renew seamlessly during a long call. Session close cannot be reversed by a remote message or a later consent call.

Identity, storage, entropy, owned DH/KEM secrets and cipher keys use zeroizing owners. The local Snow patch clears chaining state and selected DH, KEM, HMAC and HKDF buffers. Primitive internals, compiler-generated copies and memory remnants require further review. [Erasure boundaries](POST_QUANTUM.md#what-is-erased)

## Opus, CBR and padding: encryption does not hide every pattern

Opus supplies speech compression and established interoperability targets. It is not encryption. The initial profile is mono 16 kHz, 320 samples per 20 ms frame, 24 kbit/s hard CBR, no FEC and no DTX. Speech and encoded silence use a 60-byte packet. The outer authenticated record is always 128 bytes; filler covers mute and encoder underruns when the local scheduler can emit. [Opus specification, RFC 6716](https://www.rfc-editor.org/rfc/rfc6716)

This addresses speech/silence information carried by record size and intended emission cadence. It does not hide call duration, network identity, location, correlation or overload-related timing errors. Variable-rate encrypted audio can leak information, which is why compression settings and the outer schedule are part of the security design. [VBR privacy guidance, RFC 6562](https://www.rfc-editor.org/rfc/rfc6562)

## Rust, secure elements and BLE are complementary choices

Safe Rust reduces memory-safety hazards in parsing and state handling; it does not prevent logic errors or prove a protocol correct. The codec and embedded initialization contain reviewed-boundary work, dependencies and unsafe internals that still need independent scrutiny. `no_std` builds and fixed queues make the embedded transition testable; they do not create hardware isolation.

Secure elements are intended for persistent secrets/protected state where the selected chips support the necessary operations. The model does not prove that every live key can remain inside one, or that a chosen device supports Ed25519 and X25519 directly.

BLE is a future transport on a separate, untrusted controller. Its own standard cryptography does not replace the endpoint suite. The plan is a standards-compliant stack with minimal services and authority, not deleting arbitrary protocol requirements. [Bluetooth LE primer](https://www.bluetooth.com/bluetooth-le-primer/)

## ML-KEM and the recorded-call requirement

The owner selected ML-KEM-768 to protect recordings made today if a future attacker can break X25519. The portable implementation lets the lab exercise the same KEM on the desktop and Cortex-M33. VoiceVault requires the hybrid suite for each new call and uses classical Ed25519 identity authentication at call time. Captured traffic remains protected only under the assumptions of the hybrid construction and session-secret erasure. The owner made an explicit exception for the NIST-standardized KEM. [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) · [Protocol, tests and scope](POST_QUANTUM.md)
