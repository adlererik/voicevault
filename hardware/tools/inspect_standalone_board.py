#!/usr/bin/env python3
"""Export actual KiCad pad/net data; run with KiCad's bundled Python."""
import json
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[2]
board = pcbnew.LoadBoard(str(ROOT / 'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'))
board.BuildConnectivity()
board.GetConnectivity().RecalculateRatsnest()
parts = []
for footprint in board.GetFootprints():
    pads = []
    for pad in footprint.Pads():
        pads.append(dict(number=pad.GetNumber(), net=pad.GetNetname(),
                         x_mm=pad.GetPosition().x / 1e6, y_mm=pad.GetPosition().y / 1e6,
                         width_mm=pad.GetSize().x / 1e6, height_mm=pad.GetSize().y / 1e6))
    parts.append(dict(reference=footprint.GetReference(), value=footprint.GetValue(),
                      x_mm=footprint.GetPosition().x/1e6, y_mm=footprint.GetPosition().y/1e6,
                      layer=board.GetLayerName(footprint.GetLayer()), pads=pads))
out = ROOT / '.lab-runs/hardware/standalone-b0/board-pads.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(parts=parts,
    unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),
    tracks_and_vias=len(list(board.GetTracks())), zones=len(list(board.Zones()))), indent=2) + '\n')
print(f'Inspected {len(parts)} actual native footprints and their copper pads.')
