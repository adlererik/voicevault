#!/usr/bin/env python3
"""Bounded pin-aware power placement on an isolated C1 copy.

Does not route copper. Uses conservative native footprint boxes and retains all
values/nets, mounting anchors and unaffected poses. Native DRC is mandatory next.
"""
import argparse,json,math
from pathlib import Path
import pcbnew

p=argparse.ArgumentParser();p.add_argument('--board',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert a.board.resolve()!=a.output.resolve()
b=pcbnew.LoadBoard(str(a.board));fps={f.GetReference():f for f in b.GetFootprints()}
def xy(p):return [p.x/1e6,p.y/1e6]
def pose(f):return dict(xy=xy(f.GetPosition()),angle=f.GetOrientationDegrees(),layer=int(f.GetLayer()))
def pad(ref,pin):return next(p for p in fps[ref].Pads() if p.GetNumber()==pin)
def bbox(f):
 v=f.GetBoundingBox(False,False);return [v.GetX()/1e6,v.GetY()/1e6,v.GetRight()/1e6,v.GetBottom()/1e6]
def intersects(a,c,m=.12):return a[0]<c[2]+m and a[2]>c[0]-m and a[1]<c[3]+m and a[3]>c[1]-m
# Anchor actual high-current/switching pins, not the centroid of an IC.
plans=[
 ('L1201',[('1','U1201','11'),('2','U1201','9')],pcbnew.F_Cu,5.5),
 ('U9',[('C2','L701','2')],pcbnew.F_Cu,4.5),
 ('C108',[('1','U1','65')],pcbnew.F_Cu,5.0),
 ('C107',[('1','L1','2')],pcbnew.F_Cu,4.0),
 ('C704',[('1','U9','B1'),('2','U9','A1')],pcbnew.F_Cu,4.0),
 ('C705',[('1','U9','C1'),('2','U9','C3')],pcbnew.F_Cu,4.5),
 ('R707',[('1','U9','B3'),('2','U9','C3')],pcbnew.F_Cu,4.0),
 ('C1202',[('1','U1201','12'),('2','U1201','10')],pcbnew.F_Cu,6.5),
 ('C1204',[('1','U1201','7'),('2','U1201','10')],pcbnew.F_Cu,6.5),
]
moving={q[0] for q in plans};fixed=[(r,f.GetLayer(),bbox(f)) for r,f in fps.items() if r not in moving]
before={r:pose(f) for r,f in fps.items()}
identity={r:(f.GetValue(),sorted((p.GetNumber(),p.GetNetname()) for p in f.Pads())) for r,f in fps.items()}
report=[]
for ref,links,layer,radius in plans:
 f=fps[ref]
 if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
 assert f.GetLayer()==layer
 targets=[xy(pad(r,n).GetPosition()) for _,r,n in links]
 center=[sum(v[i] for v in targets)/len(targets) for i in [0,1]]
 best=None;tested=0
 for angle in [0,90,180,270]:
  f.SetOrientationDegrees(angle);f.SetPosition(pcbnew.VECTOR2I(0,0))
  offsets=[xy(pad(ref,n).GetPosition()) for n,_,_ in links];box=bbox(f)
  # Center offsets around the pin-matching least-squares translation.
  origin=[sum(t[i]-o[i] for t,o in zip(targets,offsets))/len(targets) for i in [0,1]]
  steps=int(radius/.2)
  for ix in range(-steps,steps+1):
   for iy in range(-steps,steps+1):
    x=round(origin[0]+ix*.2,6);y=round(origin[1]+iy*.2,6)
    bb=[box[0]+x,box[1]+y,box[2]+x,box[3]+y]
    if bb[0]<25.5 or bb[1]<25.5 or bb[2]>94.5 or bb[3]>69.5:continue
    if any(intersects(bb,v) for r,l,v in fixed if l==layer or r.startswith('H') or r=='AE201'):continue
    distances=[math.dist([x+o[0],y+o[1]],t) for t,o in zip(targets,offsets)]
    score=sum(d*d for d in distances)+.0001*math.dist([x,y],before[ref]['xy'])
    tested+=1
    if best is None or score<best[0]:best=(score,x,y,angle,distances)
 if best is None:raise RuntimeError('No legal conservative placement for '+ref)
 _,x,y,angle,distances=best;f.SetOrientationDegrees(angle);f.SetPosition(pcbnew.VECTOR2I(round(x*1e6),round(y*1e6)))
 fixed.append((ref,layer,bbox(f)))
 report.append(dict(ref=ref,before=before[ref],after=pose(f),pin_distances_mm=distances,feasible_candidates=tested))
 print(ref,report[-1],flush=True)
assert identity=={r:(f.GetValue(),sorted((p.GetNumber(),p.GetNetname()) for p in f.Pads())) for r,f in fps.items()}
assert all(pose(f)==before[r] for r,f in fps.items() if r not in moving)
a.output.parent.mkdir(parents=True,exist_ok=True);pcbnew.SaveBoard(str(a.output),b)
a.output.with_suffix('.placement.json').write_text(json.dumps(dict(placements=report,scope='Placement repair only; native DRC/routing required.'),indent=2)+'\n')
