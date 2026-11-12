#!/usr/bin/env python3
"""Compare the selected socket's actual native lands with reviewed drawing data.

SD-104031-001 rev B2 sheet 1: KiCad's local origin/view is rotated 180 degrees
relative to the recommended PCB layout. Latest delivered revision and assembly
acceptance are separate gates; the drawing-copy provenance is recorded in Git.
"""
import json
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-b'

def main():
    footprint=pcbnew.FootprintLoad(str(DESIGN/'VoiceVault_B0.pretty'),'microSD_HC_Molex_104031-0811')
    assert footprint is not None
    expected={str(i+1):[(x,-5.45,.85,1.1)] for i,x in enumerate([-3.105,-2.005,-.905,.195,1.295,2.395,3.495])}
    expected.update({'8':[(4.545,-5.45,.75,1.1)],'9':[(-5.74,.7,1.2,1)],'10':[(-5.74,4.4,1.2,1)],
        'SH':[(-5.565,-5.325,1.55,1.35),(-2.24,5.375,1.9,1.35),(3.73,5.375,1.9,1.35),(5.755,-5.1,1.17,1.8)]})
    actual={}
    for p in footprint.Pads():
        actual.setdefault(p.GetNumber(),[]).append((p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y))
    integer=lambda values:sorted(tuple(pcbnew.FromMM(v) for v in row) for row in values)
    assert set(actual)==set(expected)
    for number in expected:
        # Library serialization is exact to 1nm; allow 2nm conversion rounding.
        assert all(abs(a-b)<=2 for aa,bb in zip(sorted(actual[number]),integer(expected[number])) for a,b in zip(aa,bb)),number
        assert len(actual[number])==len(expected[number]),number
    board=pcbnew.LoadBoard(str(DESIGN/'voicevault-standalone-b0.kicad_pcb'))
    socket=next(f for f in board.GetFootprints() if f.GetReference()=='J401')
    assert socket.GetValue()=='1040310811' and socket.GetFPID().GetLibItemName()=='microSD_HC_Molex_104031-0811'
    mapping={'1':'SD_DAT2','2':'SD_CS_N','3':'SD_MOSI','4':'SD_3V3','5':'SD_SCK','6':'GND','7':'SD_MISO','8':'SD_DAT1','9':'SD_DETECT_N','10':'GND','SH':'GND'}
    assert {p.GetNumber():p.GetNetname() for p in socket.Pads()}==mapping
    assert len(list(socket.Pads()))==14
    assert socket.GetLayer()==pcbnew.F_Cu
    scratch=pcbnew.BOARD();scratch.Add(footprint)
    footprint.SetOrientationDegrees(socket.GetOrientationDegrees());footprint.SetPosition(socket.GetPosition())
    world=lambda f:sorted((p.GetNumber(),p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y,p.GetOrientationDegrees()%360) for p in f.Pads())
    for a,z in zip(world(footprint),world(socket)):
        assert a[0]==z[0] and all(abs(x-y)<=2 for x,y in zip(a[1:5],z[1:5])) and abs(a[5]-z[5])<1e-6,'Actual board land differs from reviewed pattern'
    out=ROOT/'.lab-runs/hardware/standalone-b0/microsd-footprint.json'
    result=dict(result='pass',part='Molex 1040310811',drawing='SD-104031-001 rev B2 sheet 1',
        logical_pins=11,physical_pads=14,actual_board_pin_nets_verified=True,actual_board_land_geometry_verified=True,
        normally_open_card_detect_closes_to_ground=True,
        scope='Nominal reviewed land geometry and pin mapping; not latest-revision, sourcing or physical qualification')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
