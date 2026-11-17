# VoiceVault C1 — local repair 01

**Preserved earlier repair checkpoint. Incomplete: 18 native open connections. Not for fabrication.**

[Open KiCad project](voicevault-standalone-c1.kicad_pro) · [Native PCB](voicevault-standalone-c1.kicad_pcb) · [Checked evidence](../../evidence/2026-11-17/c1-local-repair/README.md).

The original uploaded C1 input, raw Quilter return and live B0 board are preserved. The owner explicitly authorized local KiCad repairs. All 216 component values/pad nets and four mounting anchors remain intact. The original 0.20 mm hole-clearance requirement and antenna rules remain enforced.

The raw cloud return had six opens, plus antenna/hole failures and inadequate power placement. Moving power parts and removing invalid copper produced 50 connections to rebuild in the first repair. That repair reached 18 opens. The second study puts the MCU inductor and core-output capacitor on the MCU face; its rebuilt switching trace is about 2.924 mm with no via. Its routing remains in progress. These are different repair checkpoints, not contradictory counts for one board.

Native checks cover actual connectivity, source-rule clearance, schematic parity, all 144 MCU pins, 55 signal functions, 72 critical pin checks and seven corrupt-mapping controls. They do not qualify real power stability, RF/antenna performance, analog audio, mechanical fit, component availability, assembly or hardware security. Reference labels are retained on assembly layers; overlapping silkscreen text was moved to drawing/assembly layers.

The stack remains six-layer S/GND/S/S/GND/S with ordinary through vias. No signal copper may be added to the two reference planes. No purchase, order or manufacturing submission has been made.

[Original C1 circuit and outstanding hardware gates](../README.md) · [Quilter support findings supplied by the owner](../../evidence/2026-11-17/quilter-engineering-reply/README.md).
