# LQFP144 candidate audit — 16 November 2026

**Evaluation only.** The selected BGA CAD, local repair and all cloud inputs/returns remain preserved. No design swap, route, cloud run, purchase or manufacturing submission occurred.

The [evaluation and recommendation](../../../rev-c/LQFP_EVALUATION.md) explain the findings. The audit found 55 connected non-supply signals and 91 connected BGA pads including supply/reference pins. All signals can be retained with one proposed correction: the existing PC0 microSD clock does not support SPI2_SCK; unused PB13 does. That correction is documented, not applied.

- [report.json](report.json): observed input hashes, supply-count differences, library checks and limitations.
- [signal-migration.csv](signal-migration.csv): all connected non-supply signals, current and proposed mappings, and the retained failing result for PC0.
- [all-lqfp-pins.csv](all-lqfp-pins.csv): all 144 target pin numbers, function-group BGA references, current nets and proposed nets. A supply group is not a one-to-one physical-ball mapping.
- [Read-only audit tool](../../../tools/evaluate_lqfp_candidate.py): validates official XML hashes, MCU metadata, every KiCad symbol pin, footprint numbering/pitch, current source connections and proposed signal-function availability. It checks CAD hashes before and after. It does not execute firmware or assert a routed/qualified board.

## Reproduce

Use the exact STMicroelectronics pin-data commit `7d1f1514ed5583ec5007ad91236b4e1d377295b1`:

- [BGA XML](https://raw.githubusercontent.com/STMicroelectronics/STM32_open_pin_data/7d1f1514ed5583ec5007ad91236b4e1d377295b1/mcu/STM32U5G9ZJJxQ.xml), SHA256 `0e1f9cc90b2de934061711ce525709518007fb00caa73cf5ea61f0aa1213b6fe`.
- [LQFP XML](https://raw.githubusercontent.com/STMicroelectronics/STM32_open_pin_data/7d1f1514ed5583ec5007ad91236b4e1d377295b1/mcu/STM32U5G9ZJTxQ.xml), SHA256 `b568a8ab9ea2fc7baf33c5848f39e6bb02618ab1f35411e8523f0913eef1a55e`.

Derived pin facts retain [ST's BSD-3-Clause attribution/license](../../../rev-b/reference/ST_PIN_DATA_LICENSE.txt). Cached upstream XML is not required to be committed. From the repository root, on the current Flatpak installation:

```bash
python3 hardware/tools/evaluate_lqfp_candidate.py \
  --bga .lab-cache/hardware/vendor-layouts/STM32U5G9ZJJxQ.xml \
  --lqfp .lab-cache/hardware-research/2026-11-16/lqfp-evaluation/STM32U5G9ZJTxQ.xml \
  --symbols /home/erikclean/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Symbols/x86_64/stable/active/files/symbols/MCU_ST_STM32U5.kicad_sym \
  --footprint /home/erikclean/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints/Package_QFP.pretty/LQFP-144_20x20mm_P0.5mm.kicad_mod \
  --out hardware/evidence/2026-11-16/lqfp-evaluation
```

Adjust cache/library locations on other machines. Source CAD hashes and library hashes are recorded in the report; a different input is a new evaluation. The script deliberately rejects unexplained new pin-function failures and does not silently turn the existing failed PC0 check into a pass. Its successful completion means the evaluation completed with that known failure and a feasible proposed correction.
