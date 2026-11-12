#!/usr/bin/env python3
"""Create the first bounded RF routing candidate with KiCad's native board API.

Run using KiCad's bundled Python. This does not replace the board or manufacture
anything. Inspect the candidate with native DRC before accepting it. Dimensions
are provisional: antenna tuning and controlled impedance need an accepted stack.
"""
import hashlib
import json
from pathlib import Path
import shutil

import pcbnew

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
NAME = 'voicevault-standalone-b0'
SOURCE = DESIGN / (NAME + '.kicad_pcb')
OUT = ROOT / '.lab-cache/hardware/routing-b0/rf'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    board = pcbnew.LoadBoard(str(SOURCE))
    assert not list(board.GetTracks()), 'RF stage is a one-time operation; preserve existing copper.'
    assert len(list(board.Zones())) == 1, 'Preserve the tested antenna reservation.'
    signature = lambda: sorted((fp.GetReference(), p.GetNumber(), p.GetNetname())
                               for fp in board.GetFootprints() for p in fp.Pads())
    before = signature()
    footprints = {f.GetReference(): f for f in board.GetFootprints()}
    # Free the antenna matching corridor. The button remains accessible on the
    # rear of the serviceable prototype; no through-board anchors are added.
    poses = {
        'SW503': (63, 29, 0, True),
        'X201': (38.4, 35.7, 0, False),
        'R202': (30.3, 37.5, 0, False),
        'C209': (44.5, 31.12, 0, False),
        'C201': (34.6, 36.4, 90, False),
        'C202': (35.6, 36.4, 90, False),
        'C203': (39.6, 33.05, 90, False),
        'L201': (38.2, 33.8, 180, False),
        'L202': (36.3, 33.8, 180, False),
        'C212': (34.7, 34.5, 270, False),
        'L203': (32.7, 33.8, 180, False),
    }
    for ref, (x, y, angle, back) in poses.items():
        fp = footprints[ref]
        if (fp.GetLayer() == pcbnew.B_Cu) != back:
            # Footprints are already attached; detached Flip crashes KiCad.
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(angle)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
        fp.Value().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)

    def pad(ref, number):
        matches = [p for p in footprints[ref].Pads() if p.GetNumber() == number]
        assert len(matches) == 1
        return matches[0]

    def xy(p):
        return (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)

    segments = []

    def route(net, points, width=.15):
        code = board.FindNet(net).GetNetCode()
        for start, end in zip(points, points[1:]):
            if start == end:
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in start]))
            track.SetEnd(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in end]))
            track.SetWidth(pcbnew.FromMM(width))
            track.SetLayer(pcbnew.F_Cu)
            track.SetNetCode(code)
            board.Add(track)
            segments.append(dict(net=net, start_mm=start, end_mm=end, width_mm=width))

    route('RAD_ANT', [xy(pad('U6', 'D1')), (40.03, 33.8), xy(pad('L201', '1'))], .10)
    route('RAD_ANT', [(40.03, 33.8), xy(pad('C203', '1'))], .10)
    route('RAD_RF_50', [xy(pad('L201', '2')), xy(pad('L202', '1'))])
    route('RAD_MATCH', [xy(pad('L202', '2')), (34.7, 33.8), xy(pad('L203', '1'))])
    route('RAD_MATCH', [(34.7, 33.8), xy(pad('C212', '1'))])
    route('BLE_ANT_FEED', [xy(pad('L203', '2')), (30.45, 33.8),
                           (29.45, 32.8), xy(pad('AE201', '1'))])
    route('GND', [xy(pad('U6', 'E3')), xy(pad('U6', 'D2'))], .10)
    route('GND', [xy(pad('U6', 'F5')), xy(pad('U6', 'C5'))], .10)
    # Direct ground attachment for the radio's small WLCSP ground lands;
    # reflow/paste design remains a separate assembly-review requirement.
    for p in footprints['U6'].Pads():
        if p.GetNetname() == 'GND':
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    # Conventional through vias, outside the all-layer antenna reservation.
    # These will join the reference planes in the next routing stage.
    for ref, pos in [('C203', (39.2, 32.73)), ('C212', (34.1, 35.4))]:
        route('GND', [xy(pad(ref, '2')), pos])
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in pos]))
        via.SetWidth(pcbnew.FromMM(.50))
        via.SetDrill(pcbnew.FromMM(.30))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNetCode(board.FindNet('GND').GetNetCode())
        board.Add(via)

    # Ground/reference copper is explicitly cut back from the antenna area,
    # rather than relying on an overlapping polygon and implicit clipping.
    outline = [(25.3,32.2),(39.2,32.2),(39.2,25.3),
               (94.7,25.3),(94.7,69.7),(25.3,69.7)]
    for layer_name in ['F.Cu', 'In1.Cu', 'In4.Cu', 'B.Cu']:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(board.GetLayerID(layer_name))
        zone.SetNetCode(board.FindNet('GND').GetNetCode())
        zone.SetZoneName('GND_REFERENCE_' + layer_name)
        zone.SetLocalClearance(pcbnew.FromMM(.15))
        zone.SetMinThickness(pcbnew.FromMM(.10))
        zone.SetThermalReliefGap(pcbnew.FromMM(.15))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(.15))
        zone.Outline().NewOutline()
        for x, y in outline:
            zone.Outline().Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        board.Add(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    assert signature() == before, 'Routing altered a pad/net assignment.'
    board.BuildConnectivity()
    board.GetConnectivity().RecalculateRatsnest()
    target = OUT / SOURCE.name
    pcbnew.SaveBoard(str(target), board)
    for suffix in ['.kicad_pro', '.kicad_dru']:
        shutil.copy2(DESIGN / (NAME + suffix), OUT / (NAME + suffix))
    table = (DESIGN / 'fp-lib-table').read_text().replace('${KIPRJMOD}', str(DESIGN))
    (OUT / 'fp-lib-table').write_text(table)
    (OUT / 'routing.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        stage='RF local routing and GND reference candidate', placements=poses, segments=segments,
        tracks_and_vias=len(list(board.GetTracks())),
        unrouted_connections=board.GetConnectivity().GetUnconnectedCount(False),
        manufacturing_ready=False,
        limitations=['Provisional track widths; RF impedance and tuning not qualified',
                     'Planes and return paths require further via stitching and review']), indent=2)+'\n')
    print(f'Wrote RF candidate: {len(segments)} tracks, 2 vias; '
          f'{board.GetConnectivity().GetUnconnectedCount(False)} remaining connections.')


if __name__ == '__main__':
    main()
