#!/usr/bin/env python3
"""Propose explicit inner-segment rework around reserved MCU escape sites."""
import json,sys,collections,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'hardware/tools'));from plan_local_control_routes import obstacles,search,WIDTH
cache=r/'.lab-cache/hardware/routing-b0';data=json.load(open(cache/'obstacles.json'));audit=json.load(open(cache/'mcu-reservation-audit.json'));assert data['source_sha256']==audit['source_sha256']
badnets=sorted({x['blocker'] for x in audit['collisions']});removed=[t for t in data['tracks'] if t['kind']=='track' and t['layers']==['In1.Cu'] and t['net'] in badnets];data['tracks']=[t for t in data['tracks'] if t not in removed];data['reservations']=[dict(net=p['net'],x=p['x'],y=p['y'],w=.25,layers=['In1.Cu'],ref=p['ref'],pin=p['pin']) for p in audit['reserved_pads']]
routes=[];results=[]
for net in badnets:
 tracks=[t for t in removed if t['net']==net];graph=collections.defaultdict(set)
 for t in tracks:
  a,b=tuple(t['start']),tuple(t['end']);graph[a].add(b);graph[b].add(a)
 seen=set();ok=True
 for start in list(graph):
  if start in seen:continue
  component=set();pending=[start]
  while pending:
   a=pending.pop()
   if a in component:continue
   component.add(a);pending+=list(graph[a]-component)
  seen|=component;ends=[p for p in component if len(graph[p])==1];assert len(ends)==2,(net,ends)
  points,why=search(ends[0],ends[1],obstacles(data,net,'In1.Cu'),margin=4,budget_seconds=8)
  if not points:ok=False;results.append(dict(net=net,result=why,endpoints=ends));break
  path=dict(net=net,layer='In1.Cu',width_mm=.1,points=points);routes.append(path)
  for a,b in zip(points,points[1:]):data['tracks'].append(dict(kind='track',net=net,start=a,end=b,w=.1,layers=['In1.Cu']))
 if ok:results.append(dict(net=net,result='proposed'))
 print(results[-1],flush=True)
 (cache/'mcu-escape-rework-plan.json').write_text(json.dumps(dict(source_sha256=data['source_sha256'],removed=removed,reservations=data['reservations'],routes=routes,results=results,manufacturing_ready=False),indent=2)+'\n')
assert all(x['result']=='proposed' for x in results),'Do not build partial rework'
