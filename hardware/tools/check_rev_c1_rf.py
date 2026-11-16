#!/usr/bin/env python3
"""Run isolated native RF rule controls; never place/route the C1 input."""
import json
from pathlib import Path
import re
import subprocess
from finalize_rev_c_quilter_input import parse,child,children
from prepare_rev_c_retry import spans,fp_ref

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c1'
OUT=ROOT/'.lab-runs/hardware/standalone-c1/rf-controls'
NAME='voicevault-standalone-c1'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    text=(DESIGN/(NAME+'.kicad_pcb')).read_text();edits=[]
    for a,b in spans(text,'footprint'):
        f=parse(text[a:b]);ref=fp_ref(f)
        if ref=='C7':continue  # Real GND node for wrong-net fixture.
        if ref!='AE201':edits.append((a,b,''));continue
        fragment=text[a:b];x,y=map(float,child(f,'at')[1:3])
        fragment=re.sub(r'\(at\s+[\d.-]+\s+[\d.-]+\)', '(at 30 30)',fragment,count=1)
        fragment=re.sub(r'\(xy\s+([\d.-]+)\s+([\d.-]+)\)',
            lambda m:f'(xy {float(m[1])-x+30:g} {float(m[2])-y+30:g})',fragment)
        edits.append((a,b,fragment))
    edits += [(a,b,'') for a,b in spans(text,'zone')]
    for a,b,value in sorted(edits,reverse=True):text=text[:a]+value+text[b:]
    cases=[('same-side-feed','F.Cu','BLE_ANT_FEED',(26.9,30,28.55,30),False),
           ('opposite-side-feed','B.Cu','BLE_ANT_FEED',(26.9,30,28.55,30),True),
           ('inner-layer-feed','In3.Cu','BLE_ANT_FEED',(26.9,30,28.55,30),True),
           ('wrong-net-feed','F.Cu','GND',(26.9,30,27.5,30),True),
           ('outside-corridor','F.Cu','BLE_ANT_FEED',(27,31,28.55,31),True)]
    results=[]
    for name,layer,net,(x1,y1,x2,y2),expected in cases:
        path=OUT/(name+'.kicad_pcb')
        for suffix in ['.kicad_pro','.kicad_dru']:
            path.with_suffix(suffix).write_bytes((DESIGN/(NAME+suffix)).read_bytes())
        track=f'(segment (start {x1} {y1}) (end {x2} {y2}) (width 0.12) (layer "{layer}") (net "{net}"))\n'
        path.write_text(text.rstrip()[:-1]+track+')\n')
        target=OUT/(name+'.json')
        p=subprocess.run(['flatpak','run','--user',
            '--env=KICAD_CONFIG_HOME='+str(ROOT/'.lab-cache/kicad-revc-checks'),
            '--command=kicad-cli','org.kicad.KiCad','pcb','drc','--format','json',
            '--output',str(target),str(path)],capture_output=True,text=True,timeout=60)
        assert p.returncode==0,p.stderr
        report=json.loads(target.read_text())
        detected=any(v['type']=='items_not_allowed' for v in report['violations'])
        assert detected==expected,(name,report['violations'])
        results.append(dict(case=name,forbidden_item_detected=detected,expected=expected,passed=True))
    summary=dict(status='PASS',scope='isolated copies; not placed or routed C1',cases=results)
    (ROOT/'hardware/evidence/2026-11-16/c1-preparation/rf-controls.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Five isolated native RF controls passed; C1 input unchanged.')


if __name__=='__main__':main()
