#!/usr/bin/env python3
"""Propose more pad-to-via separation at the two RF shunt ground connections.

Run with KiCad's bundled Python. This writes a candidate only. It preserves all
pad nets and every non-ground track; native DRC/review precede acceptance.
"""
import hashlib
import json
from pathlib import Path
import shutil
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-b';NAME='voicevault-standalone-b0'
SOURCE=DESIGN/(NAME+'.kicad_pcb')
OUT=ROOT/'.lab-cache/hardware/routing-b0/rf-ground-refinement'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    board=pcbnew.LoadBoard(str(SOURCE))
    def signature():
        return sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y)
                      for f in board.GetFootprints() for p in f.Pads())
    before=signature()
    def point(xy):return pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in xy])
    def near(a,b):return abs(a.x-b.x)<10 and abs(a.y-b.y)<10
    changes=[((39.2,32.73),(39.6,32.7),(39.2,32.3)),
             ((34.1,35.4),(34.52,34.98),(34.0,35.5))]
    for old,bend,new in changes:
        vias=[v for v in board.GetTracks() if isinstance(v,pcbnew.PCB_VIA)
              and v.GetNetname()=='GND' and near(v.GetPosition(),point(old))]
        assert len(vias)==1,'Expected original RF ground via; never relocate arbitrary copper'
        tracks=[t for t in board.GetTracks() if type(t)==pcbnew.PCB_TRACK
                and t.GetNetname()=='GND' and near(t.GetEnd(),point(old))]
        assert len(tracks)==1
        track=tracks[0];track.SetEnd(point(bend));vias[0].SetPosition(point(new))
        extra=pcbnew.PCB_TRACK(board);extra.SetStart(point(bend));extra.SetEnd(point(new))
        extra.SetWidth(track.GetWidth());extra.SetLayer(track.GetLayer());extra.SetNetCode(track.GetNetCode());board.Add(extra)
    for name in ['In1.Cu','In4.Cu']:
        board.SetLayerType(board.GetLayerID(name),pcbnew.LT_POWER)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity();board.GetConnectivity().RecalculateRatsnest()
    assert signature()==before
    pcbnew.SaveBoard(str(OUT/SOURCE.name),board)
    for suffix in ['.kicad_pro','.kicad_dru']:
        shutil.copy2(DESIGN/(NAME+suffix),OUT/(NAME+suffix))
    (OUT/'fp-lib-table').write_text((DESIGN/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(DESIGN)))
    (OUT/'refinement.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        candidate_sha256=hashlib.sha256((OUT/SOURCE.name).read_bytes()).hexdigest(),
        moved_ground_vias_mm=changes,added_ground_segments=2,
        ground_reference_layers=['In1.Cu','In4.Cu'],
        unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),
        manufacturing_ready=False,reason='Separate through-via lands from shunt SMD pads; assembly and RF tuning remain unqualified'),indent=2)+'\n')
    print('Wrote RF ground refinement candidate; live board unchanged.')


if __name__=='__main__':main()
