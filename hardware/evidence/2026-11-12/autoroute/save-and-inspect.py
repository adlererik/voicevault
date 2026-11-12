from kipy import KiCad
from pathlib import Path
import json,shutil,hashlib
r=Path.cwd();d=r/'.lab-cache/hardware/freerouting-live';s=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'
c=KiCad(socket_path='ipc://'+str(Path.home()/'.var/app/org.kicad.KiCad/cache/vv-pcb/kicad/api.sock'),timeout_ms=30000);b=c.get_board();assert (Path(b.document.project.path)/b.name).resolve()==s.resolve();b.save()
for ext in ['.kicad_pcb','.kicad_pro','.kicad_dru']:shutil.copy2(s.with_suffix(ext),d/('before'+ext))
poses=[dict(reference=f.reference_field.text.value,x_nm=f.position.x,y_nm=f.position.y,angle_degrees=f.orientation.degrees,layer=int(f.layer)) for f in b.get_footprints()]
(d/'placement-before.json').write_text(json.dumps(poses,indent=2)+'\n');(d/'source-before.sha256').write_text(hashlib.sha256(s.read_bytes()).hexdigest()+'\n')
print('Saved and backed up',len(poses),'placements;',len(b.get_tracks())+len(b.get_vias()),'copper items.');print('Supported methods:',[n for n in dir(b) if any(k in n.lower() for k in ['specctra','dsn','ses','zone','save','export','import'])])
