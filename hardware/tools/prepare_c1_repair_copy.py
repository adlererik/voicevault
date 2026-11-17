#!/usr/bin/env python3
"""Create an isolated C1 repair copy; never overwrites an existing checkpoint."""
import argparse,hashlib,shutil
from pathlib import Path
from prepare_rev_c_retry import spans,fp_ref
from finalize_rev_c_quilter_input import parse,child,children
ROOT=Path(__file__).resolve().parents[2];NAME='voicevault-standalone-c1'
p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
src=ROOT/'.lab-runs/hardware/quilter/2026-11-17-c1-review/candidate-3/original-profile'
raw=ROOT/'.lab-runs/hardware/quilter/2026-11-17-c1-review/candidate-3/returned'/(NAME+'.kicad_pcb')
assert hashlib.sha256(raw.read_bytes()).hexdigest()=='9dd8b00cb72809a7b252615c985ae6f2feabc22705ff30dd6830d22630637d96'
a.output.mkdir(parents=True,exist_ok=False)
for f in src.iterdir():
 if f.is_file() and (f.suffix in ['.kicad_pcb','.kicad_pro','.kicad_sch','.kicad_dru'] or f.name in ['fp-lib-table','sym-lib-table']):shutil.copy2(f,a.output/f.name)
shutil.copytree(ROOT/'hardware/rev-c1/VoiceVault_B0.pretty',a.output/'VoiceVault_B0.pretty')
s=(a.output/(NAME+'.kicad_pcb')).read_text();original=s
for x,y in spans(s,'footprint'):
 frag=s[x:y]
 if fp_ref(parse(frag))!='AE201':continue
 assert child(parse(frag),'layer')[1]=='B.Cu'
 for u,v in spans(frag,'zone'):
  if child(parse(frag[u:v]),'name')[1]=='VV_ANTENNA_OTHER_LAYERS':
   z=frag[u:v];assert '"B.Cu"' in z;frag=frag[:u]+z.replace('"B.Cu"','"F.Cu"',1)+frag[v:];break
 s=s[:x]+frag+s[y:];break
assert s!=original
strip=lambda t:{fp_ref(f):[z for z in f if not(isinstance(z,list) and z and z[0]=='zone')] for f in children(parse(t),'footprint')}
assert strip(s)==strip(original)
(a.output/(NAME+'.kicad_pcb')).write_text(s)
print('Created isolated C1 repair copy, antenna opposite-side exclusion corrected. Native checks required.')
