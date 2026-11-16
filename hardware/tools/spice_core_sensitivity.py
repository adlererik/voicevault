#!/usr/bin/env python3
"""Run bounded passive core-output sensitivity; no regulator control-loop claim."""
from pathlib import Path
import argparse,itertools,json,re,subprocess
from spice_executable import ngspice
from spice_results import measurements_from_log
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=ROOT/'hardware/rev-b/spice/core-output-sensitivity.cir')
parser.add_argument('--out',type=Path,default=ROOT/'.lab-runs/hardware/standalone-b0/spice-core')
args=parser.parse_args()
source=args.source.read_text()
out=args.out;out.mkdir(parents=True,exist_ok=True)
results=[]
spice=ngspice()
version=subprocess.check_output([spice,'--version'],text=True)
assert 'ngspice-47' in version, 'Record and review a changed simulator version.'
(out/'version.txt').write_text(version)
for index,(inductance,capacitance,resistance) in enumerate(itertools.product([1.76e-6,2.2e-6,2.64e-6],[1.1e-6,1.76e-6,2.2e-6],[.05,.12,.199])):
    directory=out/str(index);directory.mkdir(exist_ok=True)
    text=source.replace('.param lval=2.2u cap=2.2u dcr=0.12 esr=0.02',f'.param lval={inductance} cap={capacitance} dcr={resistance} esr=0.02')
    (directory/'input.cir').write_text(text)
    process=subprocess.run([spice,'-b','input.cir'],cwd=directory,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
    (directory/'ngspice.log').write_text(process.stdout)
    values=measurements_from_log(process.stdout,['core_min','core_max'],process.returncode)
    results.append(dict(case=index,l_h=inductance,each_cap_f=capacitance,dcr_ohm=resistance,**values))
report={'status':'analysis completed','model':'Passive output network with an ideal averaged source; regulator control loop absent','claim':'27 sensitivity experiments, not electrical stability or hardware qualification','cases':results}
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'SPICE: {len(results)} cases, minimum core {min(x["core_min"] for x in results):.4f} V, maximum {max(x["core_max"] for x in results):.4f} V')
