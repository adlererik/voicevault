# VoiceVault C1 — LQFP144 prototype

**Native circuit input checked; Quilter full-layout run started at 19:42 CET on 16 November 2026. Not for fabrication.** The owner approved **STM32U5G9ZJT6Q** on 16 November 2026. C1 is a separate revision; the original C0 inputs, rejected Quilter results, isolated local repair and live B0 remain preserved.

[Open the running C1 job](https://app.quilter.ai/jobs/6afb49addfae511781423d99) · [Recorded launch and settings](../evidence/2026-11-16/c1-preparation/launch.json). Quilter continues in the cloud when this computer is off. No returned C1 candidate has been reviewed or accepted.

[KiCad project](voicevault-standalone-c1.kicad_pro) · [Root schematic](voicevault-standalone-c1.kicad_sch) · [Clean PCB input](voicevault-standalone-c1.kicad_pcb) · [Review inventory](BOM-REVIEW.csv) · [Exact circuit target](board-target.json) · [Checked evidence](../evidence/2026-11-16/c1-preparation/README.md) · [Package evaluation](../rev-c/LQFP_EVALUATION.md)

## Implemented circuit changes

| Area | C1 change |
|---|---|
| MCU | STM32U5G9ZJT6Q, LQFP144, 20 × 20 mm body, 0.50 mm pitch; native symbol and 144-pad footprint |
| Pin mapping | All 144 physical pins checked against pinned ST data, including all 55 connected signal functions and 91 connected supply/reference/signal pins |
| microSD | Move SD_SCK_MCU from PC0, which lacks SPI2_SCK, to unused PB13 / pin 70; retain PC1 MOSI, PC2 MISO and PC7 software chip select |
| Supplies | Map every LQFP supply/ground pin explicitly; retain both VDD11 pins and connect **both** VDD11DSI pins to MCU_VDD11 |
| New bypass parts | C113 at VDD pin 122, C114 at VDD pin 144, C115 at VDD11DSI pin 20; each 100 nF / 10 V |
| Debug | Retain STDC14 SWD/SWO/UART and reset on package-correct pins; development access remains open |
| CAD consistency | Preserve explicit single-pad no-connect net names for native parity. JP501 is a copper solder bridge excluded from purchasing BOM, with matching symbol/footprint attributes |
| Cloud settings | Replace all old MCU ball identifiers with LQFP pin numbers; 76 actual rail/reference bypass definitions. Exclude 12 oscillator, RF, reset, audio-filter and timing capacitors from the supply-bypass list |

Inventory is **199 electrical footprints, 13 probes and four mounting holes: 216 total**, versus C0's 213. The only changed existing component value is U1's order code. Every existing functional non-MCU connection and all four mounting-hole positions are preserved. New MCU wiring is a package remap plus the explicit SD-clock correction. [Delta checks](../evidence/2026-11-16/c1-preparation/circuit-delta.json).

The one SE050E2, larger QFN nRF52832, BQ24074 wired charger, replaceable protected lithium pack interface, audio codec/headset/mic disconnect, display/touch, microSD and local controls remain. Qi, NFC and haptics remain removed. Battery/holder/display assembly acceptance, charging safety and production-ready component sourcing remain open; this inventory is not an assembler-approved order file.

## Power-pin allocation

| LQFP supply | Pins | Local 100 nF assignments |
|---|---|---|
| VDD | 25, 41, 55, 69, 83, 89, 95, 109, 122, 144 | C7, C12, C17, C14, C10, C11, C9, C16, C113, C114 |
| VDDDSI | 13 | C8; C110 provides the existing additional bulk bypass |
| VDD11DSI | 14, 20 | C23, C115; connect to MCU_VDD11, never directly to 3.3 V |
| VDD11 | 67, 142 | C22, C24; C107/C27 retain the two 2.2 µF core capacitors |
| VDDSMPS | 65 | C26; C25/C108 retain existing input bulk capacitance |
| Other domains | VBAT 6, VREF+ 34, VDDA 35, VDDUSB 108, VDDIO2 131 | Existing domain-specific caps remapped and checked |

L1 remains between VLXSMPS pin 64 and MCU_VDD11. VSSSMPS pin 66 is ground. Correct values and pin associations are necessary; actual close placement, short switching loops, return paths, capacitor derating/ESR and measured regulation remain acceptance gates. The [full pin/net CSV](../evidence/2026-11-16/c1-preparation/mcu-pin-net.csv) includes unused and ground pins.

## Verification completed

Using KiCad **10.0.8**:

- Native ERC: **zero violations**.
- Native DRC of the off-board inventory: **zero layout violations**; explicit schematic-parity check: **zero mismatches**.
- Native netlist/PCB comparison: **711 functional pin-net assignments**, 826 exported nodes including explicit unused pins.
- All 144 MCU pin assignments, 55 signal functions and the retained 72 critical circuit/boundary checks pass. **Seven deliberately corrupted mappings are rejected**, including SD-clock, core/DSI power, debug, radio-to-secure-bus and C115 faults.
- **Five isolated native RF controls pass**: same-side feed allowed; opposite-side, inner-layer, wrong-net and out-of-corridor routes rejected. These fixtures do not route the real board.
- Full native ratsnest: **587 connections to route**. This is a new blank PCB, not the 62-open repaired BGA layout. There are **zero tracks, vias or copper pours**. All 212 non-mounting footprints are unlocked and parked outside the outline for Quilter to place.

With **ngspice 47**, 27 bounded passive core-output cases include the extra DSI bypass capacitor and sweep assumed inductance, bulk-cap derating and winding resistance. Observed idealized core extrema are **1.0148–1.1854 V**. The model has an ideal averaged source and **no MCU regulator control loop**: these are sensitivity results, not stability, power-integrity or hardware qualification. Six simulator-result checks ensure aborted/incomplete/non-finite outputs cannot be called successful. Unchanged C0 power/audio model limitations remain open.

Run `./hardware/check --rev-c1` for the native circuit/pin checks. [Evidence and additional test commands](../evidence/2026-11-16/c1-preparation/README.md).

## Placement and routing plan

Quilter owns electrical placement and routing. C1 contains no FreeRouting copper, prior cloud copper or manually designed electrical placement. The first outline remains a provisional **70 × 45 mm** rectangle. The 23.3 mm MCU courtyard bounding box fits the bare outline; populated-board fit must be established by placement and mechanical review. A larger serviceable rectangle remains an option if the actual layout requires it.

Use the standard JLCPCB **six-layer 4 mil preset**, S/GND/S/S/GND/S, **1.538 mm modeled thickness**, ordinary **0.45/0.20 mm vias**, and 0.50 mm board margin. This is a layout study against provisional published limits, not a manufacturing-stack approval or price quote. Two ground references are retained; a dedicated power plane is not required by this study. Real trace/pour current capacity and RF impedance still need review.

Connector/antenna regions express access and RF intent; Quilter chooses the actual poses. The five connector/antenna regions are assigned on the front face. Region auto-generation reports no additional groups; the other electronics remain for Quilter's full-layout placer. The antenna's front-region assignment is intended to avoid the previously observed back-side keepout-export error; verify the returned component side and keepout layer membership regardless. The cloud lists **zero BGA fanout entries**. There are 21 checked best-effort proximity requirements for the RF chain, feedback/ESD/filter/timing parts and crystal load capacitors; neither proximity checks nor region intent guarantees a valid layout. Custom KiCad rules are not fully understood by Quilter, so native return qualification remains mandatory.

The [downloaded cloud settings](../evidence/2026-11-16/c1-preparation/cloud-settings-verification.json) match the reviewed local data. All 18 downloaded server input CAD files [byte-match the checked source](../evidence/2026-11-16/c1-preparation/server-input-verification.json). Quilter computes the RF-feed impedance at **1 GHz**; the radio operates around 2.4 GHz, so this model is not RF qualification. The pin-count warning is consistent with the four connectors' extra mechanical `MP` pad identifiers; all functional pin identifiers exist and native parity passes. H1–H4 are intentionally mechanical-only. [Warning review](../evidence/2026-11-16/c1-preparation/parser-warning-review.json).

## Security and release limits

The STM32 remains the trusted plaintext/key/UI endpoint; the radio and compromised phone remain untrusted transport. This package change retains the approved hybrid X25519 + ML-KEM-768 suite, ChaCha20-Poly1305, verified contacts, local consent, replay handling and fixed audio records. It does not implement production firmware, prove physical isolation or improve cryptography by itself. [Threat model](../../docs/THREAT_MODEL.md) · [Assurance limits](../../docs/ASSURANCE.md).

No real silicon revision is verified. Read chip markings/REV_ID and apply ES0595 workarounds on the bench. Native rules and SPICE do not emulate STM32 audio/DMA, TrustZone enforcement, NXP provisioning or hostile-radio hardware behavior. C1's intended audio peripheral is **SAI1**; historical DK2 **SAI2** register/model tests must not be counted as C1 driver or DMA qualification. No full-device hardware simulation is claimed.

No purchase, paid service, quotation submission or fabrication order is authorized or performed. C1 is not ready to send to an assembler until returned routing, all native/DFM checks, component/assembly sourcing, mechanical fit, RF/power/audio review and hardware bring-up gates are satisfied.

Derived libraries retain their existing namespaces for continuity, not to identify the MCU package. [Library provenance](../rev-b/LIBRARY_NOTICE.md) · [ST pin-data license](../rev-b/reference/ST_PIN_DATA_LICENSE.txt) · [C1 references](references.json).
