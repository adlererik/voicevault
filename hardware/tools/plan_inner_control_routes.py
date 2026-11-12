#!/usr/bin/env python3
"""Propose control routes on In2/In3 using ordinary, outside-pad dogbone vias.

No power/RF/audio-clock suitability is inferred. The caller supplies explicit
control nets. Uses conservative all-layer via clearance and the native import
qualifier remains the acceptance authority. No live PCB writes.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from shapely.geometry import Point,LineString,box
from shapely.strtree import STRtree
from plan_local_control_routes import CACHE,WIDTH,obstacles,search

LAYERS=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']

def shape(p):
    if p.get('kind')=='via':return Point(p['x'],p['y']).buffer(p['w']/2+.0001)
    if p.get('kind')=='track':return LineString([p['start'],p['end']]).buffer(p['w']/2+.0001)
    return Point(p['x'],p['y']).buffer(p['w']/2+.0001) if p['shape']=='circle' else box(*p['box'])

def candidates(data,pad,gateway=False):
    records=[p for p in data['pads'] if p['layers'] or max(p['drill'])>0]+data['tracks']
    shapes=[shape(p) for p in records];tree=STRtree(shapes);net=pad['net']
    own=shape(pad);face=next(l for l in ['F.Cu','B.Cu'] if l in pad['layers'])
    possible=[]
    offsets=[(x,y) for x in [-.4,0,.4] for y in [-.4,0,.4] if x or y]
    if gateway:
        offsets += [(x,y) for x in [-3.6,-2.8,-2.,-1.2,-.4,.4,1.2,2.,2.8,3.6]
                    for y in [-3.6,-2.8,-2.,-1.2,-.4,.4,1.2,2.,2.8,3.6]
                    if math.hypot(x,y)<=4.2]
    for radius in ([.8,1.2,1.6,2.,2.4,3.2,4.] if gateway else [.6,.8,1.,1.2]):
        offsets += [(radius*math.cos(a*math.pi/4),radius*math.sin(a*math.pi/4)) for a in range(8)]
    for dx,dy in offsets:
        xy=[round(pad['x']+dx,6),round(pad['y']+dy,6)];point=Point(xy)
        if not (25.7<xy[0]<94.3 and 25.7<xy[1]<69.3):continue
        if box(24.6,24.6,39.3,32.3).contains(point):continue
        if point.distance(own)<.33:continue # ordinary unfilled via outside solder land
        line=LineString([[pad['x'],pad['y']],xy]);blocked=False
        nearby=tree.query(line.buffer(.8))
        for idx in nearby:
            other,g=records[idx],shapes[idx]
            if other['net']==net:
                if other.get('kind')=='via':
                    actual=math.dist(xy,[other['x'],other['y']])-(.2+other['drill'])/2
                    if actual<.255:blocked=True;break
                continue
            # Copper plus the default 0.25mm drill-edge to foreign-pad clearance.
            via_clear=.355 if 'ref' in other else .33
            if other['net']=='GND' and other.get('ref') in ['U8','U601','U602','U401','U1001']:
                via_clear=max(via_clear,.55) # preserve room for outer-plane thermals
            if point.distance(g)<via_clear:blocked=True;break
            if not gateway and face in other['layers']:
                clearance=max(.105,other.get('mask_margin_mm',0)+.095)
                if line.distance(g)<WIDTH/2+clearance:blocked=True;break
            drill=other.get('drill',0)
            if isinstance(drill,list):drill=max(drill)
            if drill and 'x' in other:
                actual=math.dist(xy,[other['x'],other['y']])-(.2+drill)/2
                if actual<.255:blocked=True;break
        if not blocked:
            possible.append(dict(kind='via',microvia=False,net=net,x=xy[0],y=xy[1],w=.45,drill=.2,layers=LAYERS,
                                 face=face,pad=[pad['x'],pad['y']]))
    return sorted(possible,key=lambda p:math.dist(p['pad'],[p['x'],p['y']]))[:12 if gateway else 6]


def hybrid_escape(data,pad):
    """Adjacent-layer laser via to an ordinary gateway; no stacked/skip vias."""
    face=next(l for l in ['F.Cu','B.Cu'] if l in pad['layers'])
    # Capture land stays within these existing pads. The reviewed nPM footprint
    # has explicit enlarged mask apertures; other tiny WLCSPs need a separate
    # package/mask adaptation and are not guessed here.
    if min(pad['w'],pad['h'])<.25-1e-6 and not (pad['ref']=='U3' and pad['mask_margin_mm']>=.0525-1e-6):
        return None
    span=['F.Cu','In1.Cu'] if face=='F.Cu' else ['In4.Cu','B.Cu']
    inner=span[1] if face=='F.Cu' else span[0]
    micro=dict(kind='via',microvia=True,net=pad['net'],x=pad['x'],y=pad['y'],w=.25,drill=.1,layers=span)
    point=Point(pad['x'],pad['y'])
    for t in data['tracks']:
        if not set(t['layers'])&set(span):continue
        if t['kind']=='via':
            actual=point.distance(Point(t['x'],t['y']))-(.1+t['drill'])/2
            if actual<(.13 if t['net']==pad['net'] else .24)+.005:return None
        if t['net']!=pad['net'] and point.distance(shape(t))<.23:return None
    proposed=deepcopy(data);proposed['tracks'].append(micro)
    gateways=candidates(proposed,pad,gateway=True)
    for gateway in gateways[:8]:
        path,why=search([pad['x'],pad['y']],[gateway['x'],gateway['y']],
                        obstacles(proposed,pad['net'],inner),margin=1.5)
        if path:
            gateway['escape_routes']=[dict(net=pad['net'],layer=inner,width_mm=WIDTH,points=path)]
            gateway['extra_vias']=[micro]
            return gateway
    return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--nets',nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-laser-escapes',action='store_true')
    args=p.parse_args();data=json.loads((CACHE/'obstacles.json').read_text());by_net=defaultdict(list)
    for pad in data['pads']:
        if pad['net']:by_net[pad['net']].append(pad)
    routes=[];vias=[];results=[]
    for net in args.nets:
        pads=by_net[net]
        if not 2<=len(pads)<=6:
            results.append(dict(net=net,result='unsupported endpoint count'));continue
        local=deepcopy(data);choices=[];why='no ordinary escape'
        for pad in pads:
            options=candidates(local,pad)
            if not options and args.allow_laser_escapes:
                hybrid=hybrid_escape(local,pad)
                if hybrid:options=[hybrid]
            if not options:break
            # Reserve the closest safe escape, conservatively preventing new
            # vias from colliding before an inner-layer path is attempted.
            v=options[0];choices.append(v);local['tracks'].append(v)
            if 'escape_routes' in v:
                local['tracks']+=v['extra_vias']
                for path in v['escape_routes']:
                    for a,b in zip(path['points'],path['points'][1:]):local['tracks'].append(dict(kind='track',net=net,start=a,end=b,w=WIDTH,layers=[path['layer']]))
            else:local['tracks'].append(dict(kind='track',net=net,start=v['pad'],end=[v['x'],v['y']],w=WIDTH,layers=[v['face']]))
        if len(choices)==len(pads):
            connected=[choices[0]];pending=choices[1:];net_routes=[]
            while pending:
                edges=sorted((math.dist([a['x'],a['y']],[b['x'],b['y']]),i,j)
                             for i,a in enumerate(connected) for j,b in enumerate(pending))
                found=False
                for _,i,j in edges:
                    a,b=connected[i],pending[j]
                    for layer in ['In2.Cu','In3.Cu']:
                        path,why=search([a['x'],a['y']],[b['x'],b['y']],obstacles(local,net,layer),margin=4)
                        if path:
                            net_routes.append(dict(net=net,layer=layer,width_mm=WIDTH,points=path));found=True;break
                    if found:connected.append(pending.pop(j));break
                if not found:break
            if not pending:
                for v in choices:
                    if 'escape_routes' in v:net_routes+=v['escape_routes']
                    else:net_routes.append(dict(net=net,layer=v['face'],width_mm=WIDTH,points=[v['pad'],[v['x'],v['y']]]))
                routes+=net_routes;vias+=choices;vias+=[m for v in choices for m in v.get('extra_vias',[])];data=local
                for path in net_routes:
                    for a,b in zip(path['points'],path['points'][1:]):data['tracks'].append(dict(kind='track',net=net,start=a,end=b,w=WIDTH,layers=[path['layer']]))
                why='proposed'
        results.append(dict(net=net,result=why,endpoint_escapes=len(choices)));print(results[-1],flush=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(dict(source_sha256=data['source_sha256'],routes=routes,vias=vias,results=results,
            scope='Proposal only. Native DRC, electrical review and separate acceptance required.'),indent=2)+'\n')

if __name__=='__main__':main()
