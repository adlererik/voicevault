#!/usr/bin/env python3
"""Add layout intent to unplaced C0 without choosing any component pose or route.

Run in KiCad's Python. Regions are instructions for Quilter, not placements.
The antenna rule areas belong to its footprint and follow its final pose.
"""
from pathlib import Path
import hashlib
import json
import pcbnew

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT/'hardware/rev-c'
BOARD = DESIGN/'voicevault-standalone-c0.kicad_pcb'


def identity(board):
    return {f.GetReference(): (f.GetPosition().x, f.GetPosition().y, f.GetOrientationDegrees(),
        f.GetLayer(), f.IsLocked(), f.GetValue(),
        tuple(sorted((p.GetNumber(), p.GetNetname(), p.GetPosition().x, p.GetPosition().y,
                      p.GetSize().x, p.GetSize().y) for p in f.Pads())))
        for f in board.GetFootprints()}


def area(parent, name, polygons, *, tracks=False, vias=False, pours=False, footprints=False):
    zone = pcbnew.ZONE(parent)
    zone.SetZoneName(name)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowTracks(tracks)
    zone.SetDoNotAllowVias(vias)
    zone.SetDoNotAllowZoneFills(pours)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(footprints)
    outline = zone.Outline()
    for polygon in polygons:
        outline.NewOutline()
        for x, y in polygon:
            outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return zone


