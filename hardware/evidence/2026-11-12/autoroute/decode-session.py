"""Read the router's SES with KiCad and serialize its copper for native IPC import."""
from pathlib import Path
import pcbnew,json,hashlib,collections
r=Path.cwd();d=r/'.lab-cache/hardware/freerouting-live';ses=d/'voicevault.ses';assert ses.is_file() and ses.stat().st_size>0
b=pcbnew.LoadBoard(str(d/'before.kicad_pcb'))
def placement(board):
 return sorted((f.GetReference(),f.GetPosition().x,f.GetPosition().y,f.GetOrientationDegrees()%360,f.GetLayer(),tuple(sorted((p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y) for p in f.Pads()))) for f in board.GetFootprints())
original=placement(b);positions={f.GetReference():pcbnew.VECTOR2I(f.GetPosition()) for f in b.GetFootprints()};zones=len(list(b.Zones()));assert pcbnew.ImportSpecctraSES(b,str(ses))
# The native DSN/SES bridge quantizes placement to 0.1 um. Restore the saved
# positions only after verifying this is translation rounding, never rerouting.
rounded=placement(b);max_rounding_nm=0
for old,new in zip(original,rounded):
 assert old[0]==new[0] and old[3:5]==new[3:5], 'SES changed component identity/rotation/layer'
 dx,dy=new[1]-old[1],new[2]-old[2];max_rounding_nm=max(max_rounding_nm,abs(dx),abs(dy))
 assert abs(dx)<=50 and abs(dy)<=50,'SES moved a component beyond DSN rounding'
 assert len(old[5])==len(new[5]) and all(a[:2]==z[:2] and (z[2]-a[2],z[3]-a[3])==(dx,dy) for a,z in zip(old[5],new[5])),'SES changed pad geometry/nets'
for f in b.GetFootprints():f.SetPosition(positions[f.GetReference()])
assert placement(b)==original,'SES changed footprints or pad nets';assert len(list(b.Zones()))==zones
layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];copper=[];normalized=0
point=lambda p:[p.x,p.y]
for t in b.GetTracks():
 item=dict(net=t.GetNetname(),locked=t.IsLocked())
 if isinstance(t,pcbnew.PCB_VIA):
  top,end=b.GetLayerName(t.TopLayer()),b.GetLayerName(t.BottomLayer());kind='micro' if t.GetViaType()==pcbnew.VIATYPE_MICROVIA else ('through' if t.GetViaType()==pcbnew.VIATYPE_THROUGH else 'blind_buried')
  # Specctra encodes span/diameter, not KiCad's laser-process enum.
  # Restore the exact first-order laser types enabled in the exported job.
  if [top,end] in [['F.Cu','In1.Cu'],['In4.Cu','B.Cu']] and t.GetWidth(t.TopLayer())==250000 and t.GetDrillValue()==100000 and kind!='micro':kind='micro';normalized+=1;t.SetViaType(pcbnew.VIATYPE_MICROVIA)
  item.update(kind='via',position_nm=point(t.GetPosition()),diameter_nm=t.GetWidth(t.TopLayer()),drill_nm=t.GetDrillValue(),top=top,bottom=end,via_type=kind,remove_unused=t.GetRemoveUnconnected())
 elif isinstance(t,pcbnew.PCB_ARC):item.update(kind='arc',start_nm=point(t.GetStart()),mid_nm=point(t.GetMid()),end_nm=point(t.GetEnd()),width_nm=t.GetWidth(),layer=b.GetLayerName(t.GetLayer()))
 else:item.update(kind='track',start_nm=point(t.GetStart()),end_nm=point(t.GetEnd()),width_nm=t.GetWidth(),layer=b.GetLayerName(t.GetLayer()))
 assert item['net'],'Unassigned-net copper in SES';copper.append(item)
b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest();pcbnew.SaveBoard(str(d/'ses-decoded.kicad_pcb'),b)
result=dict(ses_sha256=hashlib.sha256(ses.read_bytes()).hexdigest(),source_sha256=(d/'source-before.sha256').read_text().strip(),footprints_unchanged=True,zones_preserved=zones,copper=copper,laser_type_normalizations=normalized,max_native_placement_rounding_restored_nm=max_rounding_nm,unrouted_before_refill=b.GetConnectivity().GetUnconnectedCount(False),manufacturing_ready=False)
(d/'ses-copper.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='copper'},indent=2));print('Decoded copper:',dict(collections.Counter(t['kind'] for t in copper)))
