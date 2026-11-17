#!/usr/bin/env python3
"""Lossless text edits after safe native placement; logs every removed item."""
import argparse,json,re
from pathlib import Path
from prepare_rev_c_retry import spans,fp_ref
from finalize_rev_c_quilter_input import parse,child,children
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--rip-nets',default='REG_L1,REG_L2,MCU_LX,BL_SW,BL_FB,BL_ANODE');a=p.parse_args()
s=a.input.read_text();dedicated=set(a.rip_nets.split(','));edits=[];removed=[]
for kind in ['segment','via','arc']:
 for start,end in spans(s,kind):
  z=parse(s[start:end]);net=child(z,'net')
  if net and net[1] in dedicated:edits.append((start,end,''));removed.append(s[start:end])
for start,end in spans(s,'footprint'):
 frag=s[start:end];f=parse(frag);side=child(f,'layer')[1];changes=[]
 for x,y in spans(frag,'property'):
  prop=parse(frag[x:y])
  if prop[1]=='Reference':
   new=re.sub(r'\(layer\s+"[^"]+"\)', '(layer "'+('F.Fab' if side=='F.Cu' else 'B.Fab')+'")',frag[x:y],count=1);changes.append((x,y,new))
 for x,y,new in reversed(changes):frag=frag[:x]+new+frag[y:]
 edits.append((start,end,frag))
for start,end in spans(s,'gr_text'):
 frag=s[start:end]
 if child(parse(frag),'layer')[1] in ['F.SilkS','B.SilkS']:edits.append((start,end,re.sub(r'\(layer\s+"[^"]+"\)', '(layer "Dwgs.User")',frag,count=1)))
for start,end,new in sorted(edits,reverse=True):s=s[:start]+new+s[end:]
a.output.write_text(s);a.output.with_suffix('.ripup.json').write_text(json.dumps(dict(removed_switching_copper=removed),indent=2)+'\n');print('Removed obsolete switching copper:',len(removed))
