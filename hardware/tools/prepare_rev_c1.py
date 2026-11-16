#!/usr/bin/env python3
"""Create/finalize separate C1 LQFP CAD inputs without electrical placement.

Run 'prepare', then the native generator with --mcu-package lqfp --unplaced,
then 'finalize'. The finalizer uses host text editing, not native zone mutation.
"""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

from finalize_rev_c_quilter_input import parse, child, children
from prepare_rev_c_retry import spans, fp_ref

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'hardware/rev-c'
SOURCE = OLD / 'quilter-retry-01'
DEST = ROOT / 'hardware/rev-c1'
NAME = 'voicevault-standalone-c1'
OLDNAME = 'voicevault-standalone-c0'
LIB = 'VoiceVault_B0.pretty'
ANT = 'Johanson_2450AT18x100.kicad_mod'
EVIDENCE = ROOT / 'hardware/evidence/2026-11-16/c1-preparation'

# Explicit supply-pin allocation; repeated supply pins cannot be mapped by an
# arbitrary list order. These are ST DS14102 Fig.9 / Table27 pin numbers.
BYPASS = {
    'C6':'6','C112':'6','C7':'25','C8':'13','C9':'95','C10':'83',
    'C11':'89','C12':'41','C13':'108','C14':'69','C15':'25','C16':'109',
    'C17':'55','C18':'131','C19':'89','C20':'35','C21':'34',
    'C22':'67','C23':'14','C24':'142','C25':'65','C26':'65','C27':'142',
    'C107':'67','C108':'65','C109':'35','C110':'13','C111':'108',
    'C113':'122','C114':'144','C115':'20','C306':'28',
}
# These ground-referenced capacitors belong to oscillator, RF matching, reset,
# audio filtering or timing circuits; they are not supply bypass definitions.
NON_BYPASS = {'C201','C202','C210','C211','C301','C302','C303','C304',
              'C203','C306','C610','C1208'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected():
    files = [ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb',
             OLD/(OLDNAME+'.kicad_pcb'), SOURCE/(OLDNAME+'.kicad_pcb'),
             OLD/'local-repair-01'/(OLDNAME+'.kicad_pcb')]
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def prepare():
    if DEST.exists():
        raise SystemExit('C1 already exists; preserve it rather than regenerate.')
    DEST.mkdir()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE/'preserved-input-hashes.json').write_text(json.dumps(protected(),indent=2)+'\n')
    data = json.loads((OLD/'circuits.json').read_text())
    data['revision'] = 'C1'
    assert data['mcu_signals'].pop('PC0') == 'SD_SCK_MCU'
    assert 'PB13' not in data['mcu_signals']
    data['mcu_signals']['PB13'] = 'SD_SCK_MCU'
    data['mcu'] = {'part':'STM32U5G9ZJT6Q', 'package':'LQFP144',
                   'symbol':'STM32U5G9ZJTxQ', 'body_mm':[20,20]}
    next(p for pg in data['pages'] for p in pg['parts'] if p['ref']=='JP501')['in_bom']=False
    data['root_extra_parts'] = [dict(ref=ref,value='100n 10V',kind='C',
        nets={'1':net,'2':'GND'}) for ref,net in
        [('C113','VDD_3V3'),('C114','VDD_3V3'),('C115','MCU_VDD11')]]
    for p in data['root_extra_parts']:
        data['root_parts'][p['ref']] = {'footprint':'Capacitor_SMD:C_0402_1005Metric'}
    sd = next(p for p in data['pages'] if p['name']=='microsd')
    sd['notes'].append('C1: hardware SPI2 clock is PB13 (pin 70), not PC0. PC1=MOSI; PC2=MISO; PC7=software CS.')
    (DEST/'circuits.json').write_text(json.dumps(data,indent=2)+'\n')
    shutil.copytree(SOURCE/LIB, DEST/LIB)
    # Native generation sees a zone-free antenna footprint. Attach the reviewed
    # three rule areas afterward as text, avoiding the prior Python 3.14 crash.
    p = DEST/LIB/ANT
    text = p.read_text()
    for a,b in sorted(list(spans(text,'zone')),reverse=True):
        text = text[:a]+text[b:]
    p.write_text(text)
    for file in ['LICENSE','references.json','package-geometry.json','ble-pin-migration.csv']:
        shutil.copy2(OLD/file, DEST/file)
    decisions = copy.deepcopy(json.loads((OLD/'decisions.json').read_text()))
    decisions.update(revision='C1',recorded='2026-11-16',status='LQFP-migration-in-progress',
                     manufacturing_ready=False)
    decisions['engineering_selections']['mcu']='STM32U5G9ZJT6Q'
    decisions['engineering_selections']['mcu_package']='LQFP144 20x20mm 0.5mm pitch'
    decisions['engineering_selections']['sd_spi2_clock']='PB13'
    (DEST/'decisions.json').write_text(json.dumps(decisions,indent=2)+'\n')
    print('Prepared C1 circuit/library inputs. Native CAD generation is the next step.')


