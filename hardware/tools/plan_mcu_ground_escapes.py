#!/usr/bin/env python3
"""Plan ordinary MCU ground escapes using conservative native pad/copper geometry.

Output is a proposal only. Exact native DRC and hash-bound acceptance are required.
"""
import json,math
from pathlib import Path
from shapely.geometry import Point,LineString,box
from shapely.strtree import STRtree
r=Path(__file__).resolve().parents[2];j=json.loads((r/'.lab-cache/hardware/routing-b0/obstacles.json').read_text());records=[];shapes=[]
for p in j['pads']:
 g=Point(p['x'],p['y']).buffer(p['w']/2+0.0001,quad_segs=32) if p['shape']=='circle' else box(*p['box'])
 if p['layers']:
  records.append(p);shapes.append(g)
for p in j['tracks']:
 g=Point(p['x'],p['y']).buffer(p['w']/2+.0001,quad_segs=32) if p['kind']=='via' else LineString([p['start'],p['end']]).buffer(p['w']/2+.0001,quad_segs=16)
 records.append(p);shapes.append(g)
tree=STRtree(shapes);result=[];failed=[];vias=[]
for p in [p for p in j['pads'] if p['ref']=='U1' and p['net']=='GND']:
 options=[]
 for dx,dy in [( .4,.4),(-.4,.4),(.4,-.4),(-.4,-.4)]:
  x,y=round(p['x']+dx,6),round(p['y']+dy,6);point=Point(x,y);line=LineString([(p['x'],p['y']),(x,y)]);blocked=[]
  for idx in tree.query(point.buffer(.9)):
   o=records[idx];g=shapes[idx]
   clear=.075 if o['net']=='GND' else .1
   if o.get('kind')=='track' and o['net']=='GND':continue
   if point.distance(g)<max(.225+clear, .35 if o['net']!='GND' and 'ref' in o else 0)+.0002:blocked.append(o.get('ref',o.get('kind'))+':via');break
  if not blocked:
   for idx in tree.query(line.buffer(.6)):
    o=records[idx]
    if o['net']=='GND' or 'F.Cu' not in o['layers']:continue
    if line.distance(shapes[idx])<.075+.1+.0002:blocked.append(o.get('ref',o.get('kind'))+':trace');break
  reuse=next((v for v in vias if math.hypot(v[0]-x,v[1]-y)<1e-6),None)
  if not reuse and any(math.hypot(v[0]-x,v[1]-y)<.33+.0001 for v in vias):blocked.append('new drill spacing')
  if not blocked:options.append((reuse is None,x,y))
 if options:
  _,x,y=min(options);reuse=(x,y) in vias
  if not reuse:vias.append((x,y))
  result.append(dict(pin=p['pin'],start=[p['x'],p['y']],via=[x,y],reuse=reuse))
 else:failed.append(p['pin'])
plan=dict(source_sha256=j['source_sha256'],net='GND',reference='U1',via_diameter_mm=.45,via_drill_mm=.2,track_width_mm=.15,routes=result,blocked_pins=failed,scope='Conservative surface-pad/fixed-copper precheck; native DRC still required')
(r/'.lab-cache/hardware/routing-b0/ground-fanout-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Ground fanout:',len(result),'of',len(result)+len(failed),'MCU ground balls;',len(vias),'new through vias. Blocked:',failed)
