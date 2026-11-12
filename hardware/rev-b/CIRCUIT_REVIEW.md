# B0 circuit and power review

This records design intent and remaining work as of 2026-11-12. It is not an independent electrical sign-off. Use the native schematic and `STATUS.json` together with the source records under `reference/`.

## Power topology and startup

USB and Qi feed the protected nPM1300 input through separate Schottky paths. The battery connects to its charger/system path. `VSYS` is a raw system rail, not a regulated 5 V output. BUCK1 supplies nominal `VDD_3V3`; its reference startup resistor initially selects 2.7 V. Firmware must keep peripheral resets/interfaces inactive and program/read back the intended rail configuration before using them. BUCK2 supplies `AUX_3V3`. Both bucks have a 200 mA rating. LS1 supplies the radio through its 100 mA load-switch path; LS2 is unused.

The **backlight boost input uses VSYS**, not either 200 mA buck or the 100 mA load switch. Its input range must remain within the TPS61062 specification. The MCU controls EN/PWM, which defaults low. Four 200 Ω branch resistors improve sharing; a 12 Ω feedback resistor sets nominal total current to about 41.7 mA. The 6.2 V nominal clamp provides an alternate feedback path for open LED branches. The static SPICE envelope is documented separately; startup, pulse energy, converter stability, brightness and heat remain unverified.

The **codec analog/headphone input has its own TLV75533PDRVR regulator** from VSYS. It is not on the MCU buck. PB10 enables it through a default-off control. IOVDD and LDO_SELECT use the MCU rail; LDOIN must appear after or with valid IOVDD, following TI SLAA492A. Keep audio reset and clocks low, verify power and internal DLDO behavior, release reset, then wait at least 1 ms before register writes/ALDO configuration. AVDD/DVDD are internal-LDO outputs, not 3.3 V inputs. The DVDD-to-AVDD Schottky follows TI's pop-suppression arrangement. R609 permits isolated current measurement.

MicroSD and NFC have separate TLV75533PDRVR regulators with default-off enable controls and I/O isolation. The WSON exposed pads need grounded heat-spreading copper and a reviewed thermal/via layout. A 500 mA electrical rating does not establish continuous safe dissipation at that current. These three regulators use TI's DRV0006A pin map and copper/paste example; final assembly review remains required.

The initial protected 500 mAh battery candidate has insufficient margin for the conservative peak-call allocation. The prototype candidate is now **Adafruit 258 / PKCELL LP-503562, 1200 mAh**, nominal 34 × 62 × 5 mm, with a published 1C continuous-discharge rating. The exact delivered pack, polarity, revision, physical fit and attached external temperature sensor must be checked. Initial charging remains a proposed maximum 250 mA after NTC/configuration review. Neither battery charging nor runtime has been demonstrated. [Pack source and hash](reference/battery-selection.json)

## Explicit allocation study

`python3 hardware/tools/power_budget.py` computes an engineering envelope. These allocations are not measured currents or proven worst-case limits:

| Domain | Allocated current | Basis / limitation |
|---|---:|---|
| MCU buck | 175 mA of 200 mA | 120 mA MCU allowance, LCD 12 mA, touch 23 mA, codec I/O 10 mA, bridges/misc 10 mA. MCU and I/O allowances require measurement. |
| AUX buck | 70 mA of 200 mA | 25 mA radio, 40 mA secure elements, 5 mA other allowance; unmeasured. |
| Audio regulator | 200 mA | TI requests 150 mA analog source capability with all blocks enabled and identifies up to approximately 20 mA digital demand. Allocation includes margin; actual configuration needs measurement. |
| microSD regulator | 250 mA | Selected-card peak allocation, not a universal card specification. |
| NFC regulator | 150 mA | Initial RF/current/thermal allocation; matching and register configuration must enforce measured limits. |
| Haptic | 150 mA burst | Actuator selection and drive calibration remain open. |

