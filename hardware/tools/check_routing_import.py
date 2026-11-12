#!/usr/bin/env python3
"""Exercise copper acceptance/rejection on copies without changing the live PCB."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'
OUT = ROOT/'.lab-runs/hardware/standalone-b0/import-control'


def inject():
    import pcbnew
    board = pcbnew.LoadBoard(str(SOURCE))
    parts = {f.GetReference(): f for f in board.GetFootprints()}
    def position(ref, pin):
        return next(p.GetPosition() for p in parts[ref].Pads() if p.GetNumber() == pin)
    paths = [('RAD_ANT', position('U6','D1'), position('C203','1')),
             ('SD_CS_MCU', pcbnew.VECTOR2I(pcbnew.FromMM(35),pcbnew.FromMM(28)),
                           pcbnew.VECTOR2I(pcbnew.FromMM(36),pcbnew.FromMM(28)))]
    for net, start, end in paths:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(start); track.SetEnd(end)
        track.SetWidth(pcbnew.FromMM(.1)); track.SetLayer(pcbnew.F_Cu)
        track.SetNetCode(board.FindNet(net).GetNetCode()); board.Add(track)
    pcbnew.SaveBoard(str(OUT/'proposed.kicad_pcb'),board)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inject',action='store_true')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.inject:
        return inject()
    original=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    native=['flatpak','run','--user','--command=python3','org.kicad.KiCad']
    with (OUT/'control.log').open('w') as log:
        subprocess.run(native+[str(Path(__file__).resolve()),'--inject'],check=True,
                       stdout=log,stderr=subprocess.STDOUT,timeout=30)
        subprocess.run(native+[str(ROOT/'hardware/tools/qualify_routing_candidate.py'),
                       str(OUT/'proposed.kicad_pcb'),'--output-dir',str(OUT/'qualified')],
                       check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    result=json.loads((OUT/'qualified/qualification.json').read_text())
    assert result['accepted_net_groups']==['RAD_ANT'], 'Valid existing-net connection was not retained'
    assert {n for row in result['rejected_rounds'] for n in row['rejected_nets']}=={'SD_CS_MCU'}
    assert result['added_copper_items']==1 and result['native_layout_violations']==0
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==original, 'Live board changed'
    result['live_design_unchanged']=True
    result['control_scope']='Copy-only import: retain an allowed RF connection, reject an antenna-area intrusion, preserve original pads and copper. No physical or manufacturing qualification.'
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Routing import control passed; live design unchanged.')


if __name__=='__main__':
    sys.exit(main() or 0)
