#!/usr/bin/env python3
"""Native DSN/SES on explicit isolated files; preserves component identity/pose."""
import argparse,json
from pathlib import Path
import pcbnew
p=argparse.ArgumentParser();p.add_argument('mode',choices=['export','import']);p.add_argument('board',type=Path);p.add_argument('exchange',type=Path);p.add_argument('--output',type=Path);p.add_argument('--project',type=Path);a=p.parse_args()
b=pcbnew.LoadBoard(str(a.board))
def sig():return sorted((f.GetReference(),f.GetValue(),f.GetLayer(),f.GetOrientationDegrees(),f.GetPosition().x,f.GetPosition().y,tuple(sorted((p.GetNumber(),p.GetNetname()) for p in f.Pads()))) for f in b.GetFootprints())
before=sig()
if a.mode=='export':
 for layer in [pcbnew.In1_Cu,pcbnew.In4_Cu]:b.SetLayerType(layer,pcbnew.LT_POWER)
 assert a.project and a.project.is_file(), 'Export requires --project with the original netclass rules'
 assert pcbnew.ExportSpecctraDSN(b,str(a.exchange));assert sig()==before
 from apply_specctra_project_rules import apply_rules
 apply_rules(a.exchange,a.project)
else:
 assert a.output;positions={f.GetReference():pcbnew.VECTOR2I(f.GetPosition()) for f in b.GetFootprints()}
 assert pcbnew.ImportSpecctraSES(b,str(a.exchange))
 for x,y in zip(before,sig()):
  assert x[:4]==y[:4] and x[6:]==y[6:]
  assert max(abs(x[4]-y[4]),abs(x[5]-y[5]))<=50
 for f in b.GetFootprints():f.SetPosition(positions[f.GetReference()])
 assert sig()==before;pcbnew.SaveBoard(str(a.output),b)
print(a.mode,'OK:',a.exchange)
