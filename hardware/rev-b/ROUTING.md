# Routing method and provisional process

The owner-directed workflow now exports the saved placement as Specctra DSN, runs the official FreeRouting CLI headlessly, imports its SES copper into the live editor through kipy, then refills zones and runs native DRC. The local coordinate-proposal methods below are retained as historical/review tools, rather than the default workflow.

This is unfinished engineering CAD. [STATUS.json](STATUS.json) records the latest
checked board state; [evidence](../evidence/2026-11-12/README.md) records accepted
stages. No gerbers or assembly data are released for ordering.

## Cost-directed construction

Retain six copper layers and a provisional 1.0 mm finished thickness. Use ordinary
0.45 mm capture / 0.20 mm drill through vias where they fit. Use first-order
0.25 mm capture / 0.10 mm laser vias only for trapped fine-pitch pads: F–In1 or
In4–B. An adjacent-layer escape can reach an ordinary through via, then In2/In3.
There are no proposed stacked, skip or mechanically buried vias in this method.
Actual routing may still demonstrate that this construction is insufficient.

The factory must specify outer dielectrics compatible with the laser drill,
filled and planarized capture lands, mask/paste treatment and the exact stackup.
Total board thickness does not establish a laser-via aspect ratio. Inner ground
planes remain the preferred references; local escape corridors are not evidence
of uninterrupted return paths or controlled impedance. [Cost study](MANUFACTURING_COST.md)

## Package-specific adaptation

The pinned Nordic nPM1300 reference configuration uses six layers, including
0.30/0.15 mm F–In1 laser vias. Its pad numbering and copper geometry are preserved
in the local factual reference records. VoiceVault uses smaller 0.25/0.10 mm
captures, with **0.0525 mm local mask expansion** on the original 0.21 mm lands.
This produces 0.315 mm nominal openings and nominal webs of 0.104 mm horizontally
and 0.125 mm vertically. At a via-expanded capture the nominal radial mask gap
is 0.0325 mm. The copper pad grid and electrical mapping are unchanged.

This is an explicit engineering adaptation, not Nordic/JLC approval. Source
archive SHA-256: `eea987a3f0722f58547adba1f79adc5f5bcd64f973c2819049c21041a4b88730`.
[Nordic reference archive](https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/reference-layouts/npm1300/wlcsp/npm1300-caaa-reference-layout-1_1.zip).
Do not blindly copy reference traces: the reference configuration and VoiceVault
assign different functions to some configurable pins.

C118 was moved next to U3 and connected on In1 with two first-order laser vias.
R103/R105 moved away from this escape area. MCU ground escapes use fourteen ordinary
dogbones and three F–In1 microvias where rear-side copper blocks ordinary vias. Unreviewed tiny WLCSP captures are
not automatically expanded by the control-route planner.

## Checks before copper reaches the live editor

1. Export actual native pads, holes, layer spans and existing copper with
   `hardware/tools/export_routing_geometry.py` under KiCad's bundled Python.
2. Explicitly choose control nets. The local planners propose paths on disposable
   copies. They do not infer suitable power widths, crystal placement, RF matching,
   impedance or audio layout from net names.
3. Build the proposal with `build_control_route_candidate.py`. The source hash
   must still match. The live board is never a proposal output.
4. Run `qualify_routing_candidate.py`. Original footprints, pad nets, rules, zones
   and existing copper come from the live source. Rebuild connectivity **before**
   refilling zones. Reject new net groups implicated by native clearance, crossing,
   thermal or other layout errors; preserve diagnostic reports from each attempt.
5. Audit laser drill/capture geometry, adjacent-layer spans, hole spacing and
   hole-to-foreign-trace clearance. Reject the complete candidate if this audit
   fails. This supplements KiCad's mechanical-hole checks.
6. Accept through the local `voicevault-kicad` MCP tool. It saves the editor,
   requires exact source/candidate hashes and clean reports, backs up the board,
   reloads the checked copy, and verifies its copper count. Changed files or
   unsaved edits invalidate acceptance. No raw router board is imported directly.

The laser audit uses the provisional [published HDI rules](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq):
0.075–0.15 mm laser drills, capture diameter at least drill + 0.15 mm,
hole-edge spacing 0.13 mm on the same net / 0.24 mm on different nets,
0.15 mm hole-to-foreign-trace clearance and 0.35 mm hole-to-board-edge clearance.
The factory dielectric construction remains unresolved. Native DRC also checks
component holes and copper. Negative controls deliberately violate laser spacing,
antenna restrictions and import hashes on copies; the live design must not change.

## Reproduce a control-routing study

Use the pinned packages in `hardware/tools/routing-requirements.txt`. The outer
planner uses a 0.025 mm grid, continuous geometry checks and 45-degree shortcuts;
searches have explicit time/expansion limits. Equal-cost search paths prefer progress toward the destination to avoid exploring every point in a large open rectangle first. The inner planner tries ordinary
outside-pad vias, then optionally reviewed first-order laser escapes. Both retain
failed/unsupported nets as unfinished work. Only explicitly supplied control nets
are eligible; rails, RF, crystal and analog routes need circuit-specific review.

```bash
flatpak run --user --command=python3 org.kicad.KiCad hardware/tools/export_routing_geometry.py
.lab-cache/hardware/routing-venv/bin/python hardware/tools/plan_local_control_routes.py \
  --nets EXPLICIT_CONTROL_NET --output .lab-cache/hardware/routing-b0/study.json
flatpak run --user --command=python3 org.kicad.KiCad hardware/tools/build_control_route_candidate.py \
  .lab-cache/hardware/routing-b0/study.json .lab-cache/hardware/routing-b0/study.kicad_pcb
flatpak run --user --command=python3 org.kicad.KiCad hardware/tools/qualify_routing_candidate.py \
  .lab-cache/hardware/routing-b0/study.kicad_pcb --output-dir .lab-cache/hardware/routing-b0/study-qualified
.lab-cache/hardware/mcp-venv/bin/python hardware/tools/accept_qualified_copper.py \
  .lab-cache/hardware/routing-b0/study-qualified/qualification.json
./hardware/check --design-only
```

Review the actual paths and rejected groups before accepting a study. A successful
CAD check does not demonstrate signal integrity, charging safety, manufacturability,
real-time audio, isolation or security on physical hardware.

## Main crystal stage

The selected main-crystal layout keeps both HSE nets on F.Cu and moves the two load capacitors onto the crystal side. Their routed branches are approximately 2.61 mm and 2.97 mm; MCU-to-branch paths are approximately 3.67 mm and 5.06 mm. Four local ground microvias accompany the crystal/capacitors. R601 moved to the rear to free space. The three previously blocked MCU ground balls also received adjacent-layer ground microvias.

This explicit placement stage uses `propose_hse_layout.py` and `validate_hse_layout.py`, with four whitelisted footprint moves, an expected world-pad comparison, preservation of all earlier copper, native DRC and the laser audit. Its accepted record is [hse-layout.json](../evidence/2026-11-12/routing/hse-layout.json). Acceptance used a hash-bound native IPC reload; it did not use the copper-only MCP import path, which intentionally preserves footprint positions. The low-frequency crystal area still needs placement review. Startup, actual load capacitance, switcher coupling and EMC remain physical-test requirements.
