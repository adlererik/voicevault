# C1 native circuit and migration evidence

**Checked unplaced input, not a routed or fabrication-ready PCB.** See the [C1 design](../../../rev-c1/README.md).

The separate [C1 full-layout job](https://app.quilter.ai/jobs/6afb49addfae511781423d99) was observed **started at 19:42 CET on 16 November 2026**. It continues on Quilter's servers with the local computer off. [Launch record](launch.json) · [Recorded screenshot](quilter-started.png). No returned candidate has been accepted.

- [report.json](report.json): native ERC/DRC/parity, exact pin/functions, seven negative controls, native CAD/rule hashes and the full native ratsnest count.
- [erc.json](erc.json) and [drc.json](drc.json): actual KiCad reports. The DRC unconnected-item list is capped; the full native count is **587**, not the 499 listed items.
- [mcu-pin-net.csv](mcu-pin-net.csv): all 144 LQFP pins and their actual circuit nets.
- [circuit-delta.json](circuit-delta.json): existing non-MCU functional nets and mounting anchors unchanged; only U1's existing value changes and three capacitors are added.
- [preserved-input-hashes.json](preserved-input-hashes.json): B0, original C0, retry input and isolated BGA repair hashes verified unchanged.
- [rf-controls.json](rf-controls.json): five isolated native allowed/forbidden-route fixtures; no real C1 placement/routing was performed locally.
- [spice-core-summary.json](spice-core-summary.json), [simulator version](spice-core-version.txt): 27 ideal-source passive sensitivity cases. The regulator loop, actual MCU and physical parasitics are absent. The output range is not a hardware qualification pass band.
- [Support clarification screenshot](support-clarification.png): Quilter's human agent Justin requested clarification; the two existing C0 reproduction questions were restated in the already authorized support conversation. No diagnosis or fix has been received. This does not block the separately approved LQFP experiment.
- [Server input verification](server-input-verification.json): all 18 downloaded cloud CAD files byte-match the checked C1 source.
- [Cloud settings verification](cloud-settings-verification.json): all 76 bypass entries, 14 current budgets, three converter loops, one RF-feed definition and 21 proximity relationships match. Four crystal definitions and primary GND independently match expected values. Downloads are archived under [cloud-settings](cloud-settings/).
- [Parser warning review](parser-warning-review.json): only the four connector mechanical `MP` identifiers differ from schematic pin inventories; no functional pin identifiers are missing. H1–H4 are mechanical-only.

## Repeat checks

From the repository root:

```bash
./hardware/check --rev-c1
python3 hardware/tools/check_rev_c1_rf.py
python3 -m unittest discover -s hardware/tests -p test_spice_results.py
python3 hardware/tools/spice_core_sensitivity.py \
  --source hardware/rev-c1/spice/core-output-sensitivity.cir \
  --out .lab-runs/hardware/standalone-c1/spice-core
```

The checks use pinned official [ST package data](https://raw.githubusercontent.com/STMicroelectronics/STM32_open_pin_data/7d1f1514ed5583ec5007ad91236b4e1d377295b1/mcu/STM32U5G9ZJTxQ.xml) from the earlier evaluation cache. [Source hashes and prior evaluation](../lqfp-evaluation/README.md). KiCad CLI uses a small isolated configuration; the native Python path only reads/inspects a copy and does not replace existing rule areas. No Python crash occurred in these checks.

Generation uses `prepare_rev_c1.py prepare`, `create_standalone_draft.py --mcu-package lqfp --unplaced` inside KiCad's runtime, then `prepare_rev_c1.py finalize`. Native netlist export precedes `sync_rev_c1_nc.py` to serialize explicit single-pad NC names. Existing-design guards intentionally reject regeneration. Do not bypass them to overwrite future placed/routed C1 work. Raw intermediate files and native/SPICE logs are retained under `.lab-runs/hardware/standalone-c1`; all prior revision sources remain intact.
