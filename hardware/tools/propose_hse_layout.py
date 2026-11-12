#!/usr/bin/env python3
"""Propose a specific reviewed HSE placement on a copy; native checks required."""
from pathlib import Path
import pcbnew,json,shutil,hashlib,sys,argparse
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'hardware/tools'));from qualify_routing_candidate import geometry,laser_geometry
parser=argparse.ArgumentParser();parser.add_argument('--rotation',type=int,choices=[0,90,180,270],default=270)
parser.add_argument('--output-dir',type=Path,default=r/'.lab-cache/hardware/routing-b0/hse-placement');args=parser.parse_args()
src=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb';d=args.output_dir;d.mkdir(exist_ok=True);b=pcbnew.LoadBoard(str(src));by={f.GetReference():f for f in b.GetFootprints()}
moves={'X301':(50,52.1,180,'F.Cu'),'C301':(51.45,49.45,90,'F.Cu'),'C302':(47.9,51.55,90,'F.Cu'),'R601':(48.94,42.82,0,'B.Cu')}
moves['X301']=(50,52.1,args.rotation,'F.Cu')
expected={'X301':(49.5,52.,'F.Cu'),'C301':(48.94,42.82,'B.Cu'),'C302':(47.36,42.37,'B.Cu'),'R601':(50.67,48.52,'F.Cu')}
for ref,(x,y,side) in expected.items():
 f=by[ref];assert abs(f.GetPosition().x/1e6-x)<1e-5 and abs(f.GetPosition().y/1e6-y)<1e-5 and b.GetLayerName(f.GetLayer())==side,'Unexpected placement; do not repeat this stage'
for ref,(x,y,angle,side) in moves.items():
 f=by[ref]
 if f.GetLayer()!=b.GetLayerID(side):f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(angle);f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
def via(ref,pin,side):
 p=next(p for p in by[ref].Pads() if p.GetNumber()==pin);assert p.GetNetname()=='GND'
 v=pcbnew.PCB_VIA(b);v.SetPosition(p.GetPosition());v.SetWidth(pcbnew.FromMM(.25));v.SetDrill(pcbnew.FromMM(.1));v.SetViaType(pcbnew.VIATYPE_MICROVIA)
 pair=(pcbnew.F_Cu,b.GetLayerID('In1.Cu')) if side=='F.Cu' else (b.GetLayerID('In4.Cu'),pcbnew.B_Cu)
 v.SetLayerPair(*pair);v.SetNetCode(p.GetNetCode());b.Add(v)
for ref,pin,side in [('C301','2','F.Cu'),('C302','2','F.Cu'),('X301','2','F.Cu'),('X301','4','F.Cu'),('U1','F6','F.Cu'),('U1','F10','F.Cu'),('U1','G6','F.Cu')]:via(ref,pin,side)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest();pcbnew.SaveBoard(str(d/src.name),b)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),d/src.with_suffix(ext).name)
(d/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
meta=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((d/src.name).read_bytes()).hexdigest(),moves=moves,unrouted_connections=b.GetConnectivity().GetUnconnectedCount(False),copper_items=len(list(b.GetTracks())),laser_geometry=laser_geometry(b),manufacturing_ready=False)
(d/'proposal.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
