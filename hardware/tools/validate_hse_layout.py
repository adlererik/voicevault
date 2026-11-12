#!/usr/bin/env python3
"""Check the explicit four-footprint HSE stage, retaining all existing copper.

Run with KiCad's native Python. This is CAD validation, not oscillator startup,
EMC, crystal load-capacitance qualification or independent electrical approval.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import pcbnew
from qualify_routing_candidate import geometry,laser_geometry

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'

def pads(board):
    return sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,
                   p.GetSize().x,p.GetSize().y,p.GetOrientationDegrees()%360,p.GetLayerSet().FmtBin())
                  for f in board.GetFootprints() for p in f.Pads())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('candidate',type=Path);parser.add_argument('placement_record',type=Path)
    args=parser.parse_args();candidate=args.candidate.resolve();meta=json.loads(args.placement_record.read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source_hash=digest(SOURCE);candidate_hash=digest(candidate)
    assert source_hash==meta['source_sha256'],'Live source changed'
    assert set(meta['moves'])=={'X301','C301','C302','R601'},'Only the reviewed four-footprint stage is permitted'
    source=pcbnew.LoadBoard(str(SOURCE));board=pcbnew.LoadBoard(str(candidate))
    source_parts={f.GetReference():f for f in source.GetFootprints()};target_parts={f.GetReference():f for f in board.GetFootprints()}
    assert set(source_parts)==set(target_parts)
    fixed={geometry(source,t) for t in source.GetTracks()}
    assert fixed<={geometry(board,t) for t in board.GetTracks()},'Original copper changed'
    def distance_to_crystal(parts,cap,pin):
        a=next(p.GetPosition() for p in parts[cap].Pads() if p.GetNumber()=='1')
        z=next(p.GetPosition() for p in parts['X301'].Pads() if p.GetNumber()==pin)
        return math.hypot(a.x-z.x,a.y-z.y)/1e6
    previous={c:distance_to_crystal(source_parts,c,p) for c,p in [('C301','1'),('C302','3')]}
    for ref,(x,y,angle,side) in meta['moves'].items():
        f=source_parts[ref]
        if source.GetLayerName(f.GetLayer())!=side:f.Flip(f.GetPosition(),False)
        f.SetOrientationDegrees(angle);f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    assert pads(source)==pads(board),'Unexpected pad, layer, size or net change'
    for ref in source_parts:
        a,z=source_parts[ref],target_parts[ref]
        assert (a.GetPosition().x,a.GetPosition().y,a.GetOrientationDegrees()%360,a.GetLayer())==(z.GetPosition().x,z.GetPosition().y,z.GetOrientationDegrees()%360,z.GetLayer()),ref
    new=[t for t in board.GetTracks() if geometry(board,t) not in fixed]
    assert all(t.GetNetname() in ['GND','MCU_HSE_IN','MCU_HSE_OUT'] for t in new)
    via_items=[t for t in new if isinstance(t,pcbnew.PCB_VIA)]
    assert len(via_items)==7 and all(t.GetViaType()==pcbnew.VIATYPE_MICROVIA and t.GetNetname()=='GND' for t in via_items)
    assert all(isinstance(t,pcbnew.PCB_VIA) or board.GetLayerName(t.GetLayer())=='F.Cu' for t in new)
    board.BuildConnectivity();board.GetConnectivity().RecalculateRatsnest()
    laser=laser_geometry(board);assert not laser['violations'],laser
    result=subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(candidate.parent/'drc.json'),str(candidate)],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    assert not json.loads((candidate.parent/'drc.json').read_text())['violations'],'Native DRC failed'
    assert digest(SOURCE)==source_hash and digest(candidate)==candidate_hash,'Files changed during validation'
    lengths={net:sum(t.GetLength()/1e6 for t in new if not isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()==net) for net in ['MCU_HSE_IN','MCU_HSE_OUT']}
    report=dict(source_sha256=source_hash,candidate_sha256=candidate_hash,moves=meta['moves'],
        original_copper_items=len(list(source.GetTracks())),new_copper_items=len(new),total_copper_items=len(list(board.GetTracks())),
        unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),native_layout_violations=0,
        laser_geometry_violations=0,laser_vias=laser['laser_vias'],all_expected_world_pads_verified=True,
        original_copper_preserved=True,capacitor_to_crystal_direct_mm_before=previous,
        capacitor_to_crystal_direct_mm_after={c:distance_to_crystal(target_parts,c,p) for c,p in [('C301','1'),('C302','3')]},
        routed_net_total_length_mm=lengths,manufacturing_ready=False,
        scope='Explicit HSE CAD stage; oscillator startup, parasitic load, noise and physical function remain unqualified')
    (candidate.parent/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    (candidate.parent/'laser-geometry.json').write_text(json.dumps(laser,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
