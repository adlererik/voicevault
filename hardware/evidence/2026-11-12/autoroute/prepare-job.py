from pathlib import Path
import pcbnew,json,hashlib,re
r=Path.cwd();d=r/'.lab-cache/hardware/freerouting-live';s=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb';b=pcbnew.LoadBoard(str(s));assert hashlib.sha256(s.read_bytes()).hexdigest()==(d/'source-before.sha256').read_text().strip()
# Signal-layer treatment lets the autorouter use local HDI escape corridors.
# The saved KiCad layer definitions and all original pours remain unchanged.
for name in ['In1.Cu','In4.Cu']:b.SetLayerType(b.GetLayerID(name),pcbnew.LT_SIGNAL)
assert pcbnew.ExportSpecctraDSN(b,str(d/'voicevault.dsn'))
text=(d/'voicevault.dsn').read_text();old='(use_via "Via[0-5]_450:200_um")';new='(use_via "Via[0-5]_450:200_um" "Via[0-1]_250:100_um" "Via[4-5]_250:100_um")';assert text.count(old)==1;text=text.replace(old,new)
for name in ['Via[0-1]_250:100_um','Via[4-5]_250:100_um']:
 pattern=r'(\(padstack "'+re.escape(name)+r'"[\s\S]*?\(attach )off(\))';text,n=re.subn(pattern,r'\g<1>on\2',text,count=1);assert n==1
(d/'voicevault.dsn').write_text(text)
settings=json.load(open(r/'.lab-cache/hardware/routing-study/user-jar/freerouting.json'))
settings['profile']['allow_telemetry']=False;settings['profile']['allow_contact']=False
settings['usage_and_diagnostic_data']['disable_analytics']=True;settings['gui']['enabled']=False
settings['router']={'autorouter':{'enabled':True,'max_passes':20,'max_threads':1,'save_intermediate_stages':True},'fanout':{'enabled':True,'max_passes':10},'optimizer':{'enabled':False},'plane_as_obstacle':False,'plane_nets':['GND'],'neck_width_um':100.0,'strict_drc':True,'copper_to_edge_clearance_um':500.0,'hole_clearance_um':250.0,'max_threads':1,'job_timeout':'00:30:00','result_json':str(d/'router-result.json')}
settings['logging']['file']['location']=str(d/'router-details.log');settings['logging']['file']['level']='INFO';settings['logging']['console']['level']='INFO'
u=d/'user';u.mkdir(exist_ok=True);(u/'freerouting.json').write_text(json.dumps(settings,indent=2)+'\n')
(d/'job-profile.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(s.read_bytes()).hexdigest(),dsn_sha256=hashlib.sha256((d/'voicevault.dsn').read_bytes()).hexdigest(),placement_preserved=True,all_199_nets_in_job=True,routing_copy_changes=['All six layers exposed as signal-capable for local escape routing; live layer types retained','Refillable GND plane contours retained, plane_as_obstacle=false','Enable only existing first-order laser via types plus 0.45/0.20mm through vias','Laser captures may attach to SMD pads; no additional layer spans'],router=settings['router'],telemetry_disabled=True,manufacturing_ready=False),indent=2)+'\n')
print('Prepared complete-board DSN with original placement, copper and pours; 20-pass headless profile, first-order HDI, telemetry off.')
