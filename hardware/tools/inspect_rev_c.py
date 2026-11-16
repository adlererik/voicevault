#!/usr/bin/env python3
"""Read actual Rev C native copper pads, without editing or placing components."""
import json
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.lab-runs/hardware/standalone-c0'
board=pcbnew.LoadBoard(str(ROOT/'hardware/rev-c/voicevault-standalone-c0.kicad_pcb'))
board.BuildConnectivity()
board.GetConnectivity().RecalculateRatsnest()
parts=[]
for fp in board.GetFootprints():
    pads=[]
    for pad in fp.Pads():
        if not pad.GetNumber() or not pad.GetLayerSet().Contains(pcbnew.F_Cu):continue
        pads.append(dict(number=pad.GetNumber(),net=pad.GetNetname(),
            x_mm=pcbnew.ToMM(pad.GetPosition().x),y_mm=pcbnew.ToMM(pad.GetPosition().y),
            size_mm=[pcbnew.ToMM(pad.GetSize().x),pcbnew.ToMM(pad.GetSize().y)]))
    parts.append(dict(ref=fp.GetReference(),value=fp.GetValue(),
        x_mm=pcbnew.ToMM(fp.GetPosition().x),y_mm=pcbnew.ToMM(fp.GetPosition().y),
        placed=fp.IsPlaced(),needs_placed=fp.NeedsPlaced(),locked=fp.IsLocked(),pads=pads))
report=dict(parts=parts,tracks_vias=len(list(board.GetTracks())),
    unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),
    copper_pours=sum(not z.GetIsRuleArea() for z in board.Zones()),
    copper_layers=board.GetCopperLayerCount(),
    # NeedsPlaced is an in-memory autorouter helper flag, not serialized by
    # native KiCad. Qualify saved geometry and locks, not that transient flag.
    electrical_inventory_unplaced=all(not p['placed'] and not p['locked'] and p['x_mm']>100
                                     for p in parts if not p['ref'].startswith('H')))
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'board-pads.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='parts'}))
