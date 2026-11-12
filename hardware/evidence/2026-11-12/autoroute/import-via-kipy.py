"""Apply only the SES copper through kipy; keep every component and zone in place."""
from pathlib import Path
import json,hashlib,collections
from kipy import KiCad
from kipy.board_types import Track,ArcTrack,Via,ViaType,BoardLayer,DrillShape,UnconnectedLayerRemoval,PadStackShape
from kipy.geometry import Vector2
r=Path.cwd();d=r/'.lab-cache/hardware/freerouting-live';source=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb';job=json.load(open(d/'ses-copper.json'));assert job['footprints_unchanged']
client=KiCad(socket_path='ipc://'+str(Path.home()/'.var/app/org.kicad.KiCad/cache/vv-pcb/kicad/api.sock'),timeout_ms=60000);b=client.get_board();assert (Path(b.document.project.path)/b.name).resolve()==source.resolve()
def poses(board):return [dict(reference=f.reference_field.text.value,x_nm=f.position.x,y_nm=f.position.y,angle_degrees=f.orientation.degrees,layer=int(f.layer)) for f in board.get_footprints()]
expected=json.load(open(d/'placement-before.json'));order=lambda rows:sorted(rows,key=lambda f:f['reference'])
assert order(poses(b))==order(expected),'Placement changed while router ran'
b.save();assert hashlib.sha256(source.read_bytes()).hexdigest()==job['source_sha256'],'Saved source changed while router ran'
nets={n.name:n for n in b.get_nets()};layers={name:getattr(BoardLayer,'BL_'+name.replace('.','_')) for name in ['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']};inverse={v:k for k,v in layers.items()}
def key_native(t):
 if t['kind']=='via':return ('via',t['net'],*t['position_nm'],t['diameter_nm'],t['drill_nm'],t['top'],t['bottom'],t['via_type'])
 key=(t['kind'],t['net'],t['layer'],t['width_nm'],*sorted([tuple(t['start_nm']),tuple(t['end_nm'])]))
 return key+(tuple(t['mid_nm']),) if t['kind']=='arc' else key
def key_live(t):
 if isinstance(t,Via):
  kind={ViaType.VT_THROUGH:'through',ViaType.VT_MICRO:'micro'}.get(t.type,'blind_buried')
  return ('via',t.net.name,t.position.x,t.position.y,t.diameter,t.drill_diameter,inverse[t.padstack.drill.start_layer],inverse[t.padstack.drill.end_layer],kind)
 ends=sorted([(t.start.x,t.start.y),(t.end.x,t.end.y)])
 if isinstance(t,ArcTrack):return ('arc',t.net.name,inverse[t.layer],t.width,*ends,(t.mid.x,t.mid.y))
 return ('track',t.net.name,inverse[t.layer],t.width,*ends)
# Canonical comparison keeps existing objects and settings whenever the SES
# contains the same copper, and replaces only the router's actual differences.
existing=list(b.get_tracks())+list(b.get_vias());by_key=collections.defaultdict(list)
for t in existing:by_key[key_live(t)].append(t)
created=[];retained=0
for t in job['copper']:
 key=key_native(t)
 if by_key[key]:by_key[key].pop();retained+=1;continue
 if t['kind']=='via':
  x=Via();x.position=Vector2.from_xy(*t['position_nm']);x.diameter=t['diameter_nm'];x.drill_diameter=t['drill_nm'];x.type={'through':ViaType.VT_THROUGH,'micro':ViaType.VT_MICRO,'blind_buried':ViaType.VT_BLIND_BURIED}[t['via_type']]
  x.padstack.copper_layers[0].shape=PadStackShape.PSS_CIRCLE
  x.padstack.drill.start_layer=layers[t['top']];x.padstack.drill.end_layer=layers[t['bottom']];x.padstack.drill.shape=DrillShape.DS_CIRCLE
  names=list(layers);a,z=names.index(t['top']),names.index(t['bottom']);x.padstack.layers=[layers[n] for n in names[min(a,z):max(a,z)+1]]
  x.padstack.unconnected_layer_removal=UnconnectedLayerRemoval.ULR_REMOVE if t['remove_unused'] else UnconnectedLayerRemoval.ULR_KEEP
 else:
  x=ArcTrack() if t['kind']=='arc' else Track();x.start=Vector2.from_xy(*t['start_nm']);x.end=Vector2.from_xy(*t['end_nm']);x.width=t['width_nm'];x.layer=layers[t['layer']]
  if t['kind']=='arc':x.mid=Vector2.from_xy(*t['mid_nm'])
 x.net=nets[t['net']];x.locked=t['locked'];created.append(x)
removed=[t for group in by_key.values() for t in group];print('SES changes: retain',retained,'remove',len(removed),'create',len(created),flush=True)
commit=b.begin_commit()
try:
 for i in range(0,len(removed),200):b.remove_items(removed[i:i+200])
 for i in range(0,len(created),150):
  added=b.create_items(created[i:i+150]);assert collections.Counter(key_live(t) for t in added)==collections.Counter(key_live(t) for t in created[i:i+150]);print('Imported',min(i+150,len(created)),'of',len(created),flush=True)
 assert order(poses(b))==order(expected)
 # KiCad defers visibility of newly created objects until push_commit.
 b.push_commit(commit,'Import FreeRouting complete-board SES')
except BaseException:
 b.drop_commit(commit);raise
assert len(b.get_tracks())+len(b.get_vias())==len(job['copper'])
b.save();print('Refilling live copper zones...',flush=True);b.refill_zones(block=True,max_poll_seconds=180);b.save()
assert order(poses(b))==order(expected)
actual=collections.Counter(key_live(t) for t in list(b.get_tracks())+list(b.get_vias()));target=collections.Counter(key_native(t) for t in job['copper']);assert actual==target,'Live copper differs from decoded SES'
result=dict(imported_via='kipy native IPC transaction',ses_sha256=job['ses_sha256'],footprints_unchanged=True,retained_items=retained,removed_items=len(removed),created_items=len(created),final_copper_items=sum(actual.values()),zones_refilled=True,source_after_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),manufacturing_ready=False)
(d/'ipc-import-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
