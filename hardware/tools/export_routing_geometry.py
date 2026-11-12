#!/usr/bin/env python3
"""Export actual native copper geometry for copy-only local routing studies."""
import pcbnew,json,hashlib,argparse
from pathlib import Path
r=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path,default=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb')
args=parser.parse_args();src=args.board.resolve();assert src.is_file(),src
b=pcbnew.LoadBoard(str(src));assert b is not None,"Native board load failed"
layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];pads=[];tracks=[]
for f in b.GetFootprints():
 for p in f.Pads():
  cu=[n for n in layers if p.GetLayerSet().Contains(b.GetLayerID(n))]
  if not cu and p.GetDrillSize().x<=0:continue
  box=p.GetBoundingBox()
  pads.append(dict(ref=f.GetReference(),pin=p.GetNumber(),net=p.GetNetname(),x=p.GetPosition().x/1e6,y=p.GetPosition().y/1e6,w=p.GetSize().x/1e6,h=p.GetSize().y/1e6,shape='circle' if p.GetShape()==pcbnew.PAD_SHAPE_CIRCLE else 'box',box=[v/1e6 for v in [box.GetX(),box.GetY(),box.GetRight(),box.GetBottom()]],layers=cu,mask_margin_mm=(p.GetLocalSolderMaskMargin() or 0)/1e6,drill=[p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6]))
for t in b.GetTracks():
 if isinstance(t,pcbnew.PCB_VIA):tracks.append(dict(kind='via',microvia=t.GetViaType()==pcbnew.VIATYPE_MICROVIA,net=t.GetNetname(),x=t.GetPosition().x/1e6,y=t.GetPosition().y/1e6,w=t.GetWidth(t.TopLayer())/1e6,drill=t.GetDrillValue()/1e6,layers=layers[min(layers.index(b.GetLayerName(t.TopLayer())),layers.index(b.GetLayerName(t.BottomLayer()))):max(layers.index(b.GetLayerName(t.TopLayer())),layers.index(b.GetLayerName(t.BottomLayer())))+1]))
 else:tracks.append(dict(kind='track',net=t.GetNetname(),start=[t.GetStart().x/1e6,t.GetStart().y/1e6],end=[t.GetEnd().x/1e6,t.GetEnd().y/1e6],w=t.GetWidth()/1e6,layers=[b.GetLayerName(t.GetLayer())]))
(r/'.lab-cache/hardware/routing-b0/obstacles.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),pads=pads,tracks=tracks),indent=2)+'\n')
print('Exported',len(pads),'copper/mechanical pads and',len(tracks),'fixed tracks/vias.')
