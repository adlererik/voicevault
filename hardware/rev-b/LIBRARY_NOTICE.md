# Source and library notices

The unmodified Trezor source PDFs and notices in `reference/` are from trezor/trezor-hardware at the commit recorded in `reference/source-manifest.json`. Preserve the upstream `LICENSE`, `COPYING`, attribution and source links when distributing these materials. The new project is an independent VoiceVault adaptation and is not an official Trezor product.

The MCU symbol and stock footprint starting points in `VoiceVault_B0.kicad_sym` and `VoiceVault_B0.pretty/` are copied from the installed official KiCad 10 library extensions. KiCad library assets are distributed under CC BY-SA 4.0 with the KiCad libraries exception. Attribution: KiCad Library Team and contributors, https://www.kicad.org/libraries/license/. The connector symbol and prototype generator were created for VoiceVault. The MCU symbol retains the stock generic temperature-code naming, with the exact selected MPN supplied on its schematic instance.

The local MCU symbol has been corrected to add VDD11 balls J9 and D4 from ST DS14102 Rev 5, which were missing in the installed stock symbol. The standard Device C/L/R symbols and capacitor/resistor/inductor footprints also come from the official KiCad libraries under the same attribution. The 0402 and 0805 footprints are provisional until exact MPNs and component requirements are matched.

The Samtec SMT header copper geometry now follows manufacturer drawing H. Mating/keying and assembly acceptance remain open. The UFBGA footprint agrees with the ST 10 x 10 mm, 0.8 mm pitch package; this does not validate the rest of the board circuit or layout.

The exact STM32U5G9ZJJxQ ball/function data is derived from STMicroelectronics/STM32_open_pin_data at commit 7d1f1514ed5583ec5007ad91236b4e1d377295b1; retain reference/ST_PIN_DATA_LICENSE.txt (BSD-3-Clause) and source hashes. TROPIC01 footprint geometry comes from the pinned vendor development-board project; retain reference/TROPIC_VENDOR_LICENSE.txt. Nordic nPM1300 and nRF52832 reference-layout URLs/hashes and extracted factual pad mappings are recorded separately in reference/.

The headset jack, WSON regulator and debug-header footprints transcribe manufacturer copper/mechanical examples. The STWLC38, ST25R3916B and TPS61062 review footprints remain explicitly provisional for assembly/DFM. Manufacturer application information does not constitute endorsement or qualification of VoiceVault. Original manufacturer PDFs downloaded for review remain in the local cache unless redistribution is separately permitted.

The new B0 hardware adaptation is licensed under CERN-OHL-S-2.0 in LICENSE. Upstream reference/UPSTREAM_LICENSE and reference/UPSTREAM_COPYING retain the original hardware/software notices; the project-wide Rust software license is not replaced by this hardware notice.
