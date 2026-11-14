#!/usr/bin/env python3
"""Create a copy-only, zero-routing Quilter input with movable electronics.

Run with KiCad's bundled Python. This prepares an experiment, not a fabrication
release. It never writes the source or the live editor's board.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil

import pcbnew


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(fp):
    origin = fp.GetPosition()
    return {
        'value': fp.GetValue(),
        'library': str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName()),
        'angle': fp.GetOrientationDegrees(),
        'layer': int(fp.GetLayer()),
        'pads': sorted((p.GetNumber(), p.GetNetname(),
                        p.GetPosition().x-origin.x, p.GetPosition().y-origin.y,
                        p.GetSize().x, p.GetSize().y,
                        p.GetDrillSize().x, p.GetDrillSize().y,
                        int(p.GetShape()), int(p.GetAttribute()),
                        tuple(p.GetLayerSet().Seq()), p.GetOrientationDegrees(),
                        p.GetOffset().x, p.GetOffset().y,
                        p.GetRoundRectRadiusRatio(), p.GetChamferRectRatio(),
                        int(p.GetChamferPositions()),
                        p.GetLocalClearance(), p.GetLocalSolderMaskMargin(),
                        p.GetLocalSolderPasteMargin(), p.GetLocalSolderPasteMarginRatio())
                       for p in fp.Pads()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    src, out = args.source.resolve(), args.output.resolve()
    assert src.is_dir() and not out.exists()
    name = 'voicevault-standalone-b0'
    source_board = src/(name+'.kicad_pcb')
    source_hash = sha(source_board)
    out.mkdir(parents=True)
    for p in sorted(src.iterdir()):
        if p.suffix in ('.kicad_sch', '.kicad_pro'):
            shutil.copy2(p, out/p.name)
    board = pcbnew.LoadBoard(str(source_board))
    refs = collections.Counter(f.GetReference() for f in board.GetFootprints())
    assert len(refs) == 314 and all(n == 1 for n in refs.values())
    before = {f.GetReference(): component(f) for f in board.GetFootprints()}
    poses = {f.GetReference(): (f.GetPosition().x, f.GetPosition().y)
             for f in board.GetFootprints()}
    # Keep only enclosure/access/antenna anchors. All ICs, decoupling,
    # oscillators, inductors, matching parts and test pads are free to move.
    fixed = {r for r in refs if r.startswith(('J', 'H', 'SW', 'AE'))}
    old_tracks = list(board.GetTracks())
    for item in old_tracks:
        board.Delete(item)
    old_zones = list(board.Zones())
    pours = [z for z in old_zones if not z.GetIsRuleArea()]
    for zone in pours:
        board.Delete(zone)
    movable = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        if ref in fixed:
            continue
        i = len(movable)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(150+20*(i % 15)),
                                      pcbnew.FromMM(25+20*(i // 15))))
        fp.SetLocked(False)
        movable.append(ref)
    board.BuildConnectivity()
    assert not list(board.GetTracks())
    assert all(z.GetIsRuleArea() for z in board.Zones())
    assert {f.GetReference(): component(f) for f in board.GetFootprints()} == before
    for fp in board.GetFootprints():
        if fp.GetReference() in fixed:
            assert (fp.GetPosition().x, fp.GetPosition().y) == poses[fp.GetReference()]
    edge = board.GetBoardEdgesBoundingBox()
    for fp in board.GetFootprints():
        if fp.GetReference() in movable:
            assert fp.GetPosition().x > edge.GetRight() + pcbnew.FromMM(10)
    pcbnew.SaveBoard(str(out/(name+'.kicad_pcb')), board)
    assert sha(source_board) == source_hash
    report = {
        'source': str(source_board), 'source_sha256': source_hash,
        'source_unchanged': True, 'live_board_modified': False,
        'footprints': len(refs), 'physical_pads': sum(len(x['pads']) for x in before.values()),
        'components_and_pad_nets_geometry_unchanged': True,
        'removed_tracks_and_vias': len(old_tracks), 'removed_copper_pours': len(pours),
        'remaining_tracks': 0, 'remaining_vias': 0, 'remaining_copper_pours': 0,
        'rule_areas': [z.GetZoneName() for z in board.Zones()],
        'fixed_references': sorted(fixed), 'movable_references': movable,
        'outline_mm': [edge.GetX()/1e6, edge.GetY()/1e6, edge.GetWidth()/1e6, edge.GetHeight()/1e6],
        'copper_layers': board.GetCopperLayerCount(),
        'files': {p.name: sha(p) for p in sorted(out.iterdir())
                  if p.suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_sch')},
        'manufacturing_ready': False,
    }
    (out.parent/'preparation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('files','movable_references','fixed_references')}, indent=2))
    print('Fixed:', len(fixed), 'Movable:', len(movable))


if __name__ == '__main__':
    main()
