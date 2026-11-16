# VoiceVault hardware laboratory

The active new hardware revision is **[VoiceVault C1, STM32U5G9ZJT6Q LQFP144](rev-c1/README.md)**. Its clean [Quilter full-layout run](https://app.quilter.ai/jobs/6afb49addfae511781423d99) started at **19:42 CET on 16 November 2026**. C1 has 199 electrical components, 13 probes and four mounting holes (216 footprints). The corrected MCU package/power mapping and PB13 microSD clock pass native ERC, pin/function and schematic-parity checks. Electrical placement and routing belong to Quilter; no previous copper enters the job. [Native, RF, SPICE and cloud-input evidence](evidence/2026-11-16/c1-preparation/README.md).

The simplified architecture retains a replaceable BL-5C-style lithium-ion pack interface with wired charging, one NXP SE050E2, QFN BLE and local trusted verification, with Qi, NFC and vibration removed. Full power/RF/audio/isolation qualification, actual assembly sourcing and production firmware remain open. The C0/B0 material below is preserved history. No C1 returned layout has been accepted; no fabrication or paid action was made.
The corrected Rev C cloud retry has **finished at 95% routing and is rejected for release**. Native KiCad after refill found 30 open connections and 29 short-circuit findings in candidate 4.1, plus a failed antenna keepout layer transformation. A comparison candidate also fails. [Returned-layout evidence and next action](evidence/2026-11-16/quilter-retry-01-return/README.md) · [Checked clean retry input](rev-c/quilter-retry-01/README.md). The earlier 93% return is preserved. No result was imported into live B0 and no replacement run or order was started by this review.

The preserved live editor still holds the **[standalone Rev B prototype](rev-b/README.md)**: a rectangular 70 × 45 mm SMD board using Safe 7 core ICs, with audio, microSD, independent debug interfaces and sourceable display/battery candidates. It contains **296 electrical components, 14 probe pads and four mounting holes**. The historical complete-board FreeRouting result has **280 open connections, 33 layout errors and 100 warnings**. [Actual run and final DRC](evidence/2026-11-12/autoroute/README.md). **Manufacturing remains blocked.** [Status](rev-b/STATUS.json) · [Actual B0 images and results](evidence/2026-11-12/README.md)

## Open the preserved MCP PCB

The current launcher/MCP deliberately remain pinned to preserved B0; they do not edit the C1 cloud input. Open the [C1 project](rev-c1/voicevault-standalone-c1.kicad_pro) explicitly to inspect it. Run `./hardware/open` from the repository for B0. It opens only the PCB editor required for MCP and reuses an existing copy. This computer previously ran out of memory when several CAD/emulator windows were opened together. Keep the schematic/3D/emulators closed during heavier jobs. The older `--all` launcher targets the historical Rev A demonstration and is not the active B0 workflow.

Installed tools: **KiCad 10.0.8, ngspice 47, Renode 1.17.0, QEMU 9.2.4**, **Freerouting 2.5.0** and **kicad-tools 0.29.0** for bounded routing studies. [Exact tool records](reference/tools.json)

KiCad editor interaction uses MCP through official IPC. Native KiCad generation/exports/ERC/DRC and ngspice runs use direct command-line tools. This keeps inputs, outputs and failures reproducible and inspectable without requiring a separate MCP server for every executable. Renode currently lacks the required STM32U5G peripherals; QEMU runs CPU-only diagnostics. Neither is a qualified full-device emulator.

## Local KiCad MCP

The enabled stdio server `voicevault-kicad`, launched by `hardware/mcp`, uses the official MCP SDK and KiCad Python IPC bindings. It checks the exact active B0 board path and exposes status, footprint positions, named nets, an undoable footprint move and save. It does not expose a schematic-editing API or program a physical MCU.

The environment uses **managed CPython 3.12.14**, independent of system Python updates. Recreate it with:

```sh
python3 hardware/tools/setup_design_env.py
python3 hardware/tools/setup_kicad.py --enable-api
```

This requires `uv` and KiCad with its symbol/footprint/3D library extensions. Register the absolute `hardware/mcp` launcher with `codex mcp add voicevault-kicad -- /absolute/path/to/hardware/mcp`, then run `./hardware/open`. An existing Codex session may need reopening to discover newly registered tools; the MCP stdio connection can also be verified directly. The local IPC socket is under the KiCad Flatpak cache at `vv-pcb/kicad/api.sock`. No network listener is used by MCP.

The latest live check read **314 footprints and 199 named nets** from the open B0 editor. Evidence is stored with the dated B0 results. The earlier 30-footprint Rev A MCP result is historical.

Current 2D rendering uses **software/Cairo** to avoid the recurring OpenGL loader error. GPU/OpenGL startup is not claimed fixed. The setup helper saves library tables and first-run choices. The native generator now attaches rear-side footprints to the board before flipping them; doing that in the opposite order triggered KiCad's bundled Python 3.14 crash. This is separate from the pinned MCP Python environment.

## Available checks

```sh
./hardware/check --design-only --spice
```

Results and raw logs go to `.lab-runs/hardware/standalone-b0/`. The checks compare the actual native schematic and copper-pad net assignments, verify independent ST ball/function data, run ERC/DRC, test the antenna keepout with deliberately forbidden copper on a copy, exercise the copper-import guard on deliberately valid/invalid proposals, execute **799 ngspice passive/static cases** when `--spice` is selected, and compute a clearly labeled power-allocation study.

`--design-only` exits 0 when those available checks pass, **while keeping the manufacturing verdict blocked**. Without it, exit 2 means manufacturing is blocked. Exit 1 means an available check failed. DRC's list is capped, so remaining routing work is counted from KiCad's full ratsnest rather than the first 499 listed items.

Install ngspice 47 on another host, or point `VOICEVAULT_NGSPICE` to its executable. The scripts prefer this computer's verified cached installation when present. [SPICE models and limits](rev-b/SPICE_RESULTS.md) · [Power/circuit review](rev-b/CIRCUIT_REVIEW.md)

The latest whole-board run used the official, unmodified **FreeRouting 2.5.0 JAR on OpenJDK 25.0.4.1**, with bounded memory/CPU use and a 30-minute application deadline. It saved an SES at the deadline. KiCad’s native SES reader decoded it on a copy; a copper-only kipy transaction applied the complete result to the live board. The earlier timed-out studies were not applied. The current global result fails native DRC and is an unfinished checkpoint. Autorouting does not qualify BGA escape geometry, RF matching, return planes, power loops or a manufacturing stackup.

## Target and qualification

[Active B0 target](rev-b/target.json) is **STM32U5G9ZJJ6Q UFBGA144**. [Earlier bench reference](reference/target.json) is the DK2's **STM32U5G9ZJT6Q LQFP144**. Keep those identities distinct. The B0 revision, option bytes, entropy, audio/DMA interrupts, forbidden-access denial, clocks, supply behavior, radio isolation, acoustics, RF, charging and thermals remain unmeasured.

The software's hardware-evidence contract rejects absent models, warning-producing register accesses, missing samples/interrupts/denials and timeouts. A synthetic trace is a test of the checker, not evidence about physical silicon. CPU-only crypto/Opus memory results remain scoped to their recorded configurations.

## Historical Rev A carrier

`hardware/rev-a/` preserves the earlier 150 × 120 mm cabled DK2 carrier, module BOM and wiring plan. It is not the custom B0 device and is also unrouted. Run `./hardware/check --rev-a --design-only` for its 22 older circuit cases and actual Renode missing-peripheral negative control. [2026-11-11 evidence](evidence/2026-11-11/README.md) preserves those results. The [NUCLEO-U5A5 assessment](reference/NUCLEO_U5A5_ASSESSMENT.md) remains a reference comparison, not the active compute module.

## Assembly

[Manufacturing cost research](rev-b/MANUFACTURING_COST.md) compares public capabilities/fees for four assemblies delivered to Sweden. A cheapest delivered supplier is not established. Routing proceeds against provisional published constraints while quotations are deferred.

The [B0 circuit inventory](rev-b/circuit-inventory.csv) is not an approved assembly BOM. Exact part/variant acceptance, HDI stackup, land patterns, routing, power/thermal review, DFM/CPL, fixtures and physical qualification remain open. Batteries and other external assemblies need explicitly agreed handling; a populated PCB is not automatically a complete enclosed device. Nothing has been ordered or submitted for manufacture.
