#!/usr/bin/env python3
"""Propose five bounded local routes on a copy; native qualification is required.

The first checked run accepted MCU_LX only. This generator intentionally refuses
to rerun over any route in the target nets; preserve accepted work.
"""
import pcbnew,json
from pathlib import Path
r=Path(__file__).resolve().parents[2];b=pcbnew.LoadBoard(str(r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'))
paths={
'MCU_LX':(.30,[(58.4,51.4),(58.4,53.075),(57.925,53.55),(57.925,54.8)]),
'PMIC_VSET2':(.15,[(49.743,59.58),(49.743,60.326),(48.28,61.789)]),
'HAPTIC_REG':(.10,[(86,44.1),(86,43.8),(84.7,43.8),(83.265,45.235),(83.265,45.34)]),
'HAPTIC_PLUS':(.15,[(86.4,44.1),(86.4,43.8),(85.5,42.9),(84.9,42.9),(84.9,41.325)]),
'HAPTIC_MINUS':(.15,[(86.4,44.9),(87,44.9),(87,42.425),(85.9,41.325)])}
for net,(width,points) in paths.items():
 assert not any(t.GetNetname()==net for t in b.GetTracks()),'Preserve existing work'
 for p,q in zip(points,points[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(pcbnew.VECTOR2I(*[pcbnew.FromMM(x) for x in p]));t.SetEnd(pcbnew.VECTOR2I(*[pcbnew.FromMM(x) for x in q]));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(pcbnew.F_Cu);t.SetNetCode(b.FindNet(net).GetNetCode());b.Add(t)
pcbnew.SaveBoard(str(r/'.lab-cache/hardware/routing-b0/short-power.kicad_pcb'),b)
print('Candidate short local power/haptic paths; not applied.')
