# VoiceVault hardware laboratory

The active design is the **[standalone Rev B prototype](rev-b/README.md)**: a rectangular 70 × 45 mm SMD board using Safe 7 core ICs, with audio, microSD, independent debug interfaces and sourceable display/battery candidates. It contains **296 electrical components, 14 probe pads and four mounting holes**. The placed draft has no routed tracks. **Manufacturing remains blocked.** [Status](rev-b/STATUS.json) · [Actual B0 images and results](evidence/2026-11-12/README.md)

## Open the active PCB

Run `./hardware/open` from the repository. It opens only the PCB editor required for MCP and reuses an existing copy. This computer previously ran out of memory when several CAD/emulator windows were opened together. Keep the schematic/3D/emulators closed during heavier jobs. The older `--all` launcher targets the historical Rev A demonstration and is not the active B0 workflow.

Installed tools: **KiCad 10.0.8, ngspice 47, Renode 1.17.0, QEMU 9.2.4**, and **Freerouting 2.5.0** for bounded routing studies. [Exact tool records](reference/tools.json)

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

Results and raw logs go to `.lab-runs/hardware/standalone-b0/`. The checks compare the actual native schematic and copper-pad net assignments, verify independent ST ball/function data, run ERC/DRC, test the antenna keepout with deliberately forbidden copper on a copy, execute **799 ngspice passive/static cases**, and compute a clearly labeled power-allocation study.

`--design-only` exits 0 when those available checks pass, **while keeping the manufacturing verdict blocked**. Without it, exit 2 means manufacturing is blocked. Exit 1 means an available check failed. DRC's list is capped, so remaining routing work is counted from KiCad's full ratsnest rather than the first 499 listed items.

Install ngspice 47 on another host, or point `VOICEVAULT_NGSPICE` to its executable. The scripts prefer this computer's verified cached installation when present. [SPICE models and limits](rev-b/SPICE_RESULTS.md) · [Power/circuit review](rev-b/CIRCUIT_REVIEW.md)

A Freerouting trial runs on a copy with memory/CPU/time limits. Its JAR is used because the native 2.5.0 CLI encountered an upstream serialization error on this board. The trial did not produce an accepted route and was not applied. Autorouting cannot approve BGA escape geometry, RF matching, return planes, power loops or a manufacturing stackup.

## Target and qualification

[Active B0 target](rev-b/target.json) is **STM32U5G9ZJJ6Q UFBGA144**. [Earlier bench reference](reference/target.json) is the DK2's **STM32U5G9ZJT6Q LQFP144**. Keep those identities distinct. The B0 revision, option bytes, entropy, audio/DMA interrupts, forbidden-access denial, clocks, supply behavior, radio isolation, acoustics, RF, charging and thermals remain unmeasured.

The software's hardware-evidence contract rejects absent models, warning-producing register accesses, missing samples/interrupts/denials and timeouts. A synthetic trace is a test of the checker, not evidence about physical silicon. CPU-only crypto/Opus memory results remain scoped to their recorded configurations.

## Historical Rev A carrier

`hardware/rev-a/` preserves the earlier 150 × 120 mm cabled DK2 carrier, module BOM and wiring plan. It is not the custom B0 device and is also unrouted. Run `./hardware/check --rev-a --design-only` for its 22 older circuit cases and actual Renode missing-peripheral negative control. [2026-11-11 evidence](evidence/2026-11-11/README.md) preserves those results. The [NUCLEO-U5A5 assessment](reference/NUCLEO_U5A5_ASSESSMENT.md) remains a reference comparison, not the active compute module.

## Assembly

The [B0 circuit inventory](rev-b/circuit-inventory.csv) is not an approved assembly BOM. Exact part/variant acceptance, HDI stackup, land patterns, routing, power/thermal review, DFM/CPL, fixtures and physical qualification remain open. Batteries and other external assemblies need explicitly agreed handling; a populated PCB is not automatically a complete enclosed device. Nothing has been ordered or submitted for manufacture.
