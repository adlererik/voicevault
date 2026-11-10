# The intended device

VoxBastion's intended product is a small, dedicated voice encryption endpoint inspired by the Trezor Safe 7's separation of sensitive operations from a general-purpose host. It is not a wallet or a modified Trezor firmware image. Exact component selection is still open, and copying a wallet's component list would not demonstrate suitability for continuous audio.

The trusted boundary includes the wired headset microphone and headphone path, codec, session keys, identities, contact verification, call controls and display. A separate battery and inductive charging remove the need for a phone cable. A separate BLE controller should have a narrow ciphertext interface and no access to trusted audio, memory, flash or debug. The physical BLE stack remains standards compliant; reducing the application services and authority is preferable to creating an incompatible link protocol.

| Requirement | Software evidence now | Work before hardware reliance |
|---|---|---|
| Phone used only as a modem | Two independent hostile phone processes, restricted IPC, authenticated encrypted audio | Real BLE/controller isolation, DMA/MPU boundaries and driver review |
| Audio stays on the device | Actual Opus encode/encrypt/decrypt/decode using synthetic samples | Analog jack, ADC/DAC, headset and physical microphone disconnect |
| Trusted contacts and consent | Confirmed enrollment, pinned keys, sealed snapshots, verified invitations, local consent state | Trusted display/input drivers, usable fingerprint comparison, persistent secure-element integration |
| Device-local entropy and secrets | Source failure model, entropy injection, zeroizing owned keys | Independent entropy measurements, supported chip operations, complete erasure review |
| Offline firmware updates | Signed raw images, two banks, protected version model, interrupted-write tests | Immutable root installation, actual flash/power-loss behavior, release-key custody and reproducible production images |
| Continuous fixed-format traffic | 128-byte records per 20 ms active slot, CBR Opus, filler, no catch-up bursts | Real-time MCU/interrupt measurements and radio-observed scheduling |
| MCU capacity | Linked Cortex-M33 execution and explicit memory budgets | Board selection, exact SRAM/ECC configuration, worst-case timing and power |
| Clear enclosure and photographed glitter | Future design idea; no physical evidence | Separate tamper-evidence study if that scope is later included |

## Why this differs from an ordinary phone

A calling app needs access to plaintext audio at its endpoint. If the phone operating system is already controlled by an attacker, encryption on that same phone cannot keep its microphone samples or playback away from that operating system. A separate endpoint can change which computer must be trusted: the phone forwards records while the dedicated device processes the conversation and decides which peer is authenticated.

This benefit depends on the entire audio path staying outside the phone. A headset paired to the phone, a phone microphone left active nearby, or a trusted device that permits the phone to update its firmware would undermine that boundary. The proposed removal of the phone's microphones and speakers is a future hardware requirement; this repository does not modify any phone or demonstrate the absence of other acoustic pickup paths. Nearby devices and the other participant can also record speech.

The device cannot stop the phone or telecom operator from refusing delivery. It cannot hide a subscriber's cellular location or make call timing and duration disappear. Fixed active-call records reduce a particular speech/silence signal, while traffic correlation and endpoint identity remain separate problems. There is no always-on cover traffic between calls in this model.

## Choices still open

Trezor currently lists an STM32U5G Cortex-M33 at 160 MHz for Safe 7, alongside TROPIC01 and OPTIGA. The lab uses an STM32U585-class capacity gate as its explicitly named reference, rather than claiming an exact Safe 7 component clone. The final bill of materials remains open. [Trezor hardware specification](https://trezor.io/learn/security-privacy/how-trezor-keeps-you-safe/trezor-hardware-built-in-security) Secure elements need to be selected against supported Ed25519/X25519 operations, key custody, counters, transactional behavior, endurance and integration costs. Some operations may remain in trusted MCU RAM. A secure element does not automatically keep all live audio keys inside it.

Nostr is a possible future invitation carrier, not part of the implementation. Nostr's standard event signatures are BIP340 Schnorr on secp256k1, rather than Ed25519. Device identities can remain Ed25519 behind an independently authenticated opaque invitation adapter. Decentralized relays alone do not remove metadata or authenticate a caller. [Nostr NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md)

Avoiding NIST primitives is a preference for the end-to-end suite, not a claim that the entire system has none. Ed25519 includes SHA-512. Standard BLE uses other cryptography. Classical X25519 is not post-quantum; any future hybrid needs a reviewed construction and separate interoperability, size and timing work. [Ed25519 specification](https://www.rfc-editor.org/rfc/rfc8032), [Bluetooth LE primer](https://www.bluetooth.com/bluetooth-le-primer/)

For any signed shipping-photo scheme, the recipient verifies the manifest with an independently obtained **public** verification key. The manufacturer's private signing key is never sent to recipients. Supply-chain attacks are excluded from the current requested threat model, so no protection against device replacement is claimed here.
