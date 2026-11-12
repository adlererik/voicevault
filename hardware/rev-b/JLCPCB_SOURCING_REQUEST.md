# Draft sourcing enquiry - VoiceVault standalone prototype

**FOR FEASIBILITY AND QUOTATION ONLY. NOT A MANUFACTURING ORDER.**

We are developing a rectangular, approximately 70 x 45 mm SMD prototype using the core ICs in the published Trezor Safe 7 TS7 rev_D schematic, plus a full-duplex headset audio interface and microSD. The board outline and proposed six-layer stack are provisional. We want PCB fabrication and assembly with no development board fitted to the design. We will provide final reviewed Gerber/drill data, exact-part BOM and CPL after engineering is complete.

Target quantity: **four fully assembled prototypes delivered to Sweden**. Please itemize PCB/SMT work and all off-board assemblies separately, including shipping, inspection, fixtures and any unperformed integration. A five-unit price break may be shown separately. This draft has not been sent; the owner has deferred quotations while routing proceeds against provisional public rules. [Cost research](MANUFACTURING_COST.md) keeps the vendor choice open.

Please assess the exact order codes in the accompanying `core-parts.csv`. These are reference selections; their source designators are not a final new-board assembly BOM. We have not authorized substitutions.

Please confirm:

1. Which exact parts can be supplied through public stock, global sourcing or consignment, with the relevant JLC code, lead time, minimum quantities and attrition requirements? Confirm **STM32U5G9ZJJ6Q UFBGA144**, not the similarly named LQFP part. Confirm the nRF52832-CIAA and every WLCSP/USON/QFN package separately.
2. Can the reference OPTIGA SLS32AIA010MKUSON10XTMA2 be sourced despite its NRND status? If a successor is proposed, quote it separately with full identity and provisioning information; do not substitute automatically.
3. What exact TROPIC01 ordering code, silicon revision and lifecycle/provisioning state can be supplied? Factory Trezor attestation material is not expected or requested.
4. The owner authorized sourceable display/touch and battery equivalents. Can you source and fit the selected replacement display/touch assembly and its connector once its drawings/order code are supplied? Please also assess battery connector mates, Qi coil/ferrite and any remaining FPC assemblies. The catalogue candidates are Newhaven NHD-2.4-240320AF-CTXP-CTP, Adafruit 258 protected 1200mAh pack, Würth 760308101219 coil and Pulse W7001 NFC antenna; exact assembly/variant acceptance, actuator and thermistor/harness details remain unresolved. They are not implied to be in your catalogue.
5. Your public consignment policy excludes batteries. What battery-related assembly work, if any, can you actually quote? If this is outside scope, please identify the operations that must be completed separately. Please distinguish populated PCB assembly from display/coil attachment, enclosure assembly and a finished battery-powered device.
6. Which stock stackup, trace/space and drill capabilities do you propose for the MCU's 0.8 mm BGA pitch and the other finer-pitch packages? Confirm any additional constraints or costs. RF routing constraints will follow the final stackup; B0 uses SPI display, not DSI. Please supply exact dielectric/copper construction, thickness, blind/buried via spans, laser drill/land/mask/paste rules, via-in-pad filling/planarization, impedance tolerances and panel/assembly limits. The 0.4mm WLCSP packages and 0.1935mm Nordic lands need explicit review. A 0.075mm drill with your stated 0.075mm annular ring requires at least 0.225mm land and <=0.075mm dielectric for 1:1 aspect ratio. Confirm an approved solution rather than assuming the provisional six-layer/1.0mm outline is compatible.
7. Which inspection records can be supplied for bottom-terminated packages, including X-ray, polarity and component traceability? How are missing parts, substitutions and rework recorded?
8. Can Standard PCBA programming and a customer-defined functional test be quoted? We plan separate STM32 and Nordic programming interfaces, test pads, public diagnostic firmware and current-limited power. Fixtures, programming procedure, firmware hashes and acceptance limits will be supplied for review. No private production keys will be included.

Please keep any procurement or assembly proposal separate from an order commitment. We have not supplied manufacturing-ready files or authorized purchasing parts.


Current native project: 296 electrical components plus 14 probe pads/four mounting holes, 168 routed track segments, 49 vias (14 laser), four GND pours and 520 open connections. The circuit inventory is a requirements/selection record, not an approved BOM. The Hirose DM3AT microSD connector has discontinued variants; confirm exact available stock or review a sourceable replacement. No quote response, stackup acceptance or procurement allocation has been received. The sourcing request is ready to discuss these constraints but is not an order-ready fabrication package.

## Prepare a review bundle

Run `python3 hardware/tools/create_preflight_bundle.py` from the repository root. It checks that the recorded CAD hashes still match, packages tracked B0 sources and evidence, and verifies the archive. The result is `.lab-runs/hardware/exports/VoiceVault-B0-JLCPCB-feasibility-NOT-FOR-ORDER.zip`. Its opening notice states that it is for feasibility/sourcing discussion, contains an incompletely routed design, and gives no authorization to fabricate, assemble or purchase. It intentionally contains no manufacturing export package. Nothing is sent automatically.