def rectangle(x1, y1, x2, y2):
    return [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    if (any(z.GetZoneName().startswith('VV_REGION_') for z in board.Zones()) or
        any(z.GetZoneName().startswith('VV_ANTENNA_') for f in board.GetFootprints() for z in f.Zones())):
        raise SystemExit('Already prepared. Preserve this board; use a fresh unplaced copy for changed regions. Replacing existing rule areas through the native Python bindings is disabled after a crash.')
    assert not list(board.GetTracks()), 'Never apply preparation over routed copper'
    assert all(z.GetIsRuleArea() for z in board.Zones()), 'Never alter a copper-poured board'
    parts = {f.GetReference(): f for f in board.GetFootprints()}
    assert 'U10' not in parts and 'J801' not in parts, 'Owner removed vibration'
    assert all(f.GetPosition().x > pcbnew.FromMM(100) and not f.IsLocked()
               for r,f in parts.items() if not r.startswith('H'))
    before = identity(board)
    for zone in list(board.Zones()):
        if zone.GetZoneName().startswith('VV_REGION_'):
            board.Remove(zone)
    antenna = parts['AE201']
    for zone in list(antenna.Zones()):
        if zone.GetZoneName().startswith('VV_ANTENNA_'):
            antenna.Remove(zone)
    px, py = pcbnew.ToMM(antenna.GetPosition().x), pcbnew.ToMM(antenna.GetPosition().y)
    polygons = [rectangle(px-3.25, py-3.25, px+3.25, py+3.25)]
    zone = area(antenna, 'VV_ANTENNA_NO_COPPER', polygons, vias=True, pours=True, footprints=True)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask(6));antenna.Add(zone)
    # A narrow opening reaches feed pad 1 from the ground-reference side.
    guard = [(-3.25,-3.25),(3.25,-3.25),(3.25,3.25),(-3.25,3.25),
             (-3.25,.45),(-.85,.45),(-.85,-.45),(-3.25,-.45)]
    zone = area(antenna, 'VV_ANTENNA_TRACK_GUARD', [[(px+x,py+y) for x,y in guard]],
                tracks=True, vias=True, pours=True)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask(6));antenna.Add(zone)
    # KiCad's library writer does not rebase footprint-zone coordinates.
    # Normalize the serialization frame temporarily, then restore the exact
    # inventory pose. This is not a component placement decision.
    origin = antenna.GetPosition()
    antenna.Move(pcbnew.VECTOR2I(-origin.x,-origin.y))
    plugin = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    plugin.FootprintSave(str(DESIGN/'VoiceVault_B0.pretty'), antenna)
    antenna.Move(origin)
    library = plugin.FootprintLoad(str(DESIGN/'VoiceVault_B0.pretty'), 'Johanson_2450AT18x100')
    assert all(abs(pcbnew.ToMM(z.GetPosition().x))<4 and abs(pcbnew.ToMM(z.GetPosition().y))<4
               for z in library.Zones()), 'Footprint keepout coordinates not rebased'

    manifest = json.loads((DESIGN/'circuits.json').read_text())
    pages = {p['name']: {c['ref'] for c in p['parts']} for p in manifest['pages']}
    ports = {'J501','J601','J401','J701','AE201'}
    groups = {
        'CHARGER': pages['charging'] | pages['power-entry'],
        'MAIN_SUPPLY': pages['regulation'],
        'SECURE_ELEMENT': pages['secure'],
        'RADIO': pages['radio'] | pages['radio-interface'] | {'U1202','R1205','R1207','R1210','R1211','C1207'},
        'AUDIO': pages['audio-codec'] | pages['audio-power'] | pages['headset'],
        'DISPLAY': pages['display'] | pages['backlight'],
        'CARD': pages['microsd'] | {'R1206','C1208'},
    }
    owned = set().union(*groups.values(),ports,pages['test-access'])
    groups['MCU'] = set(parts)-owned-{r for r in parts if r.startswith('H')}
    regions = []
    for name, refs in groups.items():
        refs = sorted((refs-ports) & set(parts))
        polygons = []
        for ref in refs:
            fp=parts[ref];x=pcbnew.ToMM(fp.GetPosition().x);y=pcbnew.ToMM(fp.GetPosition().y)
            polygons.append(rectangle(x-12,y-12,x+12,y+12))
        region = area(board,'VV_REGION_GROUP_'+name,polygons)
        region.SetLayer(pcbnew.F_Cu);board.Add(region)
        regions.append(dict(name=region.GetZoneName(),mode='offboard-free-location-group',refs=refs))
    edge_regions = {
        'ANTENNA_CORNERS': (['AE201'],[rectangle(25,25,34,34),rectangle(86,25,95,34),
                                     rectangle(25,61,34,70),rectangle(86,61,95,70)]),
        'USB_BOTTOM': (['J501'],[rectangle(30,55,90,70)]),
        'HEADSET_RIGHT': (['J601'],[rectangle(77,32,95,63)]),
        'CARD_LEFT': (['J401'],[rectangle(25,32,48,63)]),
        'DISPLAY_TOP': (['J701'],[rectangle(35,25,90,45)]),
    }
    for name,(refs,polygons) in edge_regions.items():
        zone = area(board,'VV_REGION_'+name,polygons)
        zone.SetLayer(pcbnew.F_Cu);board.Add(zone)
        regions.append(dict(name=zone.GetZoneName(),mode='onboard-top-side-placement-region',refs=refs,
                            polygons_mm=polygons))
    board.SetLayerName(pcbnew.In1_Cu,'GND_L2')
    board.SetLayerName(pcbnew.In4_Cu,'GND_L5')
    assert identity(board)==before, 'Preparing constraints changed a component pose, value, net or pad geometry'
    assert not list(board.GetTracks())
    pcbnew.SaveBoard(str(BOARD),board)
    rules='''(version 1)
(rule "VV antenna: only antenna feed in exclusion"
 (condition "A.intersectsArea('VV_ANTENNA_NO_COPPER') && A.NetName != 'BLE_ANT_FEED'")
 (constraint disallow track via micro_via buried_via zone))
(rule "VV antenna: front-layer feed only"
 (condition "A.intersectsArea('VV_ANTENNA_NO_COPPER') && A.Layer != 'F.Cu'")
 (constraint disallow track via micro_via buried_via zone))
'''
    BOARD.with_suffix('.kicad_dru').write_text(rules)
    report=dict(components_or_routes_placed=False,component_poses_and_pad_nets_unchanged=True,
                source_board_sha256=hashlib.sha256(BOARD.read_bytes()).hexdigest(),regions=regions,
                antenna_keepouts='Footprint-attached 6.5mm square, no pours/vias/other footprints; feed corridor and native net/layer restrictions',
                antenna_qualification='Provisional adaptation of Johanson evaluation layout; final RF/enclosure tuning remains required',
                cloud_region_associations='Must be verified and assigned in Quilter before launch',
                antenna_match_topology='C212 series 1.2pF; L202 shunt 2.7nH; L203 series 3.3nH (Johanson reference page 2)',
                stack='Signal / GND / signal / signal / GND / signal; provisional 1.0mm',
                manufacturing_ready=False)
    (DESIGN/'quilter-intent.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Prepared',len(regions),'Quilter regions and two footprint-attached antenna rule areas; no components placed or tracks routed.')


if __name__=='__main__':main()
