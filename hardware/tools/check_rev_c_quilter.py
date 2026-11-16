#!/usr/bin/env python3
"""Test C0 layout policy on isolated copies; never place or route the design."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c'
OUT=ROOT/'.lab-runs/hardware/standalone-c0/quilter-policy'
NAME='voicevault-standalone-c0'
CASES=['clean','allowed-feed','wrong-net','guard-track','wrong-layer','forbidden-via','other-footprint']


def fixtures():
    import pcbnew
    board=pcbnew.LoadBoard(str(DESIGN/(NAME+'.kicad_pcb')))
    intent=json.loads((DESIGN/'quilter-intent.json').read_text())
    assert hashlib.sha256((DESIGN/(NAME+'.kicad_pcb')).read_bytes()).hexdigest()==intent['source_board_sha256']
    assert not list(board.GetTracks()) and all(z.GetIsRuleArea() for z in board.Zones())
    assert {z.GetZoneName() for z in board.Zones()}=={r['name'] for r in intent['regions']}
    for z in board.Zones():
        assert not any([z.GetDoNotAllowTracks(),z.GetDoNotAllowVias(),z.GetDoNotAllowZoneFills(),
                        z.GetDoNotAllowPads(),z.GetDoNotAllowFootprints()])
    antenna=next(f for f in board.GetFootprints() if f.GetReference()=='AE201')
    assert {z.GetZoneName() for z in antenna.Zones()}=={'VV_ANTENNA_NO_COPPER','VV_ANTENNA_TRACK_GUARD'}
    assert all(len(list(z.GetLayerSet().Seq()))==6 for z in antenna.Zones())
    assert board.GetLayerName(pcbnew.In1_Cu)=='GND_L2' and board.GetLayerName(pcbnew.In4_Cu)=='GND_L5'
    (OUT/'inventory.json').write_text(json.dumps({'footprints':len(list(board.GetFootprints())),
        'physical_pad_objects':sum(len(list(f.Pads())) for f in board.GetFootprints()),
        'regions':len(list(board.Zones())),'antenna_rule_areas':len(list(antenna.Zones()))},indent=2)+'\n')
    for case in CASES:
        b=pcbnew.LoadBoard(str(DESIGN/(NAME+'.kicad_pcb')))
        antenna=next(f for f in b.GetFootprints() if f.GetReference()=='AE201')
        # Test fixture only: a rule area must be exercised inside the outline.
        # Off-board inventory copper is not an adequate negative test.
        antenna.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(50),pcbnew.FromMM(50)))
        origin=antenna.GetPosition()
        if case in ['allowed-feed','wrong-net','guard-track','wrong-layer']:
            track=pcbnew.PCB_TRACK(b);track.SetWidth(pcbnew.FromMM(.1))
            track.SetLayer(pcbnew.B_Cu if case=='wrong-layer' else pcbnew.F_Cu)
            track.SetNet(b.FindNet('GND' if case=='wrong-net' else 'BLE_ANT_FEED'))
            start=(-3,0);end=(-1.5,0)
            if case=='wrong-net':end=(-2.25,0)  # Deliberately avoid a pad short.
            if case=='guard-track':start=(0,1.5);end=(1,1.5)
            for setter,point in [(track.SetStart,start),(track.SetEnd,end)]:
                setter(origin+pcbnew.VECTOR2I(*(pcbnew.FromMM(x) for x in point)))
            b.Add(track)
        if case=='forbidden-via':
            via=pcbnew.PCB_VIA(b);via.SetPosition(origin+pcbnew.VECTOR2I(pcbnew.FromMM(-2.6),0))
            via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetWidth(pcbnew.FromMM(.45));via.SetDrill(pcbnew.FromMM(.2))
            via.SetNet(b.FindNet('BLE_ANT_FEED'));b.Add(via)
        if case=='other-footprint':
            f=next(f for f in b.GetFootprints() if f.GetReference()=='C201')
            f.SetPosition(origin+pcbnew.VECTOR2I(pcbnew.FromMM(1.6),pcbnew.FromMM(1.8)))
        folder=OUT/case;folder.mkdir(exist_ok=True)
        pcbnew.SaveBoard(str(folder/'test.kicad_pcb'),b)
        for suffix in ['.kicad_pro','.kicad_dru']:
            shutil.copyfile(DESIGN/(NAME+suffix),folder/('test'+suffix))
        shutil.copyfile(DESIGN/'fp-lib-table',folder/'fp-lib-table')
        if not (folder/'VoiceVault_B0.pretty').exists():
            (folder/'VoiceVault_B0.pretty').symlink_to(DESIGN/'VoiceVault_B0.pretty',target_is_directory=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if '--fixtures' in sys.argv:
        fixtures();return
    source=DESIGN/(NAME+'.kicad_pcb');before=hashlib.sha256(source.read_bytes()).hexdigest()
    subprocess.run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',__file__,'--fixtures'],
                   cwd=ROOT,check=True,timeout=60)
    results=[]
    for case in CASES:
        folder=OUT/case
        with (folder/'drc.log').open('w') as log:
            subprocess.run(['flatpak','run','--user',f'--env=KICAD_CONFIG_HOME={ROOT/".lab-cache/kicad-revc-checks"}',
                '--command=kicad-cli','org.kicad.KiCad','pcb','drc','--format','json','--output',folder/'drc.json',
                folder/'test.kicad_pcb'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        drc=json.loads((folder/'drc.json').read_text())
        types=Counter(x['type'] for x in drc['violations'])
        denied=types.get('items_not_allowed',0)
        passed=(denied==0) if case in ['clean','allowed-feed'] else denied>0
        if case=='clean' and drc['violations']:passed=False
        results.append(dict(case=case,status='PASS' if passed else 'FAIL',violation_types=dict(types)))
    assert before==hashlib.sha256(source.read_bytes()).hexdigest(),'Rule tests changed the actual PCB'
    report=dict(scope='Native rule enforcement on test copies, not RF performance or cloud-parser proof',
        source_board_sha256=before,live_design_modified=False,
        inventory=json.loads((OUT/'inventory.json').read_text()),cases=results,
        status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL')
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['status']!='PASS':sys.exit(1)


if __name__=='__main__':main()
