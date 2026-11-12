#!/usr/bin/env python3
"""Import only new copper from a routing study and qualify it with native DRC.

Run with KiCad's bundled Python. The live board is never written. Footprints,
pad nets, rule areas, planes and pre-existing tracks come from the live source,
not the router's rewritten file. Entire new net groups implicated by DRC are
rejected. The resulting candidate still requires separate acceptance/review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pcbnew
from check_hdi_geometry import audit as audit_laser_geometry

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
NAME = 'voicevault-standalone-b0'
SOURCE = DESIGN / (NAME + '.kicad_pcb')


def signature(board):
    return sorted((f.GetReference(), p.GetNumber(), p.GetNetname(),
                   p.GetPosition().x, p.GetPosition().y, p.GetLayerSet().FmtBin())
                  for f in board.GetFootprints() for p in f.Pads())


def geometry(board, item):
    if isinstance(item, pcbnew.PCB_VIA):
        return ('via', item.GetNetname(), item.GetPosition().x, item.GetPosition().y,
                item.GetWidth(item.TopLayer()), item.GetDrillValue(), int(item.GetViaType()),
                board.GetLayerName(item.TopLayer()), board.GetLayerName(item.BottomLayer()))
    ends = sorted([(item.GetStart().x, item.GetStart().y),
                   (item.GetEnd().x, item.GetEnd().y)])
    return ('track', item.GetNetname(), board.GetLayerName(item.GetLayer()),
            item.GetWidth(), *ends)


def laser_geometry(board):
    layers=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
    tracks=[]
    for item in board.GetTracks():
        if isinstance(item,pcbnew.PCB_VIA):
            start,end=sorted([layers.index(board.GetLayerName(item.TopLayer())),layers.index(board.GetLayerName(item.BottomLayer()))])
            tracks.append(dict(kind='via',microvia=item.GetViaType()==pcbnew.VIATYPE_MICROVIA,
                net=item.GetNetname(),x=item.GetPosition().x/1e6,y=item.GetPosition().y/1e6,
                w=item.GetWidth(item.TopLayer())/1e6,drill=item.GetDrillValue()/1e6,layers=layers[start:end+1]))
        else:
            tracks.append(dict(kind='track',net=item.GetNetname(),w=item.GetWidth()/1e6,
                start=[item.GetStart().x/1e6,item.GetStart().y/1e6],end=[item.GetEnd().x/1e6,item.GetEnd().y/1e6],
                layers=[board.GetLayerName(item.GetLayer())]))
    return audit_laser_geometry(dict(tracks=tracks))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--allowed-nets', type=Path, help='JSON list of permitted digital/control net names')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / SOURCE.name
    board = pcbnew.LoadBoard(str(SOURCE))
    candidate = pcbnew.LoadBoard(str(args.candidate))
    original_pads = signature(board)
    fixed = {geometry(board, item) for item in board.GetTracks()}
    fixed_ids = {item.m_Uuid.AsString() for item in board.GetTracks()}
    allowed = set(json.loads(args.allowed_nets.read_text())) if args.allowed_nets else None
    new = []
    seen = set(fixed)
    for item in candidate.GetTracks():
        key = geometry(candidate, item)
        if allowed is not None and item.GetNetname() not in allowed:
            continue
        if key in seen:
            continue
        seen.add(key)
        net = board.FindNet(item.GetNetname())
        assert net is not None and net.GetNetname(), 'Unknown candidate net'
        assert item.m_Uuid.AsString() not in fixed_ids, 'Router changed fixed copper'
        if isinstance(item, pcbnew.PCB_VIA):
            added = pcbnew.PCB_VIA(board)
            added.SetPosition(item.GetPosition())
            added.SetWidth(item.GetWidth(item.TopLayer()))
            added.SetDrill(item.GetDrillValue())
            added.SetViaType(item.GetViaType())
            added.SetLayerPair(board.GetLayerID(candidate.GetLayerName(item.TopLayer())),
                               board.GetLayerID(candidate.GetLayerName(item.BottomLayer())))
            added.SetRemoveUnconnected(item.GetRemoveUnconnected())
        else:
            assert type(item) == pcbnew.PCB_TRACK, 'Unsupported proposed copper type'
            added = pcbnew.PCB_TRACK(board)
            added.SetStart(item.GetStart())
            added.SetEnd(item.GetEnd())
            added.SetWidth(item.GetWidth())
            added.SetLayer(board.GetLayerID(candidate.GetLayerName(item.GetLayer())))
        added.SetNetCode(net.GetNetCode())
        board.Add(added)
        new.append(added)
    assert new, 'The study produced no new copper to qualify.'
    initial_nets = sorted({item.GetNetname() for item in new})
    for suffix in ['.kicad_pro', '.kicad_dru']:
        shutil.copy2(DESIGN / (NAME + suffix), args.output_dir / (NAME + suffix))
    (args.output_dir / 'fp-lib-table').write_text(
        (DESIGN / 'fp-lib-table').read_text().replace('${KIPRJMOD}', str(DESIGN)))
    rounds = []
    for attempt in range(len(initial_nets) + 1):
        board.BuildConnectivity()
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        board.GetConnectivity().RecalculateRatsnest()
        pcbnew.SaveBoard(str(target), board)
        report_path = args.output_dir / 'drc.json'
        cli = (['kicad-cli'] if shutil.which('kicad-cli') else
               ['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad'])
        result = subprocess.run(cli + ['pcb', 'drc', '--format', 'json', '--output',
            str(report_path), str(target)], capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        drc = json.loads(report_path.read_text())
        shutil.copy2(report_path, args.output_dir / f'drc-attempt-{attempt:02}.json')
        violations = drc.get('violations', [])
        if not violations:
            break
        by_id = {item.m_Uuid.AsString(): item.GetNetname() for item in new}
        rejected = {by_id[i['uuid']] for v in violations for i in v['items']
                    if i.get('uuid') in by_id}
        # A new route can starve an old ground thermal without being named in
        # the two-item violation. Reject nearby new routes conservatively.
        for violation in violations:
            if any(i.get('uuid') in by_id for i in violation['items']):
                continue
            for detail in violation['items']:
                pos = detail.get('pos')
                if not pos or detail.get('description', '').startswith('Zone '):
                    continue
                point = pcbnew.VECTOR2I(pcbnew.FromMM(pos['x']), pcbnew.FromMM(pos['y']))
                for item in new:
                    box = item.GetBoundingBox()
                    box.Inflate(pcbnew.FromMM(.8))
                    if box.Contains(point):
                        rejected.add(item.GetNetname())
        assert rejected, 'DRC failure cannot be attributed safely; candidate rejected.'
        rounds.append(dict(attempt=attempt, violations=len(violations), rejected_nets=sorted(rejected)))
        for item in list(new):
            if item.GetNetname() in rejected:
                new.remove(item)
                board.Remove(item)
    else:
        raise RuntimeError('Candidate did not converge to clean layout DRC')
    assert signature(board) == original_pads, 'Pad positions or net assignments changed'
    assert fixed <= {geometry(board, item) for item in board.GetTracks()}, 'Fixed copper changed'
    laser=laser_geometry(board)
    (args.output_dir/'laser-geometry.json').write_text(json.dumps(laser,indent=2)+'\n')
    assert not laser['violations'],'Supplemental laser-hole geometry failed; candidate rejected'
    summary = dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        study_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
        candidate_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        offered_net_groups=initial_nets, rejected_rounds=rounds,
        accepted_net_groups=sorted({item.GetNetname() for item in new}),
        added_copper_items=len(new), total_copper_items=len(list(board.GetTracks())),
        unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),
        native_layout_violations=0, laser_geometry_violations=0, laser_vias=laser['laser_vias'], manufacturing_ready=False,
        scope='Native copper/connectivity only; signal integrity, power, RF and manufacturing remain unqualified')
    (args.output_dir / 'qualification.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
