#!/usr/bin/env python3
"""Automatically attempt remaining C1 nets, accepting only native-checked gains.

Runs a bounded external router on copies. Does not choose trace coordinates.
Preserves every component pose/value/pad net and the original design rules.
"""
import argparse,collections,json,os,re,shutil,subprocess
from pathlib import Path
from repair_rev_c_return import drc
from finalize_rev_c_quilter_input import parse,child,children
from prepare_rev_c_retry import fp_ref
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--geometry',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds-per-net',type=int,default=75);a=p.parse_args();a.board=a.board.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
assert '.lab-runs' in a.board.parts,'Only isolated run copies are supported'
base=drc(a.board,a.out/'initial-drc.json',save=True)
def counts(d):return dict(collections.Counter(v['type'] for v in d['violations']))
def hard(d):return [v for v in d['violations'] if v['type'] not in ['track_dangling','via_dangling']]
assert not hard(base),counts(base)
def signature(path):
 result=[]
 for f in children(parse(path.read_text()),'footprint'):
  at=list(map(float,child(f,'at')[1:]));at=(round(at[0],5),round(at[1],5),round((at[2] if len(at)>2 else 0)%360,5))
  pads=sorted((q[1],tuple(map(float,child(q,'size')[1:])),child(q,'net')[1] if child(q,'net') else '') for q in children(f,'pad'))
  result.append((fp_ref(f),next(q[2] for q in children(f,'property') if q[1]=='Value'),child(f,'layer')[1],at,pads))
 return sorted(result)
identity=signature(a.board)
g=json.loads(a.geometry.read_text());by_net=collections.defaultdict(list)
for q in g['pads']:
 if q['net']:by_net[q['net']].append((q['x'],q['y']))
for q in g['tracks']:
 if q['kind']=='via':by_net[q['net']].append((q['x'],q['y']))
 else:by_net[q['net']].extend([q['start'],q['end']])
net_counts=collections.Counter(re.search(r'\[([^]]+)\]',v['items'][0]['description'])[1] for v in base['unconnected_items'])
# Multi-drop supply rails require a separate plane/port completion strategy.
skip={'GND','VDD_3V3','VSYS','MCU_VDD11'}
nets=sorted(set(net_counts)-skip,key=lambda n:(max(x[0] for x in by_net[n])-min(x[0] for x in by_net[n])+max(x[1] for x in by_net[n])-min(x[1] for x in by_net[n]),n))
results=[];env=os.environ.copy();env['PYTHONUNBUFFERED']='1';env['PATH']=str(a.board.parent/'bin')+os.pathsep+env['PATH']
for index,net in enumerate(nets):
 step=a.out/f'{index:02d}-{net}';step.mkdir();src=step/'input';dst=step/'output';src.mkdir();dst.mkdir()
 for directory in [src,dst]:
  for suffix in ['.kicad_pro','.kicad_dru']:shutil.copy2(a.board.with_suffix(suffix),directory/(a.board.stem+suffix))
  shutil.copy2(a.board.parent/'fp-lib-table',directory/'fp-lib-table')
  (directory/'VoiceVault_B0.pretty').symlink_to(a.board.parent/'VoiceVault_B0.pretty',target_is_directory=True)
 source=src/a.board.name;candidate=dst/a.board.name;shutil.copy2(a.board,source)
 points=by_net[net];box=[max(.5,min(q[0] for q in points)-28),max(.5,min(q[1] for q in points)-28),min(69.5,max(q[0] for q in points)-22),min(44.5,max(q[1] for q in points)-22)]
 region=','.join(f'{v:.6f}' for v in box)
 cmd=['systemd-run','--user','--scope','-p','MemoryMax=800M','-p','MemorySwapMax=16M','-p','CPUQuota=100%','timeout','--signal=TERM','--kill-after=5s',str(a.seconds_per_net)+'s',str(ROOT/'.lab-cache/hardware/routing-venv/bin/kicad-tools'),'route-auto',str(source),'--net',net,'--region',region,'--no-repair','--no-via-resolution','--via-drill','0.2','--via-diameter','0.45','--format','json','--allow-partial','-o',str(candidate)]
 print('Attempting',net,'native opens before',len(base['unconnected_items']),flush=True)
 with (step/'router.log').open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=a.seconds_per_net+25)
 item=dict(net=net,router_exit=r.returncode,accepted=False)
 if candidate.exists():
  try:
   assert signature(candidate)==identity,'Component identity/pose changed'
   report=drc(candidate,step/'native-drc.json',save=True)
   item.update(native_opens=len(report['unconnected_items']),native_violations=counts(report))
   if not hard(report) and len(report['unconnected_items'])<len(base['unconnected_items']):
    shutil.copy2(candidate,a.board);base=report;item['accepted']=True
  except Exception as exc:item['rejection']=str(exc)[:300]
 results.append(item);print(item,flush=True)
 (a.out/'report.json').write_text(json.dumps(dict(results=results,remaining_native_opens=len(base['unconnected_items']),native_violations=counts(base)),indent=2)+'\n')
print('Native-checked remaining connections:',len(base['unconnected_items']),flush=True)
