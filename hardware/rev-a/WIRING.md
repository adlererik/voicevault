# Rev A harness wiring and electrical review

The KiCad project uses numbered carrier ports. External modules connect by function through short labeled cables. Their module pin numbers differ from carrier port numbers. The layout is a placement draft. Connectors have standard 2.54 mm pitch and do not mechanically reproduce each module.

## DK2 interfaces

The assignments come from UM3223 Tables 11 and 12 and DS14102 alternate-function tables. Configure SAI2 block A as master transmit and block B as internally synchronized receive. Confirm the exact frame format and synchronizer behavior on silicon before audio qualification. [ST board manual](https://www.st.com/resource/en/user_manual/um3223-discovery-kit-with-stm32u5g9zj-mcu-stmicroelectronics.pdf) · [ST device datasheet](https://www.st.com/resource/en/datasheet/stm32u5g9zj.pdf)

| Function | MCU pins | DK2 connection |
|---|---|---|
| Codec bit clock, master clock, DAC data | PB13, PB14, PB15 at AF13 | CN6.5, CN6.8, CN4.1 |
| Codec frame clock and ADC data | PC0, PC12 at AF13 | CN1.14, CN1.20 |
| Codec and OPTIGA control | PG13 SDA, PG14 SCL at I2C1 | CN4.9, CN4.10 |
| Radio receive and transmit at MCU | PA3 RX, PA2 TX at USART2 | CN6.1, CN6.2 |
| Radio credit output and pending input | PG0, PG1 GPIO | CN7.3, CN7.4 |
| TROPIC SPI1 SCK, MISO, MOSI | PA5, PA6, PB5 at AF5 | CN4.6, CN4.5, CN4.4 |
| TROPIC CS and interrupt | PB6 GPIO, PB1 GPIO | CN4.2, CN1.8 |
| microSD CLK, DO, DI, CS | PC1, PC2, PA7, PB0 GPIO | CN7.5, CN7.1, CN7.6, CN4.3 |
| Physical mic switch sense | PB7 GPIO | CN1.10 |
| Local update button | PB8 GPIO | CN1.12 |

microSD uses a dedicated software-SPI interface for offline updates. It shares no SPI wires with TROPIC. A bounded card driver and signed-image streaming reader still need implementation. An SDMMC qualification would require its own pin assignment and tests.

## Module harnesses

- J6 connects to the WM8960 breakout's 3.3 V logic input, ground, VIN analog supply, SDA, SCL, MCLK, BCLK, DACLRC, ADCLRC, DACDAT and ADCDAT by label. Both LRC inputs use AUDIO_FS. Use codec slave mode. Disable automatic level control and unwanted mixing paths. The trusted device owns sampling and the codec.
- J7 pin 1 supplies 5V_SYS to the Feather's USB/VBUS power pin through a power-only harness. Its onboard regulator supplies the radio locally. The carrier has no connection to the Feather's 3.3 V regulator output. Connect MCU_TX_TO_RADIO to Feather RX and RADIO_TX_TO_MCU to Feather TX. Credit and pending use dedicated radio GPIOs selected in the future radio firmware. The protocol adapter must bound lengths, reassembly, work per interrupt and queue occupancy. Electrical damage resistance and power isolation remain unverified.
- J8 connects to the Secure Tropic Click by labeled 3.3 V, ground, CS, SCK, MOSI, MISO and interrupt/GPO. J9 connects to OPTIGA Trust M by 3.3 V, ground, SDA and SCL. Verify module pull-ups and address configuration. Persistent key operation mappings, authenticated bus use and entropy health checks remain implementation work.
- J10 connects to the 3 V microSD breakout by 3V3, GND, CS, CLK, DI and DO. Add card electrical protection and a hardware power-disable path in the reviewed design.
- J11 takes raw HP_L, HP_R, ground, MICBIAS and LINPUT2 from the WM8960 module. Carrier C4/C5 block the headphone output DC before J12. Connect the CTIA jack tip to HP_L, ring 1 to HP_R, ring 2 to ground and sleeve to HEADSET_MIC. Check physical jack continuity because adapter silkscreen can label sleeve as ground. Confirm the actual headset wiring before use.
- SW1 is a mechanical DPDT switch. Pole 1 common pin 2 joins the biased CODEC_MIC node. One throw joins HEADSET_MIC and the other grounds the codec input. Pole 2 provides the local switch sense. Check throw continuity on the actual component and label the enclosure accordingly. Calls additionally require the trusted local-consent state machine.

[Codec source schematic](https://github.com/sparkfun/SparkFun_Audio_Codec_Breakout_WM8960/tree/main/Hardware) · [Feather pinout](https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/pinouts) · [TROPIC Click schematic](https://download.mikroe.com/documents/add-on-boards/click/secure-tropic-click/secure-tropic-click-schematic.pdf) · [OPTIGA evaluation board](https://www.infineon.com/evaluation-board/S2GO-SECURITY-OPTIGA-M) · [CTIA adapter contacts](https://www.adafruit.com/product/2915)

## Power arrangement

The Qi receiver feeds the BQ24074 board at its VBUS and ground pads. The protected 3.7 V lithium-ion pack connects directly to the charger's battery connector. Charger OUT feeds the 5 V regulator. Regulator output feeds carrier 5V_SYS. The DK2 supplies the carrier 3V3 rail. Use the DK2's documented external 5 V power selection before applying power on CN5.5. Keep other power sources disconnected during power tests. Verify polarity at every harness before energizing.

Set the charger for 500 mA input limit and 500 mA charging. Its default configuration differs. Attach a 10 kΩ NTC to the battery and configure THERM as specified by the charger guide. The 500 mA Qi budget is shared by charging and load. The battery may discharge while the device operates on the pad. Bench targets are total 5 V load at or below 500 mA and additional DK2 3.3 V load at or below 100 mA, pending actual current and thermal measurements. No runtime or charging-time result has been established. The proposed battery vendor recommends sustained draw under 1.3 A.

[Charger configuration](https://learn.adafruit.com/adafruit-bq24074-universal-usb-dc-solar-charger-breakout/pinouts) · [Qi receiver limits](https://www.adafruit.com/product/1901) · [Regulator characteristics](https://www.pololu.com/product/4082) · [Battery characteristics](https://www.adafruit.com/product/353)

## Before routing or assembly release

Verify every selected component's datasheet, footprint, polarity, tolerances and lifecycle. Add headphone discharge/pop control, output level limits, jack/card ESD, rail switching, backfeed prevention, reverse-current protection and production boot/debug policy as the electrical review requires. Check all DK2 solder-bridge and power selections. Match the passive circuit simulations to the final routed schematic and selected codec. Measure RF, inductive charging, noise, rails and temperature with the modules operating together. These items remain open in the manufacturing gate.
