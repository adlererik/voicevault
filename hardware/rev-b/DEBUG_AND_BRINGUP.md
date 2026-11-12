# Computer connection and first-board testing

Use an external **STLINK-V3MINIE** with its USB connection to the trusted development computer and STDC14 cable to J101 on the prototype. This replaces the development board's programming facility. It is a programming/debug probe, not a compute module on the VoiceVault PCB. The new PCB carries the actual application MCU.

The SWD connection supports loading diagnostic firmware, stopping the MCU, breakpoints, register/memory inspection and fault diagnosis. UART provides status and measurements; SWO is optional trace. Codex or Astra can invoke the installed host tools and interpret their results once probe/target support and access have been validated. KiCad MCP edits the PCB; it does not program a physical MCU or replace a debugger.

## J101 STDC14 mapping

This follows ST UM2910 Rev 4 table 4. All UART names below describe the **target MCU** direction.

| Pin | Board connection | MCU ball / function |
|---|---|---|
| 1, 2 | Not connected | Reserved by ST |
| 3 | VDD_3V3 | Probe measures target I/O voltage; **not a supply output** |
| 4 | MCU_SWDIO | C10 / PA13 |
| 5 | GND | Ground |
| 6 | MCU_SWCLK | B11 / PA14 |
| 7 | GND | Ground |
| 8 | MCU_SWO | D6 / PB3 |
| 9 | Not connected | Reserved by ST |
| 10 | Not connected | JTAG TDI unused in SWD mode |
| 11 | GND | Ground detection |
| 12 | MCU_NRST | J2 / NRST |
| 13 | MCU_UART_RX | D12 / PC8, proposed USART6 RX; probe output |
| 14 | MCU_UART_TX | F8 / PC9, proposed USART6 TX; probe input |

The UART pin function is consistent with the reference schematic's PC8/PC9 debug mapping. Configure the correct alternate function in the board firmware and verify it electrically. The headers use Samtec FTSH-107-01-L-DV (main) and FTSH-105-01-L-DV (Nordic) SMT copper geometry from the manufacturer drawing. Cable keying/mating, pin-1 orientation, package variant and assembly acceptance still require review.

J102 gives the **nRF52832 its own SWD interface**, target-voltage reference and ground. Use a probe/toolchain that supports that Nordic part. STLINK-V3MINIE is the STM32 programming recommendation and is not assumed to program the Nordic controller. No debug wire may connect through the radio into the trusted MCU, secure elements or audio circuit.

## Prototype access and operational security

During bring-up, debug access deliberately permits reading memory and changing firmware. The development computer, probe and diagnostic build are trusted lab equipment. This mode cannot demonstrate protection from a hostile computer attached to its debug port. Use synthetic audio and public test keys.

Develop and verify a separate operational lifecycle configuration that controls authenticated debug/unlock, boot configuration, secure attribution, flash protections, signing anchors and secure-element lifecycle state. Confirm the selected MCU's exact transition and recovery behavior before setting irreversible option bytes. Keep a known recoverable prototype available. Do not burn irreversible security settings or load production secrets as part of an automated generic test.

The temporary bench connection does not authorize a USB connection to the compromised phone in normal VoiceVault use. Normal transport remains BLE ciphertext and bounded public signaling; normal updates remain locally initiated signed microSD images. J501 is a power-only USB-C connector: no application USB data connection is fitted.

## Power and observable acceptance

STLINK-V3MINIE does not power the target. J501 provides protected power-only USB entry; J502 connects a protected battery. A trusted, current-limited battery simulator may replace the pack during bench tests; never parallel it with a fitted cell. USB/Qi use the drawn diode/PMIC power paths. The 100mA startup USB allowance and 500mA fuse remain binding. A conservative peak call cannot rely on USB power alone. R609 is a removable audio-current link; TP1-TP14 expose labeled rails and grounds.

Before enabling peripherals, validate the nPM buck startup (including the initial 2.7V MCU setting), program and read back the intended rails, keep radio/card/NFC interfaces disabled, and hold display/touch/audio/haptic resets appropriately. PB10 enables the separate audio regulator only after codec IOVDD is valid. Verify the internal codec LDO sequence and 1ms reset delay. Charging stays off until the actual battery, attached cell NTC, temperature thresholds and current/voltage settings are qualified. The power allocations and a proposed 3.6V full-operation threshold are in CIRCUIT_REVIEW.md; they are not delivered board firmware.

Bring-up proceeds from inspected assembly and rail resistance to current-limited power, rail measurements, reset/clock validation, chip/revision identification and diagnostic firmware readback. Then test display and local input, each secure element and entropy path, card errors/offline update behavior, and radio isolation.

Begin with dummy headphone loads and a calibrated output limit; do not wear headphones until startup/transient/DC behavior has been checked. For audio, observe actual known samples at capture/playback, the expected DMA interrupts and timestamps, bounded processing/stack use, and forbidden-access denials. Missing samples, missing interrupts, unexpected registers and timeouts fail the relevant test. Follow the existing observable-result contract; a serial message saying PASS is insufficient evidence. Add power/noise, RF/antenna, wireless charging and thermal measurements for the actual assembled configuration.

No board, probe session or hardware timing measurement has been performed by this project yet.
