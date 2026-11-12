#!/usr/bin/env python3
"""Add the explicit all-layer antenna reservation; run in KiCad's Python."""
from pathlib import Path
import shutil
import pcbnew

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
BOARD = DESIGN / 'voicevault-standalone-b0.kicad_pcb'
board = pcbnew.LoadBoard(str(BOARD))
name = 'BLE_ANTENNA_CLEARANCE'
if any(z.GetZoneName() == name for z in board.Zones()):
    raise SystemExit('Area already exists; preserve current design.')
backup=ROOT/'.lab-cache/hardware/antenna-rule-backup'
backup.mkdir(parents=True,exist_ok=True)
shutil.copyfile(BOARD,backup/BOARD.name)
zone=pcbnew.ZONE(board)
zone.SetZoneName(name)
zone.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
zone.SetIsRuleArea(True)
zone.SetDoNotAllowVias(True)
zone.SetDoNotAllowZoneFills(True)
zone.SetDoNotAllowTracks(False)  # Only the feed is excepted by the .kicad_dru rule.
zone.SetDoNotAllowPads(False)
zone.SetDoNotAllowFootprints(False)
outline=zone.Outline();outline.NewOutline()
for x,y in [(25,25),(38.9,25),(38.9,31.9),(25,31.9)]:
    outline.Append(pcbnew.FromMM(x),pcbnew.FromMM(y))
board.Add(zone)
antenna=next(f for f in board.GetFootprints() if f.GetReference()=='AE201')
feed=next(p.GetNetname() for p in antenna.Pads() if p.GetNumber()=='1')
assert feed=='BLE_ANT_FEED', 'Review changed antenna net before emitting the exception.'
pcbnew.SaveBoard(str(BOARD),board)
(BOARD.with_suffix('.kicad_dru')).write_text('''(version 1)
# Provisional manufacturer-inspired antenna reservation, not RF tuning evidence.
# Explicit rules are tested by negative control, independent of implicit keepouts.
(rule "BLE antenna: only RF feed tracks"
  (condition "A.intersectsArea('BLE_ANTENNA_CLEARANCE') && A.NetName != 'BLE_ANT_FEED'")
  (constraint disallow track via micro_via buried_via zone))
(rule "BLE antenna: no vias or copper fills"
  (condition "A.intersectsArea('BLE_ANTENNA_CLEARANCE') && A.NetName == 'BLE_ANT_FEED'")
  (constraint disallow via micro_via buried_via zone))
''')
print('Saved antenna rule area and explicit feed-only track restriction.')
