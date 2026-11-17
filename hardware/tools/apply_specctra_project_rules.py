#!/usr/bin/env python3
"""Bind an isolated DSN to the checked project's real default class.

KiCad's scripting LoadBoard/DSN exporter does not load the project's netclass.
Fail closed on unexpected defaults; never changes the PCB or native rules.
"""
import argparse,json,re,hashlib
from pathlib import Path
def apply_rules(dsn,project_path):
 s=dsn.read_text();before=hashlib.sha256(s.encode()).hexdigest();pro=json.loads(project_path.read_text());c=next(c for c in pro['net_settings']['classes'] if c['name']=='Default')
 assert c['clearance']==.1 and c['track_width']==.15 and c['via_diameter']==.45 and c['via_drill']==.2,c
 project=json.loads(project_path.read_text())
 rules=project['board']['design_settings']['rules']
 assert rules['min_clearance']<=.1 and rules['min_track_width']<=.15
 assert rules['min_hole_clearance']==.2
 assert s.count('(clearance 200)')==2 and s.count('(width 200)')==2
 s=s.replace('(clearance 200)','(clearance 100)').replace('(width 200)','(width 150)').replace('(clearance 50 (type smd_smd))','(clearance 100 (type smd_smd))')
 start=s.index('(padstack "Via[0-5]_600:300_um"');end=s.index('(padstack ',start+10);frag=s[start:end];assert frag.count(' 600)')==6
 frag=frag.replace(' 600)',' 450)');s=s[:start]+frag+s[end:];s=s.replace('Via[0-5]_600:300_um','Via[0-5]_450:200_um')
 assert '(clearance 200)' not in s and '600:300' not in s
 dsn.write_text(s);dsn.with_suffix('.rules.json').write_text(json.dumps(dict(project_sha256=hashlib.sha256(project_path.read_bytes()).hexdigest(),before_sha256=before,after_sha256=hashlib.sha256(s.encode()).hexdigest(),default_class=c,export_smd_clearance_mm=.1),indent=2)+'\n');print('DSN now matches source project: clearance .10, track .15, via .45/.20 mm.')

def main():
 p=argparse.ArgumentParser();p.add_argument('dsn',type=Path);p.add_argument('--project',required=True,type=Path);a=p.parse_args()
 apply_rules(a.dsn,a.project)

if __name__=="__main__":main()
