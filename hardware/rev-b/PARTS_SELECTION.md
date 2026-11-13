# B0 parts selection — 13 November 2026

**Catalogue candidates, not an approved assembly BOM.** The live schematic and PCB have not been changed by this shortlist. No parts have been ordered, allocated by an assembler or priced as a complete landed build.

The native [circuit inventory](circuit-inventory.csv) contains 296 electrical components. It already identifies 58 design order codes. The [candidate CSV](parts-candidates.csv) adds nominal catalogue candidates for 129 components, grouped into 20 manufacturer order codes; 109 components still lack a candidate in this combined count. Existing order codes also need lifecycle, delivered-revision and assembly acceptance. The separate battery-capacitor correction below is not included in those 129 assignments.

The [selection record](reference/parts-candidates.json) binds this review to the inventory's SHA-256 and records references, ratings, primary manufacturer sources and downloaded-specification hashes where available. CSV quantities cover fitted parts for four boards only. They exclude attrition, minimum order/reel quantities, setup charges and off-board assemblies.

## What was selected and checked

| Component group | Candidate basis | Remaining qualification |
|---|---|---|
| Ordinary 0402 resistors | Yageo RC, 1%, 0.063 W catalogue rating; nominal value and footprint checked against each reference | Actual dissipation, voltage, temperature, pulse stress and assembler allocation |
| Zero-ohm links | Yageo RC 0402/0603 jumper variants; 1 A catalogue current and maximum 0.05 Ω resistance recorded | Actual current, heating and measurement burden; these are not ideal shunts |
| R606/R607 and R707 | Panasonic 0402 parts with 0.1 W catalogue ratings, matching the circuit's printed minimum | Pulse/temperature derating and actual dissipation |
| R709–R712 | Panasonic ERJP06F2000V, 200 Ω, 0805, 0.5 W catalogue rating | Backlight branch heat, board thermal geometry and fault behavior |
| Ordinary 100 nF bypass | Yageo X7R: 16 V 0402 and 50 V 0603 variants | Effective capacitance, aging, ripple, temperature and local return geometry |
| 12 pF crystal loads and C610 33 pF | Yageo C0G, 50 V, 5%, 0402 | Actual crystal/board stray capacitance, startup and RF behavior |
| C27/C107 MCU core output | Yageo CC0603KRX7R6BB225, 2.2 µF, 10 V, X7R, 0603 | ST's effective-capacitance and maximum ESR requirements, regulator stability and return paths |

Manufacturer capacitor model plots are **typical simulations, not guaranteed maximum specifications across process, voltage and temperature**. The inspected C27/C107 plots are useful screening evidence but do not close the MCU regulator's ESR/stability gate. A nominal value, larger voltage number or passing ERC is insufficient to approve a capacitor.

Higher-power resistors were selected explicitly rather than applying a generic 0.063 W part to every resistor. NFC's 2 Ω resistors remain unselected pending RF/current/pulse review. Unselected bulk capacitors need DC-bias and regulator-loop checks rather than a blind value/package substitution. Exact manufacturer sources and per-part limits are linked in the JSON/CSV.

## Separate battery-decoupling correction

The draft C502 on `BAT_PACK` is 100 nF / 10 V / 0402. Nordic's nPM1300 reference configuration uses **2.2 µF / 16 V / X7R / 0603 at VBAT**. An isolated proposal changes C502 accordingly and preserves its two logical `BAT_PACK`/`GND` connections. This is the battery capacitor, not the separate VBUSOUT capacitor C118. [Nordic reference circuitry](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/hw_layout/ref_circuitry/frontpage.html-qfn32?contentId=n4BHJZNbrgZiW0RgLaSMGw).

The reference's Taiyo Yuden EMK107BB7225KA-T has a renamed general-purpose successor, **MSASE168BB7225KTNA01**. The manufacturer lists that candidate as preferred/mass production; supplier allocation and delivered revision remain unconfirmed. [Manufacturer catalogue](https://ds.yuden.co.jp/TYCOMPAS/ap/sm/detail?pn=MSASE168BB7225KTNA01&u=M).

On the isolated copy, C502 was replaced with the native 0603 footprint and automatically positioned using actual courtyard/copper/drill obstacles. The copy starts from the previously reviewed three-capacitor placement proposal, not the live failed routing checkpoint. Verification found:

- All 323 native schematic net records and all PCB pad/net assignments unchanged.
- All 473 source copper items, antenna reservations and outline unchanged.
- Native ERC: zero reported errors/warnings, with the source project's four existing ignored check classes explicitly retained in the report.
- Native initialized zone refill/DRC: zero layout errors, 67 dangling-copper warnings and 505 full native open connections.

[Hash-bound proposal, exact changes and position](../evidence/2026-11-13/quilter/battery-correction/verification.json) · [Native netlist comparison](../evidence/2026-11-13/quilter/battery-correction/netlist-comparison.json) · [ERC report including ignored classes](../evidence/2026-11-13/quilter/battery-correction/erc.rpt).

**This correction is absent from the live board and the running Quilter input.** It needs fresh routing and return-path review on the actual returned board, effective-capacitance/ripple checks and battery/charger bench validation. Passing these CAD checks does not establish safe charging or a working power supply.

## Before assembly release

Complete the remaining exact selections and circuit/footprint reviews, resolve NRND/provisioning issues, qualify derating and assembly process, obtain a complete compatible BOM/CPL and manufacturer DFM acceptance, and test assembled prototypes. The display, battery, coil/ferrite, actuator, thermistors, harnesses and enclosure also require an explicit assembly scope. The current shortlist makes those decisions reviewable; it is not permission to fabricate or buy anything.
