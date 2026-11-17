#!/usr/bin/env python3
"""Remove only native-reported invalid/dangling copper in an isolated copy.

Every deletion and resulting open is recorded; never changes design rules.
"""
import argparse,collections,json
from pathlib import Path
from repair_rev_c_return import drc
from prepare_rev_c_retry import spans
from finalize_rev_c_quilter_input import parse,child
p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--passes',type=int,default=12);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
removed=[];history=[]
for iteration in range(a.passes):
 report=drc(a.board,a.out/f'drc-{iteration}.json',save=True)
 text=a.board.read_text();objects={}
 for kind in ['segment','arc','via']:
  for start,end in spans(text,kind):objects[child(parse(text[start:end]),'uuid')[1]]=(start,end,kind)
 history.append(dict(iteration=iteration,violations=dict(collections.Counter(v['type'] for v in report['violations'])),opens=len(report['unconnected_items'])))
 print(history[-1],flush=True);selected={}
 for v in report['violations']:
  if v['type'] not in ['shorting_items','clearance','hole_clearance','solder_mask_bridge','items_not_allowed','track_dangling','via_dangling']:continue
  candidates=[i for i in v['items'] if i['uuid'] in objects]
  candidates.sort(key=lambda i:objects[i['uuid']][2]!='via')
  if candidates:selected.setdefault(candidates[0]['uuid'],[]).append(v['type'])
 if not selected or iteration==a.passes-1:break
 for u in selected:
  start,end,kind=objects[u];removed.append(dict(uuid=u,kind=kind,reasons=sorted(set(selected[u])),sexpr=text[start:end]))
 for start,end,kind in sorted([objects[u] for u in selected],reverse=True):text=text[:start]+text[end:]
 a.board.write_text(text)
(a.out/'cleanup.json').write_text(json.dumps(dict(history=history,removed=removed),indent=2)+'\n')
