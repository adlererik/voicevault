# Hearing the firmware's actual received speech

The local C1 device prototype now has a **received-audio monitor**. The speech is generated offline by eSpeak NG 1.52.0; no microphone, online voice service or paid API is used. Public test identities and keys remain in use. This is a development experiment, not a private calling service or flashable release.

## Start a speaking call with a transport attack

```bash
cd /home/erikclean/src/secure-voice-lab
./firmware-lab ui
./firmware-lab device --auto-call --attack tamper --wall-seconds 600
```

Open <http://127.0.0.1:8765/firmware>. The new **Hear the received test voice** link near the top jumps to the player. Click **Listen**. Browser audio requires this explicit click; sound does not start automatically.

`--auto-call` performs the test pairing, verifies every displayed fingerprint character and starts the call through actual local touch events. It then leaves the call running so you can listen and use MUTE/END. The independent native peer's local decisions remain trusted supervisor fixtures. `--self-test` instead runs the finite call/mute/end checks and finishes; the two modes cannot be combined.

Alice says: “This is Alice. Voice Vault. One, two, three.” Bob says: “This is Bob. Encrypted voice test. One, two, three.” The voices repeat. These are original generated fixtures, not recordings of a person.

## Choose what you hear

| Player choice | Actual path |
|---|---|
| **Device hears Bob — ARM decoded** | Native Bob speech → Opus → encrypted records → simulated UART/transport → ARM authentication, jitter/PLC and Opus decode → SRAM observation ring → browser |
| **Bob hears Alice — native peer decoded** | ARM Alice speech → ARM Opus/encryption → simulated UART/transport → native Bob authentication and Opus/PLC → browser |

The default is the ARM receiver. The player never plays the original speech fixture as evidence that a call worked. Neither endpoint supplies its raw source PCM to the phone/transport interface. Only the trusted development host observes the receiver output, after the real application returns playout samples.

## Buffering and honest quality limits

The emulator can execute much slower than wall-clock time. The player collects **0.50 seconds of received audio** before playing a chunk at its normal sample rate. It pauses to refill when necessary and plays the final shorter chunk after the call finishes. This produces buffered bursts, not a claim of real-time conversation latency.

Every captured output frame is retained: decoded speech, actual Opus packet-loss concealment, encrypted-filler silence and startup silence. The player does not discard loss frames or substitute clear source speech. Skipped virtual-time slots remain in record metadata and the visible counters; playback/recording concatenate actual produced frames rather than inserting additional gaps for every skipped slot.

The software speech input advances per encoded record so a slow emulator does not skip its source words. This is an explicit input fixture, not a real microphone model. Missed deadlines, loss and concealment can still make received speech choppy or difficult to understand. Hearing a voice establishes an observable software path, not physical audio-driver quality, fixed-cadence privacy or hardware readiness. `cadence_qualified` and `hardware_qualified` remain false.

## Stop, replay and download

Use END on the simulated screen to end an automatic call, or Ctrl+C in its terminal. The automatic-call mode then closes its peer and saves the recordings. The player shows a standard received-recording audio control and a **Download this receiver's WAV** link once a completed receiver stream exists. Choose the receiver with the direction selector.

Each run directory contains:

| File | Content |
|---|---|
| `received-arm.pcm` | Bounded framed observations of actual ARM playout |
| `received-peer.pcm` | The native peer's actual playout observations |
| `received-arm.wav` | ARM-received samples, unchanged, mono 16 kHz signed 16-bit |
| `received-peer.wav` | Native-received samples in the same format |
| `report.json` → `audio_observation` | Frame/kind counts and recording names |
| `build.json` | ELF/source identity, including generated speech fixture hashes |

The framed `.pcm` files include 12 bytes of metadata per frame and are not ordinary raw PCM files. Each 652-byte record is little-endian sequence, virtual slot and kind (`u32` each), followed by 320 signed 16-bit samples. Kinds are 0 decoded audio, 1 filler silence, 2 loss/malformed concealment and 3 startup silence. The WAV body is exactly the concatenation of those sample payloads.

## Boundaries and verification

The ARM publisher is a 32-record SRAM ring with one main-loop writer. The count is published after a complete record; the host reads it while Renode is paused. An overrun, wrong sequence or malformed record fails observation instead of fabricating sound. Public input speech occupies a separate actual C1 SRAM bank; existing stack/driver reserves are retained and the ELF must still fit the declared bank ranges.

`/firmware/audio` and `/firmware/recording` are bounded GET outputs on the existing loopback service. They accept only the current device run's audio identifier and a fixed receiver name. No file path or source fixture can be requested. Wrong runs/profiles, path escapes, malformed counters and cross-origin requests are refused. Recordings are served only after completion. Native scored timing is not an eligible source and does not gain monitor files through this feature. No audio upload, microphone permission, network call or new phone/radio command exists.

Tests check byte-for-byte equality between observation records, WAV payloads and HTTP playback; batching, incomplete tails, source/profile/cursor restrictions, symlink escape, invalid metadata, silent filler and completion/origin gates. The integrated ARM call still has to perform real pairing, hybrid establishment, authentication, decoding, mute and END. Finite tests are not an independent security audit or physical acoustic qualification.
