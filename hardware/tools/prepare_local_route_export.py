#!/usr/bin/env python3
"""Remove nonblocking placement hints ONLY from a disposable DSN export copy."""
import argparse
from pathlib import Path
from prepare_rev_c_retry import spans
from finalize_rev_c_quilter_input import parse,child
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--omit-ground-pours',action='store_true');a=p.parse_args()
s=a.source.read_text();drop=[]
for start,end in spans(s,'zone'):
 z=parse(s[start:end]);n=child(z,'name')
 if n and n[1].startswith('VV_REGION_'):
  assert all(c[1]=='allowed' for c in child(z,'keepout')[1:]);drop.append((start,end))
 elif a.omit_ground_pours and not child(z,'keepout'):
  assert child(z,'net')[1]=='GND','Only ground pours may be omitted from export'
  drop.append((start,end))
for start,end in reversed(drop):s=s[:start]+s[end:]
a.output.write_text(s);print('Export-only omitted placement hints:',len(drop))
