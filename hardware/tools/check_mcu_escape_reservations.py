#!/usr/bin/env python3
"""Keep unfinished MCU pads accessible to the planned adjacent-layer escape.

This is a geometric routing policy, not a proof of a complete or manufacturable
fanout. Only the MCU is covered. Other packages still need separate reviews.
"""
import json
import re
from pathlib import Path
import math
import hashlib
import argparse
import pcbnew
from check_hdi_geometry import distance_to_segment

ROOT=Path(__file__).resolve().parents[2]

def audit(board,drc):
    board.BuildConnectivity();board.GetConnectivity().RecalculateRatsnest()
    count=board.GetConnectivity().GetUnconnectedCount(False)
    assert len(drc['unconnected_items'])==count,'Truncated/incomplete native open-net list; cannot infer remaining reservations'
    pending=set()
    for issue in drc['unconnected_items']:
        for item in issue['items']:
            match=re.search(r'\[(.*?)\]',item['description'])
            if match:pending.add(match.group(1))
    mcu=next(f for f in board.GetFootprints() if f.GetReference()=='U1')
    pads=[p for p in mcu.Pads() if p.GetNetname() in pending and p.GetNetname()!='GND']
    collisions=[]
    for pad in pads:
        point=[pad.GetPosition().x/1e6,pad.GetPosition().y/1e6]
        for t in board.GetTracks():
            if t.GetNetname()==pad.GetNetname():continue
            if isinstance(t,pcbnew.PCB_VIA):
                if not t.GetLayerSet().Contains(board.GetLayerID('In1.Cu')):continue
                actual=math.dist(point,[t.GetPosition().x/1e6,t.GetPosition().y/1e6])-t.GetWidth(t.TopLayer())/2e6
                limit=.30 # future 0.10mm laser hole + native 0.25mm hole/capture rule
            else:
                if t.GetLayer()!=board.GetLayerID('In1.Cu'):continue
                actual=distance_to_segment(point,[t.GetStart().x/1e6,t.GetStart().y/1e6],[t.GetEnd().x/1e6,t.GetEnd().y/1e6])-t.GetWidth()/2e6
                limit=.225 # 0.25mm future capture plus 0.10mm copper clearance
            if actual<limit-1e-6:
                collisions.append(dict(pin=pad.GetNumber(),net=pad.GetNetname(),blocker=t.GetNetname(),actual_mm=actual,minimum_mm=limit))
    sites=[dict(ref='U1',pin=p.GetNumber(),net=p.GetNetname(),x=p.GetPosition().x/1e6,y=p.GetPosition().y/1e6,w=.25,layers=['In1.Cu']) for p in pads]
    return dict(result='fail' if collisions else 'pass',reserved_mcu_pads=len(pads),reserved_sites=sites,collisions=collisions,
        scope='Remaining MCU In1 escape sites only; other packages, final escape and manufacturing remain unqualified')

def main():
    out=ROOT/'.lab-runs/hardware/standalone-b0'
    parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path,default=ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb')
    parser.add_argument('--drc',type=Path,default=out/'drc.json');parser.add_argument('--output',type=Path,default=out/'mcu-escape-reservations.json')
    args=parser.parse_args();source=args.board
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    board=pcbnew.LoadBoard(str(source))
    drc=json.loads(args.drc.read_text());result=audit(board,drc)
    if not result['collisions']:
        target=result['reserved_sites'][0]
        original=next(t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)
                      and t.GetLayer()==board.GetLayerID('In1.Cu') and t.GetNetname()=='AUD_SDA')
        fault=pcbnew.PCB_TRACK(board);fault.SetStart(original.GetStart())
        fault.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(target['x']),pcbnew.FromMM(target['y'])))
        fault.SetWidth(pcbnew.FromMM(.1));fault.SetLayer(board.GetLayerID('In1.Cu'));fault.SetNetCode(original.GetNetCode());board.Add(fault)
        bad=audit(board,drc)
        assert any(c['pin']==target['pin'] and c['blocker']=='AUD_SDA' for c in bad['collisions']),'Reservation negative control missed'
        result['negative_control']='Foreign inner-layer branch through a reserved MCU site rejected in a memory-only copy'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    result['source_sha256']=before
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return bool(result['collisions'])

if __name__=='__main__':raise SystemExit(main())
