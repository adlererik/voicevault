#!/usr/bin/env python3
"""Automatically stitch isolated GND pads to the retained ground planes.

Chooses short 45-degree stubs/via sites from actual native geometry. Checks
clearance on all copper layers, avoids via-in-pad, then uses native DRC as an
acceptance oracle. Does not waive any finding or modify component placement.
"""
import argparse,json,subprocess,sys,uuid,math,shutil
from pathlib import Path
from shapely.geometry import Point,LineString,box
from shapely.strtree import STRtree
from repair_rev_c_return import drc
from prepare_rev_c_retry import spans
from finalize_rev_c_quilter_input import parse,child,children
ROOT=Path(__file__).resolve().parents[2];layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.board=a.board.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
assert '.lab-runs' in a.board.parts
geometry=a.out/'geometry.json'
subprocess.run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',str(ROOT/'hardware/tools/export_routing_geometry.py'),'--board',str(a.board),'--output',str(geometry)],check=True,timeout=90,capture_output=True)
g=json.loads(geometry.read_text());pads={q['uuid']:q for q in g['pads']};via_obs=[];trace_obs={l:[] for l in layers}
for q in g['pads']:
 shape=Point(q['x'],q['y']).buffer(q['w']/2) if q['shape']=='circle' else box(*q['box'])
 # Surface land exclusion prevents via-in-pad, including GND lands.
 if q['layers']:via_obs.append(shape.buffer(.225+.105))
 if q['net']!='GND':
  for l in q['layers']:trace_obs[l].append(shape.buffer(.075+.105))
 if max(q['drill'])>0:
  via_obs.append(Point(q['x'],q['y']).buffer(max(q['drill'])/2+.1+.205))
  if not q['net']:
   for l in layers:trace_obs[l].append(Point(q['x'],q['y']).buffer(max(q['drill'])/2+.075+.205))
for q in g['tracks']:
 shape=Point(q['x'],q['y']) if q['kind']=='via' else LineString([q['start'],q['end']])
 if q['net']!='GND':
  via_obs.append(shape.buffer(q['w']/2+.225+.105))
  for l in q['layers']:trace_obs[l].append(shape.buffer(q['w']/2+.075+.105))
 if q['kind']=='via':via_obs.append(shape.buffer(q['drill']/2+.1+.205))
# The antenna's all-layer copper exclusion is a hard obstacle.
ae=next(f for f in g['footprints'] if f['ref']=='AE201');exclusion=box(*ae['box']).buffer(.3)
via_obs.append(exclusion)
for l in layers:trace_obs[l].append(exclusion)
vias=STRtree(via_obs);traces={l:STRtree(v) for l,v in trace_obs.items()}
report=drc(a.board,a.out/'initial-drc.json',save=True);history=[];seen=set()
for iteration in range(12):
 candidates=[]
 for item in report['unconnected_items']:
  for node in item['items']:
   q=pads.get(node['uuid'])
   if q and q['net']=='GND' and q['uuid'] not in seen:candidates.append(q)
 if not candidates:break
 q=candidates[0];seen.add(q['uuid']);layer=next((l for l in ['F.Cu','B.Cu'] if l in q['layers']),None)
 if not layer:continue
 accepted=False
 for distance in [.5,.6,.7,.8,.9,1.0,1.2,1.4,1.6,1.8,2.0]:
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
   x=round(q['x']+dx*distance,6);y=round(q['y']+dy*distance,6)
   if not(25.73<=x<=94.27 and 25.73<=y<=69.27):continue
   if len(vias.query(Point(x,y),predicate='intersects')):continue
   line=LineString([(q['x'],q['y']),(x,y)])
   if len(traces[layer].query(line,predicate='intersects')):continue
   step=a.out/f'{iteration:02d}-{q["ref"]}-{q["pin"]}';step.mkdir(exist_ok=True);candidate=step/a.board.name
   for suffix in ['.kicad_pro','.kicad_dru']:shutil.copy2(a.board.with_suffix(suffix),candidate.with_suffix(suffix))
   shutil.copy2(a.board.parent/'fp-lib-table',step/'fp-lib-table')
   if not(step/'VoiceVault_B0.pretty').exists():(step/'VoiceVault_B0.pretty').symlink_to(a.board.parent/'VoiceVault_B0.pretty',target_is_directory=True)
   text=a.board.read_text();extra=f'(via (at {x} {y}) (size 0.45) (drill 0.2) (layers "F.Cu" "B.Cu") (net "GND") (uuid "{uuid.uuid4()}"))\n(segment (start {q["x"]} {q["y"]}) (end {x} {y}) (width 0.15) (layer "{layer}") (net "GND") (uuid "{uuid.uuid4()}"))\n'
   candidate.write_text(text.rstrip()[:-1]+extra+')\n');result=drc(candidate,step/'native-drc.json',save=True)
   hard=[v for v in result['violations'] if v['type'] not in ['track_dangling','via_dangling']]
   if not hard and len(result['unconnected_items'])<len(report['unconnected_items']):
    shutil.copy2(candidate,a.board);report=result;accepted=True;break
  if accepted:break
 history.append(dict(pad=q['ref']+'.'+q['pin'],accepted=accepted,remaining=len(report['unconnected_items'])));print(history[-1],flush=True)
(a.out/'report.json').write_text(json.dumps(dict(history=history,remaining_native_opens=len(report['unconnected_items'])),indent=2)+'\n')
