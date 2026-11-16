#!/usr/bin/env python3
"""Isolated local repair: restore RF layer intent and rip up invalid copper.

Removed copper creates opens that MUST be rerouted and checked before acceptance.
Never modifies the raw cloud return, electrical components or live editor.
"""
import collections
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from finalize_rev_c_quilter_input import parse, child, children
from prepare_rev_c_retry import spans, fp_ref

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.lab-runs/hardware/quilter/2026-11-16-local-repair-02'
SOURCE=ROOT/'.lab-runs/hardware/quilter/2026-11-16-c0-retry-review/candidate-4/returned/voicevault-standalone-c0.kicad_pcb'
DESIGN=ROOT/'hardware/rev-c/quilter-retry-01'
NAME='voicevault-standalone-c0'
CLI=['flatpak','run','--user',f'--env=KICAD_CONFIG_HOME={ROOT}/.lab-cache/kicad-revc-checks','--command=kicad-cli','org.kicad.KiCad']

def inventory(text):
    return {fp_ref(f):[x for x in f if not (isinstance(x,list) and x and x[0]=='zone')]
            for f in children(parse(text),'footprint')}

def drc(board,out,save=False):
    cmd=CLI+['pcb','drc','--refill-zones','--format','json','--output',str(out)]
    if save:cmd+=['--save-board']
    subprocess.run(cmd+[str(board)],check=True,timeout=120,capture_output=True)
    return json.loads(out.read_text())

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    board=OUT/(NAME+'.kicad_pcb')
    if board.exists():raise SystemExit('Repair already exists; preserve it, do not overwrite.')
    original=SOURCE.read_text();text=original
    for a,b in spans(text,'footprint'):
        fragment=text[a:b]
        if fp_ref(parse(fragment))!='AE201':continue
        assert child(parse(fragment),'layer')[1]=='B.Cu'
        for c,d in spans(fragment,'zone'):
            z=parse(fragment[c:d])
            if child(z,'name')[1]!='VV_ANTENNA_OTHER_LAYERS':continue
            old=fragment[c:d];new=old.replace('"B.Cu"','"F.Cu"',1)
            fragment=fragment[:c]+new+fragment[d:];break
        text=text[:a]+fragment+text[b:];break
    assert inventory(text)==inventory(original)
    board.write_text(text)
    for suffix in ['.kicad_pro','.kicad_dru']:shutil.copy2(DESIGN/(NAME+suffix),OUT/(NAME+suffix))
    shutil.copy2(DESIGN/'fp-lib-table',OUT/'fp-lib-table')
    (OUT/'VoiceVault_B0.pretty').symlink_to(DESIGN/'VoiceVault_B0.pretty',target_is_directory=True)
    removed=[];history=[]
    # Native saving assigns persistent identities to UUID-less Quilter tracks.
    for iteration in range(6):
        report=drc(board,OUT/f'drc-{iteration}.json',save=True)
        text=board.read_text();pcb=parse(text)
        # Native serialization may normalize strings; compare actual components
        # using the native before/after checkpoints once stable IDs exist.
        if iteration==0:stable_inventory=inventory(text)
        else:assert inventory(text)==stable_inventory,'Component/pad/placement changed'
        history.append(dict(iteration=iteration,violations=dict(collections.Counter(v['type'] for v in report['violations'])),opens=len(report['unconnected_items'])))
        objects={};locations={}
        for kind in ['segment','arc','via']:
            for a,b in spans(text,kind):
                node=parse(text[a:b]);u=child(node,'uuid')[1];objects[u]=(a,b,kind);locations[u]=node
        selected={}
        for v in report['violations']:
            if v['type'] not in ['shorting_items','clearance','hole_clearance','solder_mask_bridge']:continue
            candidates=[i for i in v['items'] if i['uuid'] in objects]
            candidates.sort(key=lambda i:objects[i['uuid']][2]!='via')
            if candidates:selected.setdefault(candidates[0]['uuid'],[]).append(v['type'])
        if not selected:break
        if iteration==5:break
        for u in selected:removed.append(dict(uuid=u,kind=objects[u][2],reasons=sorted(set(selected[u])),geometry=locations[u]))
        for a,b,_ in sorted([objects[u] for u in selected],reverse=True):text=text[:a]+text[b:]
        board.write_text(text)
    # Verify the actual reference/value/net/pose identity against original return.
    def sig(t):
        return {fp_ref(f):(next(p[2] for p in children(f,'property') if p[1]=='Value'),tuple(float(x) for x in child(f,'at')[1:3]),child(f,'layer')[1],sorted((p[1],child(p,'net')[1] if child(p,'net') else '') for p in children(f,'pad'))) for f in children(parse(t),'footprint')}
    before=sig(original);after=sig(board.read_text());assert before.keys()==after.keys()
    rounding=max(abs(a-b) for r in before for a,b in zip(before[r][1],after[r][1]))
    assert rounding<=0.000001,'Native serialization moved a component beyond one nanometre'
    assert all(before[r][0]==after[r][0] and before[r][2:]==after[r][2:] for r in before)
    result=dict(status='PARTIAL REPAIR - NOT ACCEPTED',source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),board_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),antenna_layer_membership_corrected=True,component_values_pad_nets_and_poses_preserved=True,max_native_position_rounding_mm=rounding,invalid_copper_removed=len(removed),removed=removed,history=history,manufacturing_ready=False)
    (OUT/'repair.json').write_text(json.dumps(result,indent=2)+'\n')
    # Placement hints have no routing restrictions. KiCad's DSN writer
    # nevertheless exports them as solid copper keepouts; omit only those
    # hints from a separate export copy, preserving the checked native board.
    export=board.read_text();drop=[]
    for a,b in spans(export,'zone'):
        node=parse(export[a:b]);name=child(node,'name')
        if name and name[1].startswith('VV_REGION_'):
            assert all(c[1]=='allowed' for c in child(node,'keepout')[1:])
            drop.append((a,b))
    assert len(drop)==13
    for a,b in reversed(drop):export=export[:a]+export[b:]
    (OUT/'export-input.kicad_pcb').write_text(export)
    for suffix in ['.kicad_pro','.kicad_dru']:
        shutil.copy2(OUT/(NAME+suffix),OUT/('export-input'+suffix))
    (OUT/'export-note.json').write_text(json.dumps(dict(placement_only_regions_omitted_from_export=13,
        reason='Native DSN exporter converts nonblocking placement hints to copper keepouts; actual copper and antenna restrictions remain.',native_repair_board_unchanged=True),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='removed'},indent=2))

if __name__=='__main__':main()
