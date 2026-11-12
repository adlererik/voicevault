#!/usr/bin/env python3
"""Audit laser-via geometry omitted by native mechanical-hole spacing checks.

Public provisional JLC rules, not factory DFM/stackup acceptance. Model each
laser hole as a finished circle and evaluate only overlapping copper spans.
No dielectric/aspect-ratio pass is inferred from the board's total thickness.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'
CACHE=ROOT/'.lab-cache/hardware/routing-b0'
OUT=ROOT/'.lab-runs/hardware/standalone-b0/hdi-geometry.json'

def distance_to_segment(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];square=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/square)) if square else 0
    return math.dist(p,[a[0]+t*dx,a[1]+t*dy])

def audit(data):
    issues=[];pairs=0;foreign_tracks=0
    vias=[t for t in data['tracks'] if t['kind']=='via']
    laser=[t for t in vias if t['microvia']]
    for v in laser:
        at=[v['x'],v['y']]
        def fail(rule,**details):issues.append(dict(rule=rule,at_mm=at,net=v['net'],**details))
        if not .075-1e-6<=v['drill']<=.15+1e-6:fail('laser drill range')
        if v['w']-v['drill']<.15-1e-6:fail('laser capture annulus')
        if v['layers'] not in [['F.Cu','In1.Cu'],['In4.Cu','B.Cu']]:fail('first-order adjacent-layer span')
        edge=min(v['x']-25,95-v['x'],v['y']-25,70-v['y'])-v['drill']/2
        if edge<.35-1e-6:fail('laser hole to board edge',actual_mm=edge)
        for other in vias:
            if other is v or not set(v['layers'])&set(other['layers']):continue
            # Report each laser/laser pair once, every laser/mechanical pair.
            if other['microvia'] and id(other)<id(v):continue
            pairs+=1;limit=.13 if other['net']==v['net'] else .24
            actual=math.dist(at,[other['x'],other['y']])-(v['drill']+other['drill'])/2
            if actual<limit-1e-6:fail('hole edge spacing',other_net=other['net'],actual_mm=actual,minimum_mm=limit)
        for t in data['tracks']:
            if t['kind']!='track' or t['net']==v['net'] or not set(t['layers'])&set(v['layers']):continue
            foreign_tracks+=1
            actual=distance_to_segment(at,t['start'],t['end'])-(v['drill']+t['w'])/2
            if actual<.15-1e-6:fail('laser hole to foreign trace',other_net=t['net'],actual_mm=actual)
    return dict(laser_vias=len(laser),overlapping_hole_pairs_checked=pairs,
                foreign_track_pairs_checked=foreign_tracks,violations=issues)

def main():
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    subprocess.run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',
                    str(ROOT/'hardware/tools/export_routing_geometry.py')],check=True,timeout=60)
    data=json.loads((CACHE/'obstacles.json').read_text());assert data['source_sha256']==before
    result=audit(data)
    # Deliberately add a foreign hole 0.20mm away in a copy: native mechanical
    # hole spacing does not cover this laser pair, so this audit must catch it.
    assert result['laser_vias'],'Expected B0 laser-via test subject'
    bad=deepcopy(data);v=next(t for t in bad['tracks'] if t['kind']=='via' and t['microvia'])
    injected=dict(v,x=v['x']+.20,net='NEGATIVE_CONTROL_FOREIGN_NET')
    bad['tracks'].append(injected)
    assert any(i['rule']=='hole edge spacing' for i in audit(bad)['violations']), 'Negative control missed'
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==before,'Live board changed'
    result.update(source_sha256=before,result='fail' if result['violations'] else 'pass',
        negative_control='Foreign laser hole at 0.20mm center spacing rejected in memory-only copy',
        live_design_unchanged=True,source='https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq',
        scope='Nominal hole/capture/span/trace geometry; native DRC covers component holes and copper.',
        unresolved=['Exact factory dielectric construction and laser aspect ratio',
                    'Filled/planarized via-in-pad, mask/paste and assembly acceptance'],manufacturing_ready=False)
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return bool(result['violations'])

if __name__=='__main__':raise SystemExit(main())
