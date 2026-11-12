# NUCLEO-U5A5ZJ-Q as a plug-in processor module

The owner suggested this board during the Rev A carrier work. It is a good candidate for a serviceable prototype. Its accessible expansion connectors and onboard ST-LINK simplify measurement and debugging. A carrier can add the trusted display, audio, radio, secure elements, offline card reader and power system. The existing DK2 carrier draft still uses the DK2 pin assignments. A target change requires a separate pin map and firmware configuration. [ST board manual, UM2861](https://www.st.com/resource/en/user_manual/um2861-stm32u5-nucleo144-board-mb1549-stmicroelectronics.pdf)

## MCU and verification scope

The board carries STM32U5A5ZJT6Q. ST specifies a 160 MHz Cortex-M33 with TrustZone, 4 MB flash, and 2514 KB RAM with SRAM3 ECC disabled or 2450 KB with ECC enabled. The existing VoiceVault CPU probe fits within its smaller 768 KB RAM and 960 KB image budgets, which supports evaluating the U5A5. Complete driver, display, interrupt and real-time budgets still need measurement. Use the U5A5 device headers and ES0553. A later U5G9 implementation needs its own peripheral and errata verification. [ST MCU specifications](https://www.st.com/en/microcontrollers-microprocessors/stm32u5a5zj.html) · [U5A5 errata, ES0553 Rev 6](https://www.st.com/resource/en/errata_sheet/es0553-stm32u59xxx-and-stm32u5axxx-device-errata-stmicroelectronics.pdf)

The board manual documents MB1549-U5A5ZJQ-C04 assemblies with silicon C and X. Check the actual board sticker and DBGMCU revision. ES0553 Rev 6 lists X as REV_ID 0x3001 and W as 0x3003. Record the measured revision before selecting a qualified test profile. The generic ordering code alone does not identify the received silicon revision. [ST board history](https://www.st.com/resource/en/user_manual/um2861-stm32u5-nucleo144-board-mb1549-stmicroelectronics.pdf)

## Installed KiCad library inspection

KiCad 10.0.8 includes these generic module footprints locally.

- `Module:ST_Morpho_Connector_144_STLink`
- `Module:ST_Morpho_Connector_144_STLink_MountingHoles`

The inspected mounting-hole version has 148 numbered pads. Pads 1–72 form one 36-row strip, pads 73–144 form the second, and pads 145–148 form two additional two-pin groups. UM2861 Table 19 specifies two 70-pin connectors, CN11 and CN12, each with 35 rows. Reusing the generic footprint requires correcting the connector rows, numbering and board geometry against MB1549. The installed MCU_Module symbol library has several F4/F7/H7 Nucleo variants. It has no exact NUCLEO-U5A5ZJ-Q board symbol.

A dedicated MB1549 module symbol and footprint should map CN11 and CN12 pin numbers explicitly. Check orientation, mating side, mounting holes, connector spacing, component clearance and USB/ST-LINK overhang against the manufacturer drawing and an actual board. UM2861 notes that Morpho headers are unpopulated by default. Include the mating connector hardware in the assembly list. [ST connector tables and mechanical drawing](https://www.st.com/resource/en/user_manual/um2861-stm32u5-nucleo144-board-mb1549-stmicroelectronics.pdf)

## Power and trust boundary

UM2861 specifies external 5 V on CN11.6 with JP6 selecting pins 5–6. The board's regulator provides 3.3 V with a combined board-and-expansion current budget of 500 mA. Verify voltage selection, VDDIO2, solder bridges and consumption before connecting modules. Keep the phone connected only by BLE. Treat the separate radio processor as hostile and keep reset, boot, debug, audio, display and update controls on the trusted side. ST-LINK remains a development interface requiring a production lockdown design. [ST power selection and expansion configuration](https://www.st.com/resource/en/user_manual/um2861-stm32u5-nucleo144-board-mb1549-stmicroelectronics.pdf)

## Recommendation

Use the Nucleo as a removable compute module for initial electrical bring-up and adversarial radio testing, with a separate trusted display. Keep the STM32U5G9J-DK2 as the U5G9-specific comparison target. Qualify audio samples, DMA interrupts, CPU and DMA denials, offline flash updates and timing on the exact board used. KiCad describes circuitry and geometry. An executable peripheral model and silicon measurements supply the behavior evidence.
