#!/usr/bin/env python3
"""Bounded automatic link completion from native KiCad's actual open objects.

Plans shortest obstacle-avoiding paths, optionally through one ordinary via.
Only a strictly improved candidate with no native hard DRC finding is retained.
No component, rule or existing copper is edited by this tool.
"""
import argparse,json,math,subprocess,shutil,uuid,itertools
from pathlib import Path
from shapely.geometry import Point,LineString,box
from shapely.strtree import STRtree
import plan_local_control_routes as grid
from repair_rev_c_return import drc
ROOT=Path(__file__).resolve().parents[2]
LAYERS=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];SIGNALS=['F.Cu','In2.Cu','In3.Cu','B.Cu']
p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--max-links',type=int,default=35);p.add_argument('--via-attempts',type=int,default=12);a=p.parse_args();a.board=a.board.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);assert '.lab-runs' in a.board.parts
history=[];failed=set();proposals=0

def export(index):
 f=a.out/f'geometry-{index}.json'
 subprocess.run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',str(ROOT/'hardware/tools/export_routing_geometry.py'),'--board',str(a.board),'--output',str(f)],check=True,capture_output=True,timeout=90)
 return json.loads(f.read_text())

def endpoints(obj):
 if obj.get('kind')=='track':return [obj['start'],obj['end'],[(x+y)/2 for x,y in zip(obj['start'],obj['end'])]]
 return [[obj['x'],obj['y']]]

def geometry_shape(q):
 if q.get('kind')=='via':return Point(q['x'],q['y']).buffer(q['w']/2)
 if q.get('kind')=='track':return LineString([q['start'],q['end']]).buffer(q['w']/2)
 return Point(q['x'],q['y']).buffer(q['w']/2) if q['shape']=='circle' else box(*q['box'])

def model(data,net,width):
 obs={l:[] for l in LAYERS};vobs=[]
 for q in data['pads']+data['tracks']:
  shape=geometry_shape(q)
  if q['net']!=net:
   for l in q['layers']:obs[l].append(shape.buffer(max(.100001,q.get('mask_margin_mm',0)+.095)+width/2))
   vobs.append(shape.buffer(.225+.100001))
  # No via in an SMD land, including the same net.
  if 'ref' in q and q['layers'] and max(q['drill'])==0:vobs.append(shape.buffer(.225+.100001))
  if q.get('kind')=='via':vobs.append(Point(q['x'],q['y']).buffer(q['drill']/2+.1+.205))
  if 'ref' in q and max(q['drill'])>0:
   vobs.append(Point(q['x'],q['y']).buffer(max(q['drill'])/2+.1+.205))
   if not q['net']:
    for l in LAYERS:obs[l].append(Point(q['x'],q['y']).buffer(max(q['drill'])/2+.205+width/2))
 ant=next(f for f in data['footprints'] if f['ref']=='AE201');exclusion=box(*ant['box']).buffer(width/2+.001)
 for l in LAYERS:obs[l].append(exclusion)
 vobs.append(exclusion.buffer(.225));return obs,{l:STRtree(v) for l,v in obs.items()},STRtree(vobs)

def path(start,end,layer,obs,trees,width,budget=2):
 if math.dist(start,end)<1e-8:return [start]
 dx,dy=end[0]-start[0],end[1]-start[1];sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
 bends=([[start[0]+sx*abs(dy),end[1]],[end[0]-sx*abs(dy),start[1]]] if abs(dx)>=abs(dy) else [[end[0],start[1]+sy*abs(dx)],[start[0],end[1]-sy*abs(dx)]])
 for bend in bends:
  pts=[start,bend,end]
  if not len(trees[layer].query(LineString(pts),predicate='intersects')):return [q for i,q in enumerate(pts) if i==0 or math.dist(q,pts[i-1])>1e-8]
 grid.STEP=.05;grid.WIDTH=width;grid.CLEARANCE=.100001
 result,_=grid.search(start,end,obs[layer],margin=3,budget_seconds=budget);return result

