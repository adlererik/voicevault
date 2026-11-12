#!/usr/bin/env python3
"""Make KiCad reject forbidden copper on a copy, while accepting the RF feed."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-b'
BOARD=DESIGN/'voicevault-standalone-b0.kicad_pcb'
OUT=ROOT/'.lab-runs/hardware/standalone-b0/antenna-negative'


def inject():
    import pcbnew
    board=pcbnew.LoadBoard(str(BOARD))
    ids={}
    for label,net,y in [('blocked_track','VDD_3V3',28),('allowed_feed','BLE_ANT_FEED',29)]:
        track=pcbnew.PCB_TRACK(board)
        # The forbidden sample must not touch the real antenna pad: KiCad
        # reconciles a track's net with physically connected pads on loading.
        x = 35 if label == 'blocked_track' else 30
        track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
        track.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x+1),pcbnew.FromMM(y)))
        track.SetWidth(pcbnew.FromMM(.15));track.SetLayer(pcbnew.F_Cu)
        track.SetNet(board.FindNet(net));board.Add(track)
        ids[label]=track.m_Uuid.AsString()
    via=pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(33),pcbnew.FromMM(28)))
    via.SetWidth(pcbnew.FromMM(.45));via.SetDrill(pcbnew.FromMM(.2))
    via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetNet(board.FindNet('GND'));board.Add(via)
    ids['blocked_via']=via.m_Uuid.AsString()
    pcbnew.SaveBoard(str(OUT/'negative.kicad_pcb'),board)
    (OUT/'injected.json').write_text(json.dumps(ids,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--inject',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if a.inject:return inject()
    before=hashlib.sha256(BOARD.read_bytes()).hexdigest()
    for suffix in ['.kicad_pro','.kicad_dru']:
        shutil.copyfile(BOARD.with_suffix(suffix),OUT/('negative'+suffix))
    (OUT/'fp-lib-table').write_text((DESIGN/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(DESIGN)))
    subprocess.run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',
                    str(Path(__file__).resolve()),'--inject'],check=True,timeout=30)
    result=subprocess.run(['flatpak','run','--user','--command=kicad-cli','org.kicad.KiCad',
        'pcb','drc','--format','json','--exit-code-violations','--output',str(OUT/'drc.json'),
        str(OUT/'negative.kicad_pcb')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
    (OUT/'drc.log').write_text(result.stdout)
    if result.returncode != 5:raise RuntimeError('Negative copper did not produce the expected DRC failure')
    d=json.loads((OUT/'drc.json').read_text());ids=json.loads((OUT/'injected.json').read_text())
    blocked={i['uuid'] for v in d['violations'] if v['type']=='items_not_allowed' for i in v['items']}
    if not {ids['blocked_track'],ids['blocked_via']} <= blocked:
        raise RuntimeError('Headless DRC failed to reject forbidden antenna-area copper')
    if ids['allowed_feed'] in blocked:raise RuntimeError('Legitimate RF-feed exception was rejected')
    if hashlib.sha256(BOARD.read_bytes()).hexdigest()!=before:raise RuntimeError('Negative control changed the live board file')
    report=dict(result='pass',simulator='KiCad 10.0.8 native DRC',
        rejected=['non-RF track','ground through-via'],allowed=['RF-feed track'],
        live_board_unchanged=True,scope='Geometric rule enforcement only; not RF performance or hardware isolation')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
