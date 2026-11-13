# B0 parts selection — 13 November 2026

**Catalogue candidates, not an approved assembly BOM.** The live schematic and PCB have not been changed by this shortlist. No parts have been ordered, allocated by an assembler or priced as a complete landed build.

The native [circuit inventory](circuit-inventory.csv) contains 296 electrical components. It already identifies 58 design order codes. The [candidate CSV](parts-candidates.csv) adds nominal catalogue candidates for 182 components, grouped into 29 manufacturer order codes; 56 components still lack a candidate in this combined count. Existing order codes also need lifecycle, delivered-revision and assembly acceptance. The separate battery-capacitor correction below is not included in those 182 assignments.

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
| Radio's 16/12 pF loads, 100 pF and 100 nF bypass | Separate 0201 manufacturer variants preserving each printed nominal value, C0G/X7R class and 2/5/10% tolerance | Actual crystal load/stray capacitance, startup, decoupling and RF behavior |
| Remaining 2.2 µF bypass and selected 1/4.7/10 µF MLCC groups | Separate package/voltage/dielectric selections; the 0805 10 µF candidate is 25 V X5R | Effective capacitance under DC bias, ripple, regulator-loop and thermal requirements; X5R's +85 °C limit remains binding |
| C611/C612 headphone coupling | KEMET T520D227M006ATE025, 220 µF, 6.3 V, polarized polymer, D/7343 case | Polarized land pattern, DC operating point, leakage, transients/reverse stress and dummy-load/pop tests |

Manufacturer capacitor model plots are **typical simulations, not guaranteed maximum specifications across process, voltage and temperature**. The inspected C27/C107 plots are useful screening evidence but do not close the MCU regulator's ESR/stability gate. A nominal value, larger voltage number or passing ERC is insufficient to approve a capacitor.

Higher-power resistors were selected explicitly rather than applying a generic 0.063 W part to every resistor. NFC's 2 Ω resistors remain unselected pending RF/current/pulse review. Bulk-capacitor candidates do not close DC-bias or regulator-loop requirements: this is particularly important for C25's MCU SMPS input and the Qi rectifier/output capacitors. ST's wearable example identifies Murata GRM21BR61E106KA73L for its 10 µF / 25 V / 0805 group; the shortlisted Yageo part is a nominal alternative requiring its own effective-capacitance/ripple qualification, not a proven equivalent. [STWLC38 DS14078 Table 37](https://www.st.com/resource/en/datasheet/stwlc38.pdf). Exact manufacturer sources and per-part limits are linked in the JSON/CSV.

The screening deliberately rejected Yageo CC0201ARNPO9BN1R0 for C203: its retrieved manufacturer specification states ±0.5 pF at 1 pF, whereas the circuit's 5% requirement is ±0.05 pF. No tolerance was relaxed. C209 also remains open: the evaluated 1 µF / 0402 candidate has 10% tolerance, while Nordic's reference C9 specifies 5%. These rejected/held choices and source hashes are recorded in the selection JSON. Similar names or a plausible order-code suffix do not establish compliance.

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