def finalize():
    before = json.loads((EVIDENCE/'preserved-input-hashes.json').read_text())
    assert protected() == before
    marker = DEST/'preparation.json'
    if marker.exists():
        raise SystemExit('C1 already finalized; preserve it and its future returned layout.')
    path = DEST/(NAME+'.kicad_pcb')
    text = path.read_text()
    board = parse(text)
    assert len(children(board,'footprint')) == 216
    assert not any(children(board,k) for k in ['segment','via','arc','zone'])
    assert all(float(child(f,'at')[1])>100 and not children(f,'locked')
               for f in children(board,'footprint') if not fp_ref(f).startswith('H'))
    # Validate mapping coverage before writing any final files.
    with (OLD/'quilter-settings/bypass_capacitors.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if row['bypassed_component']=='U1' and row['capacitor'] not in NON_BYPASS:
                assert row['capacitor'] in BYPASS, row
    original = (SOURCE/(OLDNAME+'.kicad_pcb')).read_text()
    source = parse(original)
    sa,sb = next((a,b) for a,b in spans(original,'footprint') if fp_ref(parse(original[a:b]))=='AE201')
    ta,tb = next((a,b) for a,b in spans(text,'footprint') if fp_ref(parse(text[a:b]))=='AE201')
    old_fp,new_fp = parse(original[sa:sb]),parse(text[ta:tb])
    ox,oy = map(float,child(old_fp,'at')[1:3])
    nx,ny = map(float,child(new_fp,'at')[1:3])
    zones = []
    for a,b in spans(original[sa:sb],'zone'):
        z = original[sa:sb][a:b]
        z = re.sub(r'\(xy\s+([\d.-]+)\s+([\d.-]+)\)',
                   lambda m:f'(xy {float(m[1])-ox+nx:g} {float(m[2])-oy+ny:g})',z)
        zones.append(z)
    assert len(zones)==3
    text = text[:ta]+text[ta:tb].rstrip()[:-1]+'\n'+'\n'.join(zones)+'\n)'+text[tb:]
    guides = [original[a:b] for a,b in spans(original,'zone')]
    assert all(child(parse(z),'keepout') for z in guides)
    text = text.rstrip()[:-1]+'\n'+'\n'.join(guides)+'\n)\n'
    # Match the selected cloud preset's modeled thickness; layer roles are
    # independently selected and verified in Quilter, not inferred from names.
    text = re.sub(r'(\(general\s*\(thickness\s+)[\d.]+',r'\g<1>1.538',text,count=1)
    path.write_text(text)
    shutil.copy2(SOURCE/LIB/ANT, DEST/LIB/ANT)
    # Remove the unused old MCU footprint from this new library only.
    (DEST/LIB/'UFBGA-144_10x10mm_Layout12x12_P0.8mm.kicad_mod').unlink(missing_ok=True)
    project = json.loads((SOURCE/(OLDNAME+'.kicad_pro')).read_text())
    project['meta']['filename']=NAME+'.kicad_pro'
    (DEST/(NAME+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
    shutil.copy2(SOURCE/(OLDNAME+'.kicad_dru'),DEST/(NAME+'.kicad_dru'))
    settings = DEST/'quilter-settings'
    settings.mkdir(exist_ok=True)
    for file in (OLD/'quilter-settings').glob('*.csv'):
        with file.open(newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        if file.name=='bypass_capacitors.csv':
            rows=[row for row in rows if row['capacitor'] not in NON_BYPASS]
            for row in rows:
                if row['bypassed_component']=='U1':
                    row['bypassed_pin']=BYPASS[row['capacitor']]
            rows += [dict(capacitor=ref,bypassed_component='U1',bypassed_pin=BYPASS[ref],capacitance='100')
                     for ref in ['C113','C114','C115']]
        with (settings/file.name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    intent = json.loads((OLD/'quilter-intent.json').read_text())
    intent['revision']='C1'
    intent['mcu']='STM32U5G9ZJT6Q / LQFP144'
    intent['automatic_mcu_bga_fanout']=False
    intent['excluded_non_supply_bypass_definitions']=sorted(NON_BYPASS)
    intent['electrical_components']=199
    intent['footprints']=216
    intent['c1_changes']=['Exact LQFP144 pin mapping','SD clock PC0 -> PB13',
        'Three extra bypass capacitors','No copied BGA/cloud/local routed copper',
        'Keep antenna on F.Cu in cloud configuration to avoid known layer-flip export issue']
    (DEST/'quilter-intent.json').write_text(json.dumps(intent,indent=2)+'\n')
    report = dict(revision='C1',status='generated-unplaced-input-awaiting-native-checks',
        mcu='STM32U5G9ZJT6Q',footprints=216,electrical_components=199,
        added_components=['C113','C114','C115'],sd_clock='PB13 / LQFP pin 70',
        electrical_placement='off-board inventory only; Quilter selects actual placement',
        tracks=0,vias=0,copper_pours=0,footprint_antenna_keepouts=3,
        board_thickness_mm=1.538,manufacturing_ready=False,
        source_preserved=protected()==before)
    assert protected()==before
    marker.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','finalize'])
    globals()[p.parse_args().action]()