The study assumes 80% buck efficiency, 75% backlight efficiency, the worst modeled backlight output power, and 10 mA system overhead. At 3.6 V it gives approximately **623 mA for the conservative call allocation**, below an engineering allocation of 960 mA for the candidate 1200 mAh pack. All features at their allocations exceed that engineering limit and must not run concurrently. Offline update and NFC enrollment exclude active audio. These restrictions are requirements for board firmware, not delivered MCU drivers.

Full operation below **3.6 V VSYS** remains blocked pending dropout/rail-margin measurements. The pack's 3.0 V protection cutoff is not the operational shutdown threshold. A 100 mA USB source cannot independently sustain a full call. The existing 500 mA resettable USB fuse and source/CC limits remain binding; the modeled peak requires battery supplementation. Do not increase USB current merely because a cable is attached. Charging must yield to system load.

For an illustrative 5.2 V regulator input and 50 °C ambient, TI's 100.2 °C/W DRV JEDEC reference gives approximately 88 °C audio, 98 °C microSD and 79 °C NFC junction estimates at the allocations. These are arithmetic estimates on a reference thermal model. The actual board, enclosure, copper and simultaneous heat sources can differ substantially.

## Interfaces and security boundary

SAI1 uses PE2 MCLK, PE3 capture data, PE4 frame sync, PE5 bit clock and PE6 playback data. I2C2 PF0/PF1 controls the codec. The CTIA jack connects tip/ring to left/right playback, ring 2 to ground, and sleeve to the microphone. The physical switch disconnects the microphone and grounds the codec-side path in mute. Headphone coupling capacitors require polarity, startup, transient, DC and dummy-load tests before wearing headphones.

The radio UART/control bridges have hardware-fixed directions, default-disabled enables and power-off isolation. Main-MCU and Nordic debug connectors are separate. Qi has a separate MCU control bus, and NFC/card I/O is locally enabled. A compromised radio must never be given access to debug, audio, provisioning or shared trusted buses. The net checks establish circuit correspondence, not resistance to malicious electrical faults or DMA exploits on silicon.

The microSD controller is an untrusted data source. Update authentication, rollback rejection, power-failure recovery, physical entry and protection of earlier boot stages require a board-specific port and tests. The immutable/write-protected first-stage design is not established merely by fitting the STM32.

## Layout and sourcing still required

Placement keeps the secure elements clear of the main MCU's rear-side escape field and reserves the antenna corner on every copper layer. The antenna rule permits only the intended feed track and forbids vias/fills there. It is tested with deliberately forbidden copper on a separate board copy. The matching values are starting points from reference designs, not measurements of this rectangle and enclosure.

The nPM1300 and nRF52832 copper geometries come from Nordic reference layouts. TROPIC01 comes from the vendor board source. OPTIGA, codec, debug headers, audio jack and added WSON regulator geometry have source checks. STWLC38/ST25R3916B/TPS61062 land/assembly reviews remain open, as do mask/paste process constraints across all bottom-terminated parts.

JLCPCB publishes HDI blind-via drills of 0.075–0.15 mm and requires at least 0.075 mm annular ring; dielectric/drill aspect ratio must not exceed 1:1. Its published artwork baseline is 3/3 mil. This supports investigating HDI; it does **not** approve this stackup or pad construction. A 0.1935 mm Nordic copper land cannot simply accept a 0.225 mm minimum via land without reviewing its copper/mask/paste construction. Do not enlarge vendor pads or relax checks silently. [HDI capabilities](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq)

The selected Hirose DM3AT card-connector family has discontinued variants; procurement/lifecycle acceptance is open. A Molex 1040310811 alternative has an installed KiCad footprint but has not been substituted or independently qualified. Generic capacitor values do not establish DC-bias capacitance, ESR or stability. RF parts, surge parts, antenna, coil, actuator, harnesses and temperature-sensor assemblies all need exact acceptance before release.
