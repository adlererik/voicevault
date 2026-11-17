#!/usr/bin/env python3
"""Restore sub-micron junctions lost in DSN's 0.1um coordinate grid.

Only same-net, same-layer endpoints within 0.00025mm of a pre-export copper
endpoint are snapped. No broad movement or rule relaxation; native DRC follows.
"""
import argparse,json,math,re
from collections import defaultdict
from pathlib import Path
from prepare_rev_c_retry import spans
from finalize_rev_c_quilter_input import parse,child
p=argparse.ArgumentParser();p.add_argument('original',type=Path);p.add_argument('imported',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
assert a.imported.resolve()!=a.output.resolve()
all_layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];index=defaultdict(list)
def points(node):
 return [(k,tuple(map(float,child(node,k)[1:3]))) for k in ['start','end','at'] if child(node,k)]
def layers(node):
 z=child(node,'layer')
 if z:return z[1:]
 return all_layers
original=a.original.read_text()
for kind in ['segment','via','arc']:
 for start,end in spans(original,kind):
  z=parse(original[start:end]);net=child(z,'net')[1]
  for _,(x,y) in points(z):
   for layer in layers(z):index[(net,layer,round(x*1000),round(y*1000))].append((x,y))
s=a.imported.read_text();edits=[];snapped=[]
for kind in ['segment','via','arc']:
 for start,end in spans(s,kind):
  frag=s[start:end];z=parse(frag);net=child(z,'net')[1]
  for k,(x,y) in points(z):
   candidates=[]
   for layer in layers(z):
    for ix in range(-1,2):
     for iy in range(-1,2):candidates.extend(index.get((net,layer,round(x*1000)+ix,round(y*1000)+iy),[]))
   if not candidates:continue
   point=min(candidates,key=lambda p:math.dist(p,(x,y)));distance=math.dist(point,(x,y))
   if 0<distance<=.00025:
    frag=re.sub(r'\('+k+r'\s+[-\d.]+\s+[-\d.]+',f'({k} {point[0]:.6f} {point[1]:.6f}',frag,count=1)
    snapped.append(dict(net=net,field=k,before=[x,y],after=point,displacement_mm=distance))
  edits.append((start,end,frag))
for start,end,frag in reversed(sorted(edits)):s=s[:start]+frag+s[end:]
a.output.write_text(s);a.output.with_suffix('.rounding.json').write_text(json.dumps(dict(tolerance_mm=.00025,snapped=snapped),indent=2)+'\n');print('Restored coordinate precision at',len(snapped),'same-net junction endpoints.')
