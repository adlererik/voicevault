# MCU power-network review

The 32-component MCU/debug/power stage created on 2026-11-11 has expanded into the 296-component hierarchical B0 circuit. The MCU power network described here remains unrouted and unqualified. See README.md and STATUS.json for the complete current design.

## Corrected symbol

The installed KiCad `STM32U5G9ZJJxQ` symbol contained 142 unique pin numbers. It omitted the two **VDD11** balls **J9** and **D4**, which are shown in ST DS14102 Rev 5, Figure 10/Table 27 and in the Safe 7 MCU power sheet. Both pins are restored in the project's local symbol. The shared/global KiCad library was not modified. The exported native netlist now contains 144 unique MCU ball numbers, including the two restored pins. The checker rejects a symbol with either pin missing.

## Electrical intent

| Network | Connections in this draft |
|---|---|
| `VDD_3V3` | MCU VDD, VDDIO2, VDDA, VREF+, VDDUSB, VDDDSI and VDDSMPS, and the debug probe's target-voltage sense. The nPM1300 now supplies this rail; startup and current/thermal behavior still require qualification. |
| `MCU_LX` | VLXSMPS ball M7 to L1 pin 1 only. |
| `MCU_VDD11` | L1 pin 2, VDD11 balls J9/D4, VDD11DSI ball G3, and core decoupling. This is the internal regulator's core domain, **not the 3.3 V input**. Its operating voltage depends on the MCU regulator configuration. |
| `MCU_VBAT_3V3` | VBAT ball C2 and local capacitors, linked to the regulated rail through R101. It is not wired to the raw LiPo pack. |
| `GND` | MCU ground domains, debug grounds and all capacitor returns. Required physical return geometry remains unrouted. |

The capacitor reference numbers C6-C27 follow the published MCU power sheet where possible. The current candidate footprints use 0402 bypass, 0603 bulk/core and 0805 10uF parts rather than blindly copying the reference sizes. Extra parts C107-C112 and R101 make the adaptations explicit.

The core output uses **C27 and C107, each 2.2 uF and at least 10 V rated**, instead of copying the reference's single nominal 4.7 uF / 6.3 V part. ST DS14102 Rev 5 specifies two 2.2 uF output capacitors, ESR below 20 milliohms at 3 MHz, and at least 10 V rating. C25 is the 10 uF SMPS input capacitor. L1 is now a TDK VLS252012HBX-2R2M-1 candidate (102mohm maximum DCR, 2.3A manufacturer saturation-current criterion), retaining requirements **ISAT > 0.5 A and DCR < 200 milliohms**, as specified by ST. The reference's generic inductor entry does not establish those characteristics.

C108 adds a nominal 10 uF bulk capacitor; C109 adds 4.7 uF for the I/O supply requirement; C110/C111 add analog/reference capacitance; C112 adds a local backup-domain bypass. These are circuit requirements, not qualified manufacturer order codes. Exact MPNs, tolerance, DC-bias derating, temperature, effective capacitance, ESR, current rating and land patterns still require selection and review. Nominal capacitance printed in a schematic is insufficient.

The regulated VBAT link is a prototype choice with a clear limitation: **the RTC/backup domain is not maintained when that rail turns off**. The eventual power and firmware design must establish trusted time/state after reset before relying on invitation expiry. A raw 4.2 V fully charged LiPo must not be connected directly to this MCU supply pin. The final always-on backup arrangement is unfinished.

## What the checks establish

The KiCad-exported netlist verifies six debug signals, ground/voltage sense, all 144 MCU ball numbers, the distinct core/input/ground networks, the two-terminal switching-node path, regulated backup path and the grounds of all 28 capacitors. PCB DRC checks the current footprint geometry and reports the remaining airwires. No tracks, vias or planes have been routed. Capacitors are staged near the MCU and will need placement against the actual BGA balls, return paths and stackup.

These checks do not establish voltage regulation, decoupling effectiveness, stable startup, safe battery charging, boot behavior, timing, hardware isolation or RF/audio performance. ERC now passes with the added PMIC and other circuits; that does not validate their physical behavior. The manufacturing verdict stays blocked.

Primary reference: [ST DS14102 Rev 5](https://www.st.com/resource/en/datasheet/stm32u5g9zj.pdf), particularly Figure 10, Table 27 and section 5.1.6; [ST AN5373 supply guidance](https://www.st.com/content/st_com/en/technical-documents/an5373-getting-started-with-stm32u5-mcu-hardware-development-stmicroelectronics_asset/chunk-002-topic-an5611-power-supply-schemes.html). The pinned Safe 7 MCU power sheet is PDF page 3 in `reference/ts7_main_rev_d_sch.pdf`.
