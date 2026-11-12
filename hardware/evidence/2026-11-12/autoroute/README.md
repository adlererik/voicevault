# Complete-board FreeRouting run — 2026-11-12

**Unfinished routing checkpoint. Native KiCad DRC failed. Not for fabrication.**

Used **[FreeRouting 2.5.0](https://github.com/freerouting/freerouting/releases/tag/v2.5.0)**, the official unmodified JAR, headlessly on **OpenJDK 25.0.4.1**. The JAR SHA-256 is `f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7`. It is cached locally rather than committed to Git.

The job ran from **19:49:32 to 20:20:00 Europe/Stockholm**. It reached its application-level 30-minute budget, completed its current pass, and saved an SES. Its process exited successfully; the routing job state is **TIMED_OUT**, not fully routed. The wrapper took 1,847.57 seconds. A process exit of zero does not establish routing success.

## Actual final result

| Native KiCad measurement | Before | After SES import and copper refill |
|---|---:|---:|
| Component footprints | 314 | 314; exact placement unchanged |
| Open connections, full native ratsnest | 495 | **280** |
| Track segments | 345 | 1,863 |
| Vias | 103 | 274 |
| Laser vias | 31 | 53 |
| Ground pours | 4 | 4 |
| Antenna rule areas | 1 | 1 |
| Layout errors | 0 | **33** |
| Layout warnings | 0 | **100** |

The 133 layout findings are **two antenna-area rule violations, twelve undersized-track errors, nineteen starved-thermal errors, 95 dangling-via warnings and five dangling-track warnings**. The 280 unconnected findings are additional. The native DRC command exited **5**, indicating findings. No native clearance/short violations were listed, but the other errors and unconnected items still prevent release. See [unaltered native DRC](final-drc.json) and [full native status](final-status.json).

The router reported 259 unfinished connections before KiCad import/refill; that is a different observation. The authoritative saved-board count is **280 after native copper refill**. The router also logged 449 pre-existing clearance warnings in its own model. Those differ from KiCad’s clean input clearance check; they were retained in the logs, not waived or substituted for native DRC. No existing KiCad rules were relaxed.

## What was done

1. Saved the live editor through official kipy IPC and backed up its PCB/project/rules. Input PCB SHA-256: `40b4ab8ab8936caeb09e776a75e81ecd19168797a168c04d9e7f8948dfe78d69`. The input is preserved in commit `53378f2`.
2. Exported all components, all 199 named copper nets and existing copper as [Specctra DSN](voicevault.dsn). In the export copy only, In1/In4 were signal-capable. Ground contours were retained, with `plane_as_obstacle=false`. Enabled only the existing 0.45/0.20 mm through via and 0.25/0.10 mm F–In1 / In4–B laser spans.
3. Ran the official JAR headlessly. Fanout: ten passes; autorouter: up to twenty passes, one thread; optimizer off; application timeout 30 minutes. Telemetry, analytics and the router’s servers were disabled. [Exact profile](job-profile.json), [actual tool settings/results](router-result.json), [command](command.json), [terminal log](terminal.log), [process outcome](run-result.json).
4. Decoded the complete [SES](voicevault.ses) with KiCad’s native SES reader on a copy. Its placement rounding was at most 21 nanometres; exact original placements were restored on that copy after verifying rotations, layers and pad/net correspondence. Restored the laser-via type for the enabled adjacent-layer capture/drill combinations. [Decode record](ses-decoding.json).
5. Applied the entire copper result through a **single undoable kipy native IPC transaction** in the live PCB editor. Retained 324 identical original items, removed 124 changed items and created 1,813 router-result items. No footprint or zone was replaced. Payloads were sent in API-sized groups; these were serialization groups, not manually routed coordinate batches. [Actual import record](ipc-import-result.json).
6. Refilled the original copper zones through kipy, saved, ran native `kicad-cli pcb drc`, then inspected the full native ratsnest independently. Final PCB SHA-256: `7e82425a6895dc75763a0df97c2fb472d34389b821d46791485e6d5a137d53c1`.

KiCad 10’s IPC API has no direct DSN-export/SES-import handler. Using its native SES reader on a copy and applying only copper through kipy bridges that gap without replacing the live board file wholesale.

The Java maximum heap was 640 MiB and CPU quota 150%. The initial process limit of 1,000 MiB memory / 128 MiB swap was raised during the run to 1,200 / 256 MiB to allow JVM overhead while bounding workstation use. [Recorded adjustment](resource-limit-update.json). The log’s 421.59 GB “total allocated” is cumulative allocation across garbage collections, not simultaneous resident memory; its reported peak Java heap was 606 MB.

## Evidence and reproduction

The saved `*-*.py` scripts in this directory are the exact bridge/run scripts used, with their original local cache paths. They are evidence snapshots, not a general installer: `prepare-job.py` also uses the workstation’s previously initialized router settings file. The source-before copy, JAR and managed kipy environment remain in `.lab-cache/hardware/freerouting-live/` and `.lab-cache/hardware/mcp-venv/`. Do not rerun the save/export stage over this run’s cache; it would overwrite the input checkpoint. Reconstruct a fresh job directory for another run.

To recheck the current board from the repository root:

```sh
flatpak run --user --command=kicad-cli org.kicad.KiCad pcb drc \
  --format json --exit-code-violations \
  --output /tmp/voicevault-current-drc.json \
  hardware/rev-b/voicevault-standalone-b0.kicad_pcb
```

Expected result at this checkpoint: DRC exit 5 with the findings above. [Artifact hashes](artifact-hashes.json) bind the retained DSN, SES, results and bridge scripts. The pre-autoroute full-check report elsewhere in this evidence directory belongs to the input hash, not the final PCB.

## Remaining work

Correct how the export represents the antenna restrictions and minimum widths, investigate thermal connections and dangling fanout, and finish the 280 open connections using reviewed constraints. The automatic 100 µm neckdowns on power nets do not establish adequate current capacity. Power widths/loops, return paths, clocks, audio, RF, stackup and filled laser-via assembly need engineering review. Then rerun native DRC and the supplemental design gates. No manual trace routing or filtering into selected successful nets followed this run.

This run does not demonstrate a functioning board, a manufacturable assembly, safe charging, signal integrity, radio isolation or physical security. No parts, services or fabrication were purchased; no supplier submission was made. The eleven-group Rust laboratory and the 799 circuit-model cases were not rerun for this copper-only change.
