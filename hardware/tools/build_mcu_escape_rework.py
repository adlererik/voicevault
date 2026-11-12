#!/usr/bin/env python3
"""Build and check the hash-bound MCU escape rework on a disposable copy."""
import pcbnew,json,hashlib,shutil,sys,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'hardware/tools'));from qualify_routing_candidate import geometry,signature,laser_geometry
from check_mcu_escape_reservations import audit
s=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb';j=json.load(open(r/'.lab-cache/hardware/routing-b0/mcu-escape-rework-plan.json'));assert hashlib.sha256(s.read_bytes()).hexdigest()==j['source_sha256'];assert all(x['result']=='proposed' for x in j['results'])
b=pcbnew.LoadBoard(str(s));netcodes={p.GetNetname():p.GetNetCode() for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()};fixed={geometry(b,t) for t in b.GetTracks()};pads=signature(b);removed=[];removed_objects=[];new_items=[]
key=lambda t:(t.GetNetname(),b.GetLayerName(t.GetLayer()),t.GetWidth()/1e6,tuple(sorted([(t.GetStart().x/1e6,t.GetStart().y/1e6),(t.GetEnd().x/1e6,t.GetEnd().y/1e6)])))
wanted={(t['net'],'In1.Cu',t['w'],tuple(sorted([tuple(t['start']),tuple(t['end'])]))) for t in j['removed']}
for t in list(b.GetTracks()):
 if not isinstance(t,pcbnew.PCB_VIA) and key(t) in wanted:removed.append(geometry(b,t));removed_objects.append(t);b.Remove(t)
assert len(removed)==len(wanted)
b.BuildConnectivity()
for path in j['routes']:
 for a,z in zip(path['points'],path['points'][1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(pcbnew.VECTOR2I(*[pcbnew.FromMM(x) for x in a]));t.SetEnd(pcbnew.VECTOR2I(*[pcbnew.FromMM(x) for x in z]));t.SetWidth(pcbnew.FromMM(.1));t.SetLayer(b.GetLayerID('In1.Cu'));t.SetNetCode(netcodes[path['net']]);b.Add(t);new_items.append(t)
assert pads==signature(b);assert fixed-set(removed)<={geometry(b,t) for t in b.GetTracks()}
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest();assert b.GetConnectivity().GetUnconnectedCount(False)<=495
out=r/'.lab-cache/hardware/routing-b0/mcu-escape-rework';out.mkdir(exist_ok=True)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(s.with_suffix(ext),out/s.with_suffix(ext).name)
(out/'fp-lib-table').write_text((s.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(s.parent)))
pcbnew.SaveBoard(str(out/s.name),b)
subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(out/'drc.json'),str(out/s.name)],check=True,capture_output=True,timeout=90)
drc=json.load(open(out/'drc.json'));assert not drc['violations'],drc['violations'];laser=laser_geometry(b);assert not laser['violations'];reserve=audit(b,drc);assert not reserve['collisions'],reserve
meta=dict(source_sha256=j['source_sha256'],candidate_sha256=hashlib.sha256((out/s.name).read_bytes()).hexdigest(),reworked_nets=sorted({t['net'] for t in j['removed']}),removed_inner_segments=len(removed),new_inner_segments=sum(len(p['points'])-1 for p in j['routes']),unchanged_other_pads_and_copper_verified=True,total_copper_items=len(list(b.GetTracks())),unrouted_connections=b.GetConnectivity().GetUnconnectedCount(False),native_layout_violations=0,laser_geometry_violations=0,escape_reservations=reserve,manufacturing_ready=False)
(out/'review.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
