# Sourceable display and battery candidates

The owner authorized catalogue equivalents on 2026-11-11. These are initial candidates, **not released BOM selections**. Availability shown on a vendor web page is not confirmed allocation for a JLCPCB order.

| Function | Candidate | Published size / interface | Engineering consequence |
|---|---|---|---|
| Display and trusted touch | Newhaven NHD-2.4-240320AF-CTXP-CTP | 2.4 inch 240 x 320 IPS, ST7789VI, 3-wire SPI or parallel, FT5426 I2C touch, 42.8 x 59.91 x 4.13 mm | Catalogue module with public pinout. Different resolution/controller/interface from the Safe 7. Requires a VoiceVault driver, pin allocation and new connectors. |
| Protected battery | Adafruit 258 / PKCELL LP-503562, 3.7 V 1200 mAh | Published 34 x 62 x 5 mm, protected pack, two-pin JST-PH lead | No temperature-sense wire. Requires a properly attached external temperature sensor and a reviewed charging/power path. The previous 500mAh candidate lacks conservative peak-call current headroom. Delivered pack limits and measured load still need validation. |

The display's published 42.8 x 59.91 mm outline can fit within a provisional 45 x 70 mm board envelope in plan view. This is **only a bounding-box comparison**: connector bends, cable exits, glass tolerances, jack/card access, board mounting, battery, coil and enclosure interference have not been checked. Battery and display thickness already exceed the PCB thickness; no Safe 7 thickness claim is made.

The display specification gives a typical backlight point of 3.1V / 80mA, a minimum 40mA operating point and four cathodes. The native B0 adaptation uses TPS61062 from VSYS, nominal 41.7mA total, four 200-ohm sharing resistors and a nominal 6.2V alternate feedback clamp. It has been exercised in 704 static model cases; converter startup, brightness, current sharing with the actual LEDs, faults and thermals still require validation. The LCD supply range starts at 2.4V and the touch controller's at 2.7V; keep resets inactive until the configured rails are valid.
The display uses a 40-pin 0.5 mm FFC plus a separate six-pin 1.0 mm touch FFC. Its specification recommends Molex 54132-4062 and 52271-0679 or equivalents. The current candidates are Hirose FH12-40S-0.5SH(55) and Molex 2005280060 equivalents. Contact side, actuator orientation, flex thickness, land pattern and cable geometry must match the purchased module. It does not use the reference Safe 7 display connector.

Adafruit specifies a charge rate of 500 mA or less for the battery. Set a conservative initial charging requirement no higher than 250 mA until the actual pack datasheet, NTC placement, thermal behavior and nPM1300 configuration have been reviewed. That 250 mA value is a proposed bench limit, not a validated charger setting. Verify polarity on the delivered pack and the chosen board connector; the connector name alone does not establish polarity. Wireless-charge heating must be evaluated with the cell and coil in their final positions.

JLCPCB's current public consignment terms exclude batteries. Keep the battery purchase/attachment and its temperature-sensor assembly as a separately confirmed assembly operation. No assertion is made that JLCPCB will ship a finished battery-powered enclosure.

Primary sources checked on 2026-11-11/12:

- [Newhaven product and mechanical/interface details](https://newhavendisplay.com/2-4-inch-ips-tft-with-capacitive-touchscreen/)
- [Newhaven candidate specification](https://newhavendisplay.com/content/specs/NHD-2.4-240320AF-CTXP-CTP.pdf)
- [Adafruit protected 1200mAh pack](https://www.adafruit.com/product/258) and [manufacturer pack specification](https://cdn-shop.adafruit.com/product-files/258/C101-_Li-Polymer_503562_1200mAh_3.7V_with_PCM_APPROVED_8.18.pdf)
- [JLCPCB consignment terms](https://jlcpcb.com/help/article/consignment-part-terms-conditions)
