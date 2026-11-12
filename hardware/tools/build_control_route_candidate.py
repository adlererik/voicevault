#!/usr/bin/env python3
"""Turn hash-bound local-route proposals into a disposable native board copy."""
import argparse
import hashlib
import json
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();plan=json.loads(args.plan.read_text())
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==plan['source_sha256'],'Stale proposal'
    assert args.output.resolve()!=SOURCE.resolve(),'Live board is never a proposal target'
    b=pcbnew.LoadBoard(str(SOURCE))
    for via in plan.get('vias',[]):
        net=b.FindNet(via['net']);assert net and net.GetNetname()
        v=pcbnew.PCB_VIA(b);v.SetPosition(pcbnew.VECTOR2I(*[pcbnew.FromMM(via[k]) for k in ['x','y']]))
        v.SetWidth(pcbnew.FromMM(via['w']));v.SetDrill(pcbnew.FromMM(via['drill']))
        if via.get('microvia'):
            v.SetViaType(pcbnew.VIATYPE_MICROVIA)
            v.SetLayerPair(b.GetLayerID(via['layers'][0]),b.GetLayerID(via['layers'][-1]))
        else:
            v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
        # Retain ordinary capture lands on all layers. Besides conservative
        # fabrication geometry this avoids stale unused-pad caches during fill.
        v.SetRemoveUnconnected(False);v.SetNetCode(net.GetNetCode());b.Add(v)
    for route in plan['routes']:
        net=b.FindNet(route['net']);assert net and net.GetNetname()
        for a,z in zip(route['points'],route['points'][1:]):
            t=pcbnew.PCB_TRACK(b);t.SetNetCode(net.GetNetCode());t.SetLayer(b.GetLayerID(route['layer']))
            t.SetWidth(pcbnew.FromMM(route['width_mm']))
            t.SetStart(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in a]))
            t.SetEnd(pcbnew.VECTOR2I(*[pcbnew.FromMM(v) for v in z]));b.Add(t)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    pcbnew.SaveBoard(str(args.output),b)
    print(f'Wrote {len(plan["routes"])} proposed connections to disposable native copy')

if __name__=='__main__':main()
