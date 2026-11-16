# C0 clean retry 01 input

This is a separate checked input for [Quilter job 6afadd5b82651a6067c78f92](https://app.quilter.ai/jobs/6afadd5b82651a6067c78f92), started on 16 November 2026 at 11:53 CET. It is **not a completed or manufacturing-ready PCB**.

The 196 electrical components, 13 probe pads, four mounting holes, all pad nets and all component positions are unchanged from the original clean C0 inventory. Electrical components remain unlocked and outside the outline; Quilter owns all actual placement and routing. The circuit/schematics are unchanged. Additional same-side RF feed geometry and explicit cloud proximity requirements address findings in the first return.

[Full diagnosis, changes and checked evidence](../../evidence/2026-11-16/quilter-retry-01/README.md) · [Preparation record](preparation.json) · [Proximity settings](user_defined_component_proximity.csv) · [Parent circuit design](../README.md)

Reproduce the bounded input checks from the repository root:

```sh
python3 hardware/tools/check_rev_c_retry.py
```

`prepare_rev_c_retry.py` derives this input from the preserved original C0 files, refuses to overwrite placed/routed work and does not use KiCad's Python mutation API. Never copy a returned candidate over this input or the live B0 board. Returned candidates require their own native checks and acceptance review.
