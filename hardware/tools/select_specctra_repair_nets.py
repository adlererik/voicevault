#!/usr/bin/env python3
"""Route native-reported opens only; preserve every other net in DSN classes."""
import argparse,json,re
from pathlib import Path
from finalize_rev_c_quilter_input import parse
p=argparse.ArgumentParser();p.add_argument('dsn',type=Path);p.add_argument('drc',type=Path);a=p.parse_args()
s=a.dsn.read_text();d=json.loads(a.drc.read_text());active={re.search(r'\[([^]]+)\]',v['items'][0]['description'])[1] for v in d['unconnected_items']};active.discard('GND')
start=s.index('(class kicad_default');depth=0;end=None
for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',s[start:]):
 if m[0]=='(':depth+=1
 elif m[0]==')':
  depth-=1
  if depth==0:end=start+m.end();break
assert end;node=parse(s[start:end]);all_nets={x for x in node[2:] if isinstance(x,str)};assert active<=all_nets
via=re.search(r'\(use_via\s+([^\s)]+)',s)[1]
switch=active&{'REG_L1','REG_L2','BL_SW'}
def cls(name,nets,width):return f'(class {name} '+ ' '.join(json.dumps(n) for n in sorted(nets))+f' (circuit (use_via {via})) (rule (width {width}) (clearance 100)))\n'
replacement=cls('VV_PRESERVE',all_nets-active,150)+cls('VV_REPAIR',active-switch,150)
if switch:replacement+=cls('VV_SWITCHING',switch,400)
a.dsn.write_text(s[:start]+replacement+s[end:]);a.dsn.with_suffix('.selection.json').write_text(json.dumps(dict(active_nets=sorted(active),switching_nets=sorted(switch),ignored_class='VV_PRESERVE'),indent=2)+'\n');print('Native-selected nets',sorted(active))
