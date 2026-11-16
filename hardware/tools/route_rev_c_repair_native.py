#!/usr/bin/env python3
"""Native DSN/SES bridge on the isolated C0 repair only; no GUI/live edits."""
import sys
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.lab-runs/hardware/quilter/2026-11-16-local-repair-02'
board=pcbnew.LoadBoard(str(OUT/('export-input.kicad_pcb' if sys.argv[1]=='export' else 'voicevault-standalone-c0.kicad_pcb')))
def signature():
    return sorted((f.GetReference(),f.GetPosition().x,f.GetPosition().y,f.GetLayer(),f.GetOrientationDegrees(),
                   tuple(sorted((p.GetNumber(),p.GetNetname()) for p in f.Pads()))) for f in board.GetFootprints())
before=signature()
if sys.argv[1]=='export':
    for layer in [pcbnew.In1_Cu,pcbnew.In4_Cu]:board.SetLayerType(layer,pcbnew.LT_POWER)
    assert pcbnew.ExportSpecctraDSN(board,str(OUT/'repair.dsn'))
    assert signature()==before
    print('Exported repair.dsn; fixed placement retained and L2/L5 reserved as planes.')
elif sys.argv[1]=='import':
    positions={f.GetReference():pcbnew.VECTOR2I(f.GetPosition()) for f in board.GetFootprints()}
    assert pcbnew.ImportSpecctraSES(board,str(OUT/'repair.ses'))
    after=signature()
    for a,b in zip(before,after):
        assert a[0]==b[0] and a[3:]==b[3:]
        assert max(abs(a[1]-b[1]),abs(a[2]-b[2]))<=50,'SES moved a component beyond serialization rounding'
    for f in board.GetFootprints():f.SetPosition(positions[f.GetReference()])
    assert signature()==before
    pcbnew.SaveBoard(str(OUT/'routed.kicad_pcb'),board)
    print('Imported SES to isolated routed.kicad_pcb; placements/pad nets preserved.')
else:raise SystemExit('export or import required')
