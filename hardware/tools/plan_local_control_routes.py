#!/usr/bin/env python3
"""Propose short, single-layer control routes; native DRC must qualify output.

This conservative grid search uses actual pads, holes and fixed copper. It does
not route power, clocks, RF or audio automatically, infer electrical suitability,
or write the live PCB. Run with the pinned routing environment after exporting
geometry with KiCad's bundled Python.
"""
import argparse
from collections import defaultdict
import heapq
import json
import math
from pathlib import Path
import time

import numpy as np
from shapely import intersects_xy
from shapely.geometry import Point, LineString, box

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.lab-cache/hardware/routing-b0'
STEP = .025
WIDTH = .10
CLEARANCE = .105  # 5um numerical margin above the native 0.10mm rule


def polish(points, shapes):
    """Remove grid stair steps with continuous-checked 45-degree shortcuts."""
    output=[points[0]]; i=0
    while i<len(points)-1:
        for j in range(len(points)-1,i,-1):
            a,z=points[i],points[j];dx=z[0]-a[0];dy=z[1]-a[1]
            sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
            bends=([[a[0]+sx*abs(dy),z[1]],[z[0]-sx*abs(dy),a[1]]]
                   if abs(dx)>=abs(dy) else
                   [[z[0],a[1]+sy*abs(dx)],[a[0],z[1]-sy*abs(dx)]])
            found=None
            for bend in bends:
                trial=[a,bend,z];line=LineString(trial)
                if not any(line.intersects(s) for s in shapes):found=trial;break
            if found:
                output.extend(p for p in found[1:] if math.dist(output[-1],p)>1e-6)
                i=j;break
        else:
            # The original path passed continuous checks; retain its next edge.
            i+=1;output.append(points[i])
    return output


def obstacles(data, net, layer):
    result = []
    for p in data['pads']:
        if p['net'] == net:
            continue
        if layer in p['layers']:
            g = (Point(p['x'], p['y']).buffer(p['w']/2 + .0001)
                 if p['shape'] == 'circle' else box(*p['box']))
            margin = CLEARANCE
            if layer in ('F.Cu', 'B.Cu'):
                margin = max(margin, p['mask_margin_mm'] + .095)
            result.append(g.buffer(margin + WIDTH/2))
        if max(p['drill']) > 0:
            # Conservative enclosing circle also covers rotated/slotted holes.
            result.append(Point(p['x'], p['y']).buffer(max(p['drill'])/2 + .255 + WIDTH/2))
    for t in data['tracks']:
        if t['net'] == net or layer not in t['layers']:
            continue
        g = (Point(t['x'], t['y']) if t['kind'] == 'via'
             else LineString([t['start'], t['end']]))
        result.append(g.buffer(t['w']/2 + CLEARANCE + WIDTH/2))
    result += [box(25, 25, 38.9, 31.9)]  # all-layer radio reservation
    return result


