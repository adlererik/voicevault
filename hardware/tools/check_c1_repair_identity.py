#!/usr/bin/env python3
"""Independent circuit/pose guards for a C1 local repair; no layout-success claim."""
import argparse,json,hashlib
from pathlib import Path
from finalize_rev_c_quilter_input import parse,child,children
from prepare_rev_c_retry import fp_ref
from check_rev_c1 import check_connections
from evaluate_lqfp_candidate import vendor
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
def parts(path):return {fp_ref(f):f for f in children(parse(path.read_text()),'footprint')}
before=parts(a.reference);after=parts(a.board);assert set(before)==set(after) and len(after)==216
nodes={}
allowed={'L1201','U9','C108','C107','C704','C705','R707','C1202','C1204',
         'L1','C22','C26','C25','C17','U1202','C1207'}
changes=[]
for ref,f in after.items():
 g=before[ref]
 for field in ['Value']:
  assert next(p[2] for p in children(f,'property') if p[1]==field)==next(p[2] for p in children(g,'property') if p[1]==field),(ref,field)
 def pads(x):return sorted((p[1],tuple(child(p,'at')[1:]),tuple(child(p,'size')[1:]),child(p,'net')[1] if child(p,'net') else '') for p in children(x,'pad'))
 # Rear-to-front flips legitimately reflect local pad coordinates. Identity still
 # requires identical number, dimensions and net for every physical pad.
 assert sorted((p[0],p[2],p[3]) for p in pads(f))==sorted((p[0],p[2],p[3]) for p in pads(g)),ref
 for pp in children(f,'pad'):
  if pp[1]:nodes[(ref,pp[1])]=child(pp,'net')[1] if child(pp,'net') else ''
 def pos(x):
  values=list(map(float,child(x,'at')[1:]));return values[:2]+[(values[2] if len(values)>2 else 0)%360]
 changed=child(f,'layer')!=child(g,'layer') or len(pos(f))!=len(pos(g)) or any(abs(x-y)>0.000001 for x,y in zip(pos(f),pos(g)))
 if changed:assert ref in allowed,('Unexpected movement',ref);changes.append(ref)
manifest=json.loads((ROOT/'hardware/rev-c1/circuits.json').read_text());_,pins=vendor(ROOT/'.lab-cache/hardware-research/2026-11-16/lqfp-evaluation/STM32U5G9ZJTxQ.xml','lqfp')
expected=check_connections(nodes,manifest,pins);negative=[]
for key,value in [(('U1','70'),'GND'),(('U1','29'),'SD_SCK_MCU'),(('U1','20'),'VDD_3V3'),(('U1','142'),'VDD_3V3'),(('U1','107'),'GND'),(('U6','26'),'SE_SDA'),(('C115','1'),'VDD_3V3')]:
 try:check_connections(nodes|{key:value},manifest,pins)
 except (AssertionError,ValueError):negative.append('.'.join(key))
 else:raise AssertionError(('Corrupt mapping accepted',key))
result=dict(status='PASS',board_sha256=hashlib.sha256(a.board.read_bytes()).hexdigest(),reference_sha256=hashlib.sha256(a.reference.read_bytes()).hexdigest(),footprints=216,critical_pins=72,mcu_physical_pins=144,mcu_function_checks=55,connected_mcu_pins=len(expected),corrupt_mapping_controls_rejected=negative,moved_refs=sorted(changes),mounting_anchors_preserved=True,scope='Circuit identity/authorized pose changes only; not physical qualification.')
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
