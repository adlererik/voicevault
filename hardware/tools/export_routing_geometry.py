#!/usr/bin/env python3
"""Export actual native copper geometry for copy-only local routing studies."""
import pcbnew,json,hashlib,argparse
from pathlib import Path
r=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path,default=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb')
parser.add_argument('--output',type=Path,default=r/'.lab-cache/hardware/routing-b0/obstacles.json')
parser.add_argument('--with-connectivity',action='store_true',help='Include native connected-copper component UUIDs for alternative attachment sites')
args=parser.parse_args();src=args.board.resolve();assert src.is_file(),src
b=pcbnew.LoadBoard(str(src));assert b is not None,"Native board load failed"
layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];pads=[];tracks=[];footprints=[]
# Display aliases (e.g. Quilter's "Top Layer") are not canonical layer IDs.
layer_ids=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.In3_Cu,pcbnew.In4_Cu,pcbnew.B_Cu]
canonical=dict(zip(layer_ids,layers))
for f in b.GetFootprints():
 box=f.GetBoundingBox(False,False)
 footprints.append(dict(ref=f.GetReference(),value=f.GetValue(),x=f.GetPosition().x/1e6,y=f.GetPosition().y/1e6,angle=f.GetOrientationDegrees(),layer=canonical[f.GetLayer()],box=[v/1e6 for v in [box.GetX(),box.GetY(),box.GetRight(),box.GetBottom()]]))
 for p in f.Pads():
  cu=[n for lid,n in canonical.items() if p.GetLayerSet().Contains(lid)]
  if not cu and p.GetDrillSize().x<=0:continue
  box=p.GetBoundingBox()
  pads.append(dict(uuid=p.m_Uuid.AsString(),ref=f.GetReference(),pin=p.GetNumber(),net=p.GetNetname(),x=p.GetPosition().x/1e6,y=p.GetPosition().y/1e6,w=p.GetSize().x/1e6,h=p.GetSize().y/1e6,shape='circle' if p.GetShape()==pcbnew.PAD_SHAPE_CIRCLE else 'box',box=[v/1e6 for v in [box.GetX(),box.GetY(),box.GetRight(),box.GetBottom()]],layers=cu,mask_margin_mm=(p.GetLocalSolderMaskMargin() or 0)/1e6,drill=[p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6]))
for t in b.GetTracks():
 if isinstance(t,pcbnew.PCB_VIA):tracks.append(dict(uuid=t.m_Uuid.AsString(),kind='via',microvia=t.GetViaType()==pcbnew.VIATYPE_MICROVIA,net=t.GetNetname(),x=t.GetPosition().x/1e6,y=t.GetPosition().y/1e6,w=t.GetWidth(t.TopLayer())/1e6,drill=t.GetDrillValue()/1e6,layers=layers[min(layer_ids.index(t.TopLayer()),layer_ids.index(t.BottomLayer())):max(layer_ids.index(t.TopLayer()),layer_ids.index(t.BottomLayer()))+1]))
 else:tracks.append(dict(uuid=t.m_Uuid.AsString(),kind='track',net=t.GetNetname(),start=[t.GetStart().x/1e6,t.GetStart().y/1e6],end=[t.GetEnd().x/1e6,t.GetEnd().y/1e6],w=t.GetWidth()/1e6,layers=[canonical[t.GetLayer()]]))
output=args.output
output.parent.mkdir(parents=True,exist_ok=True)
payload=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),footprints=footprints,pads=pads,tracks=tracks)
if args.with_connectivity:
 native_pads={p.m_Uuid.AsString():p for f in b.GetFootprints() for p in f.Pads()}
 for q in pads:
  q['outlines']={}
  for layer in q['layers']:
   poly=native_pads[q['uuid']].GetEffectivePolygon(b.GetLayerID(layer),pcbnew.ERROR_OUTSIDE)
   q['outlines'][layer]=[[[poly.COutline(i).CPoint(j).x/1e6,poly.COutline(i).CPoint(j).y/1e6] for j in range(poly.COutline(i).PointCount())] for i in range(poly.OutlineCount())]
 b.BuildConnectivity(); connectivity=b.GetConnectivity(); groups={}; seen=set()
 items=list(b.GetTracks())+[p for f in b.GetFootprints() for p in f.Pads()]
 for item in items:
  uid=item.m_Uuid.AsString()
  if uid in seen:continue
  members={uid}|{q.m_Uuid.AsString() for q in connectivity.GetConnectedItems(item)}
  key=min(members);groups[key]=sorted(members);seen.update(members)
 payload['connected_copper_components']=groups
policy=r/'.lab-runs/hardware/standalone-b0/mcu-escape-reservations.json'
if policy.exists():
 profile=json.loads(policy.read_text())
 if profile.get('result')=='pass' and profile.get('source_sha256')==payload['source_sha256']:
  payload['reservations']=profile['reserved_sites']
output.write_text(json.dumps(payload,indent=2)+'\n')
print('Exported',len(pads),'copper/mechanical pads and',len(tracks),'fixed tracks/vias.')