def search(start, end, shapes, margin=3.0):
    lo = np.floor((np.minimum(start, end)-margin)/STEP)*STEP
    hi = np.ceil((np.maximum(start, end)+margin)/STEP)*STEP
    lo = np.maximum(lo, [25.4, 25.4]); hi = np.minimum(hi, [94.6, 69.6])
    nx, ny = (np.rint((hi-lo)/STEP).astype(int)+1)
    free = np.ones((ny, nx), dtype=bool)
    for g in shapes:
        a,b,c,d = g.bounds
        ix0=max(0,int(math.floor((a-lo[0])/STEP))); ix1=min(nx-1,int(math.ceil((c-lo[0])/STEP)))
        iy0=max(0,int(math.floor((b-lo[1])/STEP))); iy1=min(ny-1,int(math.ceil((d-lo[1])/STEP)))
        if ix1 < ix0 or iy1 < iy0:
            continue
        xs=lo[0]+np.arange(ix0,ix1+1)*STEP
        ys=lo[1]+np.arange(iy0,iy1+1)*STEP
        free[iy0:iy1+1,ix0:ix1+1] &= ~intersects_xy(g,xs[None,:],ys[:,None])
    def grid(p): return tuple(np.rint((np.asarray(p)-lo)/STEP).astype(int))
    a,z=grid(start),grid(end)
    if not free[a[1],a[0]] or not free[z[1],z[0]]:
        return None, 'endpoint blocked'
    def h(x,y):
        dx,dy=abs(z[0]-x),abs(z[1]-y)
        return max(dx,dy)+(math.sqrt(2)-1)*min(dx,dy)
    dist={a:0.}; parent={}; queue=[(h(*a),0.,a)]
    directions=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    deadline=time.monotonic()+4
    expanded=0
    while queue:
        _,g,u=heapq.heappop(queue)
        if g>dist[u]+1e-9: continue
        if u==z:
            route=[u]
            while route[-1]!=a: route.append(parent[route[-1]])
            route.reverse(); keep=[route[0]]
            for i in range(1,len(route)-1):
                before=(route[i][0]-route[i-1][0],route[i][1]-route[i-1][1])
                after=(route[i+1][0]-route[i][0],route[i+1][1]-route[i][1])
                if before!=after: keep.append(route[i])
            keep.append(route[-1])
            points=[list(start)]+[(lo+np.array(p)*STEP).round(6).tolist() for p in keep]+[list(end)]
            points=[p for i,p in enumerate(points) if i==0 or math.dist(p,points[i-1])>1e-6]
            # Validate continuous segments too, including off-grid pad centers.
            line=LineString(points)
            if any(line.intersects(s) for s in shapes): return None,'continuous clearance check'
            return polish(points,shapes),'proposed'
        expanded+=1
        if expanded%1024==0 and (time.monotonic()>deadline or expanded>100000):
            return None,'bounded search timeout'
        x,y=u
        for dx,dy in directions:
            xx,yy=x+dx,y+dy
            if not (0<=xx<nx and 0<=yy<ny) or not free[yy,xx]: continue
            if dx and dy and not (free[y,xx] and free[yy,x]): continue
            v=(xx,yy); ng=g+(math.sqrt(2) if dx and dy else 1)
            if ng+1e-9>=dist.get(v,float('inf')): continue
            dist[v]=ng;parent[v]=u;heapq.heappush(queue,(ng+h(xx,yy),ng,v))
    return None,'no path'


def main():
    p=argparse.ArgumentParser();p.add_argument('--nets',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    data=json.loads((CACHE/'obstacles.json').read_text());by_net=defaultdict(list)
    for pad in data['pads']:
        if pad['net']: by_net[pad['net']].append(pad)
    routes=[];results=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for net in args.nets:
        pads=by_net[net];common=set.intersection(*(set(p['layers']) for p in pads))
        layers=[l for l in ['F.Cu','B.Cu'] if l in common]
        if not layers or not 2<=len(pads)<=6:
            results.append(dict(net=net,result='unsupported endpoint topology'));continue
        # Greedy minimum spanning tree, with every endpoint explicitly reached.
        connected=[pads[0]];pending=pads[1:];net_routes=[];reason='no path'
        while pending:
            edges=sorted((math.dist((a['x'],a['y']),(b['x'],b['y'])),i,j)
                         for i,a in enumerate(connected) for j,b in enumerate(pending))
            found=False
            for _,i,j in edges:
                a,b=connected[i],pending[j]
                for layer in layers:
                    shapes=obstacles(data,net,layer)
                    path,reason=search([a['x'],a['y']],[b['x'],b['y']],shapes)
                    if path:
                        net_routes.append(dict(net=net,layer=layer,width_mm=WIDTH,points=path))
                        connected.append(pending.pop(j));found=True;break
                if found:break
            if not found:break
        if not pending:
            routes+=net_routes
            for path in net_routes:
                for a,b in zip(path['points'],path['points'][1:]):
                    data['tracks'].append(dict(kind='track',net=net,start=a,end=b,w=WIDTH,layers=[path['layer']]))
        results.append(dict(net=net,result='proposed' if not pending else reason,connections=len(net_routes)))
        print(results[-1],flush=True)
        args.output.write_text(json.dumps(dict(source_sha256=data['source_sha256'],routes=routes,results=results,
            scope='Proposal only. Native DRC, electrical review and separate hash-bound acceptance required.'),indent=2)+'\n')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(source_sha256=data['source_sha256'],routes=routes,results=results,
        scope='Proposal only. Native DRC, electrical review and separate hash-bound acceptance required.'),indent=2)+'\n')


if __name__=='__main__':main()