def plan(A,B,data,net,width):
 obs,trees,via_tree=model(data,net,width)
 pairs=sorted((math.dist(s,t),s,t) for s in endpoints(A) for t in endpoints(B))
 common=set(A['layers'])&set(B['layers'])&set(SIGNALS)
 for _,s,t in pairs:
  for layer in SIGNALS:
   if layer not in common:continue
   pts=path(s,t,layer,obs,trees,width)
   if pts:return [(layer,pts)],[]
 # Try a one-via transition near either actual endpoint, closest paths first.
 for _,s,t in pairs[:2]:
  sites=set()
  for origin in [s,t]:
   # Search a local area, not just eight rays: a legal escape via often sits
   # between two staggered rows of package pads and existing vias.
   for ix in range(-12,13):
    for iy in range(-12,13):sites.add((round(origin[0]+ix*.25,6),round(origin[1]+iy*.25,6)))
   for distance in [.5,.6,.7,.8,.9,1,1.2,1.4,1.6,1.8,2,2.4]:
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:sites.add((round(origin[0]+dx*distance,6),round(origin[1]+dy*distance,6)))
  sites=sorted(sites,key=lambda v:math.dist(s,v)+math.dist(t,v));tested=0
  for v in sites:
   if not(25.73<=v[0]<=94.27 and 25.73<=v[1]<=69.27) or len(via_tree.query(Point(v),predicate='intersects')):continue
   tested+=1
   for la in set(A['layers'])&set(SIGNALS):
    for lb in set(B['layers'])&set(SIGNALS):
     if la==lb:continue
     one=path(s,v,la,obs,trees,width,budget=.8)
     if not one:continue
     two=path(v,t,lb,obs,trees,width,budget=.8)
     if two:return [(la,one),(lb,two)],[v]
   if tested>=a.via_attempts:break
 # A signal may need to leave both crowded outer surfaces. Preserve the two
 # reference planes and use an inner SIGNAL layer between ordinary vias.
 # Keep switching-inductor loops on their existing outer surface.
 if net not in {'REG_L1','REG_L2','BL_SW'}:
  _,s,t=pairs[0]
  def near(point):
   sites=[]
   for ix in range(-12,13):
    for iy in range(-12,13):
     v=(round(point[0]+ix*.25,6),round(point[1]+iy*.25,6))
     if 25.73<=v[0]<=94.27 and 25.73<=v[1]<=69.27 and not len(via_tree.query(Point(v),predicate='intersects')):sites.append(v)
   return sorted(sites,key=lambda v:math.dist(point,v))[:8]
  left=[];right=[]
  for v in near(s):
   for layer in set(A['layers'])&set(SIGNALS):
    pts=path(s,v,layer,obs,trees,width,budget=.8)
    if pts:left.append((v,layer,pts))
  for v in near(t):
   for layer in set(B['layers'])&set(SIGNALS):
    pts=path(v,t,layer,obs,trees,width,budget=.8)
    if pts:right.append((v,layer,pts))
  options=sorted(itertools.product(left,right),key=lambda q:math.dist(q[0][0],q[1][0]))
  for (va,la,pa),(vb,lb,pb) in options[:24]:
   if math.dist(va,vb)<.45:continue
   for middle in ['In2.Cu','In3.Cu']:
    if middle in [la,lb]:continue
    pm=path(va,vb,middle,obs,trees,width,budget=1)
    if pm:return [(la,pa),(middle,pm),(lb,pb)],[va,vb]
 return None,None

report=drc(a.board,a.out/'initial-drc.json',save=True);data=export(0)
for iteration in range(a.max_links):
 objects={q['uuid']:q for q in data['pads']+data['tracks']};choices=[]
 for item in report['unconnected_items']:
  ids=tuple(sorted(q['uuid'] for q in item['items']));key=ids
  if key in failed or len(ids)!=2 or not all(i in objects for i in ids):continue
  A,B=(objects[i] for i in ids);assert A['net']==B['net']
  cost=min(math.dist(s,t) for s in endpoints(A) for t in endpoints(B));choices.append((cost,key,A,B))
 if not choices:break
 _,key,A,B=min(choices,key=lambda q:q[0]);net=A['net'];width=.2 if net in ['VDD_3V3','VSYS','MCU_VDD11','MCU_LX'] else (.3 if net in ['REG_L1','REG_L2','BL_SW'] else .1016)
 print('Planning',net,'native opens',len(report['unconnected_items']),flush=True)
 routes,vias=plan(A,B,data,net,width);entry=dict(net=net,accepted=False)
 if routes:
  step=a.out/f'{iteration:02d}-{net}';step.mkdir();candidate=step/a.board.name
  for suffix in ['.kicad_pro','.kicad_dru']:shutil.copy2(a.board.with_suffix(suffix),candidate.with_suffix(suffix))
  shutil.copy2(a.board.parent/'fp-lib-table',step/'fp-lib-table');(step/'VoiceVault_B0.pretty').symlink_to(a.board.parent/'VoiceVault_B0.pretty',target_is_directory=True)
  extra=[]
  for layer,pts in routes:
   for start,end in zip(pts,pts[1:]):extra.append(f'(segment (start {start[0]:.6f} {start[1]:.6f}) (end {end[0]:.6f} {end[1]:.6f}) (width {width}) (layer "{layer}") (net "{net}") (uuid "{uuid.uuid4()}"))')
  for v in vias:extra.append(f'(via (at {v[0]} {v[1]}) (size .45) (drill .2) (layers "F.Cu" "B.Cu") (net "{net}") (uuid "{uuid.uuid4()}"))')
  text=a.board.read_text();candidate.write_text(text.rstrip()[:-1]+'\n'+'\n'.join(extra)+'\n)\n');result=drc(candidate,step/'drc.json',save=True)
  entry.update(opens=len(result['unconnected_items']),hard_findings=[v['type'] for v in result['violations'] if v['type'] not in ['track_dangling','via_dangling']])
  if not entry['hard_findings'] and entry['opens']<len(report['unconnected_items']):
   shutil.copy2(candidate,a.board);report=result;entry['accepted']=True;data=export(iteration+1)
 if not entry['accepted']:failed.add(key)
 history.append(entry);print(entry,flush=True);(a.out/'report.json').write_text(json.dumps(dict(history=history,remaining_native_opens=len(report['unconnected_items'])),indent=2)+'\n')
print('Remaining native opens:',len(report['unconnected_items']),flush=True)
