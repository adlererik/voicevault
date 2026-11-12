#!/usr/bin/env python3
"""Propose the reviewed Molex socket on a copy, preserving existing copper."""
from pathlib import Path
import pcbnew,hashlib,json,shutil,sys
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'hardware/tools'));from qualify_routing_candidate import geometry,signature,laser_geometry
src=r/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb';d=r/'.lab-cache/hardware/routing-b0/microsd-replacement';d.mkdir(parents=True,exist_ok=True);b=pcbnew.LoadBoard(str(src));old=next(f for f in b.GetFootprints() if f.GetReference()=='J401');assert old.GetValue()=='DM3AT-SF-PEJM5'
expected={p.GetNumber():p.GetNetname() for p in old.Pads()};all_other=sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetLayerSet().FmtBin()) for f in b.GetFootprints() if f.GetReference()!='J401' for p in f.Pads());fixed={geometry(b,t) for t in b.GetTracks()}
f=pcbnew.FootprintLoad('/app/extensions/Library/footprints/Connector_Card.pretty','microSD_HC_Molex_104031-0811');assert f is not None
f.SetUuid(old.m_Uuid);f.SetPath(old.GetPath());f.SetReference('J401');f.SetValue('1040310811');f.SetFPID(pcbnew.LIB_ID('VoiceVault_B0','microSD_HC_Molex_104031-0811'));b.Remove(old);b.Add(f)
f.SetOrientationDegrees(270);f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(87.9),pcbnew.FromMM(58)))
f.Reference().SetLayer(pcbnew.F_Fab);f.Value().SetVisible(False)
assert set(p.GetNumber() for p in f.Pads())==set(expected)
for p in f.Pads():p.SetNetCode(b.FindNet(expected[p.GetNumber()]).GetNetCode())
assert all_other==sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetLayerSet().FmtBin()) for f in b.GetFootprints() if f.GetReference()!='J401' for p in f.Pads())
assert fixed=={geometry(b,t) for t in b.GetTracks()}
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest();pcbnew.SaveBoard(str(d/src.name),b)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),d/src.with_suffix(ext).name)
(d/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
meta=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((d/src.name).read_bytes()).hexdigest(),replacement='Molex1040310811 / JLC C585350 candidate',reference='J401',position_mm=[87.9,58],rotation_degrees=270,opens_towards='right/east PCB edge',card_opening_x_mm=93.6,closest_nominal_copper_to_right_edge_mm=1.1,all_other_pads_and_copper_preserved=True,logical_pin_nets=expected,unrouted_connections=b.GetConnectivity().GetUnconnectedCount(False),copper_items=len(list(b.GetTracks())),laser_geometry=laser_geometry(b),manufacturing_ready=False)
(d/'proposal.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
