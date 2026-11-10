# The VoxBastion device vision

VoxBastion is intended to become a physical encrypted voice endpoint. The current software lab is its engineering foundation: a place to make the protocol, failure behavior and resource demands inspectable before committing to a board.

The distinctive challenge is keeping voice, identities and user decisions on a small endpoint while the carrier is actively hostile. The project combines protocol engineering, embedded Rust, audio processing, trusted interaction and measurable security boundaries.

## The phone's role

Assume the phone is already compromised by an attacker with NSA-class capabilities and the telecommunications path is controlled. The phone can forward, record or sabotage what it receives. It must not be needed to keep an identity secret, approve a call, generate trusted entropy or authorize firmware.

The future endpoint encrypts outgoing media before passing it to the phone and authenticates incoming media before decoding it. The phone still handles public signaling/routing data and exposes delivery metadata. This is a new endpoint boundary, not a promise of anonymity or guaranteed availability.

## The intended physical arrangement

| Element | Intention | Current status |
|---|---|---|
| Independent voice device | A compact dedicated endpoint inspired by wallet-style host separation | Software model and freestanding ARM diagnostic |
| Trusted color display and controls | Verified contacts, peer information, pairing comparison and local call decisions stay on the device | Policy APIs and synthetic local control; physical UI not built |
| Analog headset jack | Wired microphone/headphone audio connects to the endpoint, not the phone | Synthetic PCM/Opus/WAV pipeline; no ADC/DAC/headset driver |
| Physical mic disconnect | A local hardware action can disconnect capture | Hardware requirement, not a simulated switch security claim |
| Separate BLE controller | Minimal standards-compliant services and a bounded ciphertext-data interface | Hostile-radio policy model; real radio/driver/isolation work pending |
| Own battery and inductive charging | No power/data cable to the phone during intended use | Architecture requirement; no power hardware built |
| Trusted MCU and secure elements | Protect persistent secrets/state and isolate radio/audio/control responsibilities | STM32U585-class capacity reference; chip operations and bill of materials undecided |
| Protected first-stage verifier | A small manufacturing-protected boot trust root checks later code | Signed-image/two-bank/version model; no physical immutability established |
| Local offline firmware introduction | Physically initiated microSD updates, bounded image parsing and on-device verification | Raw-image policy and fault tests; no SD filesystem/driver |
| Reproducible release artifacts | Users can compare independently built payloads and separately verify signatures | Pinned inputs/provenance exist; a bit-reproducible production release pipeline is future work |
| Decentralized invitation carriers | Interchangeable untrusted relay/discovery adapters | Future investigation; no Nostr deployment |

The Safe 7 inspiration includes a separate MCU, secure elements, battery/display and host separation. VoxBastion is not a wallet, an endorsed Trezor derivative or a claim that a wallet bill of materials will sustain real-time voice. The exact part, memory layout, supported chip operations and peripheral design need selection and measurement. [Device rationale](DEVICE_RATIONALE.md)

## The acoustic requirement matters

The intended host-phone setup removes the phone's microphones and speakers. Otherwise spyware can activate the microphone and record a conversation without decrypting any packets. A wired closed headset and local mic disconnect belong to the device plan, but neither proves the absence of acoustic leakage. Remaining pickup paths, other nearby devices, the user's surroundings and an intentional recording by the recipient require separate consideration and testing.

No phone has been modified by this repository. The software run does not demonstrate that a specific phone is acoustically safe after modification.

## Pairing must be understandable on the trusted device

Two people should be able to establish a contact without trusting either phone's screen. The implemented software ceremony uses full transcript-fingerprint comparison and authenticated confirmation on both sides. The physical transfer method—contact pads, QR exchange or another bounded mechanism—has not been selected. A user-friendly short SAS needs a reviewed design and usable error/attempt handling.

The goal is a meaningful local decision: which peer is being enrolled or called, what evidence was checked and whether the user approves. A phone-supplied name or a relay's claim must not substitute for that decision.

## Optional physical tamper evidence

The original enclosure idea uses clear plastic/polycarbonate with a random glitter pattern, reference photos and a signed per-unit manifest. A recipient would verify the manifest with an independently obtained public verification key and compare the received enclosure with the authenticated reference.

This remains an optional research idea. No enclosure or visual-verification method has been built or evaluated. A photograph does not prove the absence of hidden modifications, and supply-chain attacks are outside the current requested threat model. The manufacturer's private signing key must never be given to recipients.

## What would make the project ready to advance?

A successful encrypted call is necessary but insufficient. The software stage needs repeatable hostile-input/failure tests, independently reviewed protocol and integration code, a usable pairing specification, durable-state design and measurements tied to the chosen platform. Hardware then adds interrupt/audio deadlines, radio containment, entropy quality, flash failures, UI integrity, power and acoustic tests.

The project grows by passing these gates and preserving evidence, not by treating a promising simulation as a finished protective device. [Roadmap](ROADMAP.md) · [Assurance case](ASSURANCE.md)
