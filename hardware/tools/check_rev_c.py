#!/usr/bin/env python3
"""Check real Rev C exports and keep placement, routing and hardware gates open."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c'
OUT=ROOT/'.lab-runs/hardware/standalone-c0'
PROFILE=ROOT/'.lab-cache/kicad-revc-checks'
CAD=['flatpak','run','--user',f'--env=KICAD_CONFIG_HOME={PROFILE}',
     '--command=kicad-cli','org.kicad.KiCad']
NAME='voicevault-standalone-c0'


def run(args,name,timeout=180,allowed_codes=(0,)):
    with (OUT/name).open('w') as log:
        p=subprocess.Popen(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise RuntimeError(f'{name}: timeout, no successful check claimed')
    if code not in allowed_codes:raise RuntimeError(f'{name}: command failed ({code}); see log')
    return code


def validate(nodes, mcu_package='bga'):
    # Independently specified critical connections based on vendor pin tables
    # and the intended trust boundary, not copied from an exported netlist.
    expected={
      ('U11','9'):'SE_SDA',('U11','10'):'SE_SCL',('U11','11'):'SE_ENABLE',
      ('U11','12'):'VDD_3V3',('U11','15'):'SE_VCC',('U11','18'):'SE_VCC',
      ('U11','1'):'GND',('U11','17'):'GND',('U11','19'):'GND',('U11','21'):'GND',
      ('U6','25'):'RAD_SWDCLK',('U6','26'):'RAD_SWDIO',('U6','8'):'RAD_TX',
      ('U6','10'):'RAD_RX',('U6','7'):'RAD_RTS',('U6','9'):'RAD_CTS',
      ('U6','13'):'RADIO_3V3',('U6','36'):'RADIO_3V3',('U6','48'):'RADIO_3V3',
      ('U6','31'):'GND',('U6','45'):'GND',('U6','49'):'GND',
      ('U3','1'):'BAT_TS',('U3','2'):'BAT_PACK',('U3','3'):'BAT_PACK',
      ('U3','4'):'GND',('U3','5'):'GND',('U3','6'):'CHARGER_500_EN',
      ('U3','10'):'VSYS',('U3','11'):'VSYS',('U3','13'):'USB_5V_FUSED',
      ('U3','16'):'CHARGER_ISET',('U3','17'):'GND',
      ('U1201','5'):'REG_FB',('U1201','7'):'VDD_3V3',('U1201','8'):'VDD_3V3',
      ('U1201','9'):'REG_L2',('U1201','10'):'GND',('U1201','11'):'REG_L1',
      ('U1201','12'):'VSYS',('U1201','13'):'VSYS',('U1201','14'):'REG_ENABLE',
      ('U1202','1'):'VDD_3V3',('U1202','2'):'GND',('U1202','3'):'RADIO_POWER_EN',
      ('U1202','4'):'RADIO_FAULT_N',('U1202','5'):'RADSW_ILIM',('U1202','6'):'RADIO_3V3',
      ('U401','1'):'VDD_3V3',('U401','6'):'SD_3V3',
      ('U602','1'):'VDD_3V3',('U602','5'):'AUD_2V8_REG',
      ('R501','1'):'USB_CC1',('R501','2'):'GND',('R502','1'):'USB_CC2',('R502','2'):'GND',
      ('U1','K11'):'SE_SCL',('U1','K9'):'SE_SDA',('U1','L11'):'SE_ENABLE',
      ('U1','J9'):'MCU_VDD11',('U1','D4'):'MCU_VDD11',('U1','C10'):'MCU_SWDIO',
      ('U6','30'):'RAD_ANT',('L201','1'):'RAD_ANT',('L201','2'):'RAD_RF_50',
      ('C212','1'):'RAD_RF_50',('C212','2'):'RAD_MATCH',('L202','1'):'RAD_MATCH',('L202','2'):'GND',
      ('L203','1'):'RAD_MATCH',('L203','2'):'BLE_ANT_FEED',('AE201','1'):'BLE_ANT_FEED',
    }
    if mcu_package == 'lqfp':
        expected = {key:value for key,value in expected.items() if key[0] != 'U1'}
        expected.update({('U1','77'):'SE_SCL',('U1','78'):'SE_SDA',('U1','75'):'SE_ENABLE',
                         ('U1','67'):'MCU_VDD11',('U1','142'):'MCU_VDD11',('U1','107'):'MCU_SWDIO'})
    elif mcu_package != 'bga':
        raise ValueError('Unknown exact MCU package')
    for key,value in expected.items():
        if nodes.get(key)!=value:raise ValueError(f'Critical connection {key}: expected {value}, got {nodes.get(key)}')
    forbidden=('SE_','MCU_','AUD_','HEADSET_','REG_','CHARGER_','BAT_',
               'SD_','LCD_','TOUCH_','HAPTIC_')
    for (ref,pin),net in nodes.items():
        if ref in ('U6','J102') and net.startswith(forbidden):
            raise ValueError(f'Radio/debug linked to a trusted interface: {ref}.{pin} {net}')
    return len(expected)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spice',action='store_true')
    parser.add_argument('--design-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);PROFILE.mkdir(parents=True,exist_ok=True)
    for name,body in [('sym-lib-table','(sym_lib_table (version 7))\n'),('fp-lib-table','(fp_lib_table (version 7))\n')]:
        (PROFILE/name).write_text(body)
    checks=[];report=dict(revision='C0',checked_utc=datetime.now(timezone.utc).isoformat(),
        manufacturing='BLOCKED',layout='UNPLACED / UNROUTED FOR QUILTER',checks=checks)
    try:
        report['kicad_version']=subprocess.check_output(CAD+['version'],text=True).strip()
        report['input_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(DESIGN.iterdir()) if p.suffix in {'.kicad_sch','.kicad_pcb','.kicad_pro','.kicad_dru'}
            or p.name in {'circuits.json','package-geometry.json','references.json','quilter-intent.json'}}
        d=json.loads((DESIGN/'decisions.json').read_text())
        if hashlib.sha256((ROOT/'hardware/rev-b/voicevault-standalone-b0.kicad_pcb').read_bytes()).hexdigest()!=d['preserved_b0_pcb_sha256']:
            raise RuntimeError('Preserved B0 PCB changed')
        run(CAD+['sch','export','netlist','--format','kicadxml','--output',OUT/'netlist.xml',DESIGN/(NAME+'.kicad_sch')],'netlist.log')
        tree=ET.parse(OUT/'netlist.xml').getroot()
        nodes={(n.get('ref'),n.get('pin')):net.get('name').removeprefix('/')
               for net in tree.findall('./nets/net') for n in net.findall('node')}
        components={x.get('ref'):x.findtext('value') for x in tree.findall('./components/comp')}
        if any(x in components for x in ['U8','U5','U7','U10','J801']):raise ValueError('Removed secure/Qi/NFC/vibration core remains')
        if any(n.startswith('HAPTIC_') for n in nodes.values()):raise ValueError('Removed vibration interface remains')
        if components.get('U11')!='SE050E2HQ1/Z01Z3Z':raise ValueError('Incorrect secure-element variant')
        checks.append(dict(check='Manufacturer critical pin maps / radio boundary',status='PASS',pins=validate(nodes)))
        for key,wrong in [(('U11','9'),'SE_SCL'),(('U11','18'),'GND'),(('U6','26'),'SE_SDA'),(('R502','2'),'USB_CC1'),(('C212','2'),'GND')]:
            corrupt=nodes|{key:wrong}
            try:validate(corrupt)
            except ValueError:continue
            raise RuntimeError('Negative control accepted corrupt critical net: '+str(key))
        checks.append(dict(check='Five corrupt-net negative controls including antenna-match regression',status='PASS'))
        run(['flatpak','run','--user','--command=python3','org.kicad.KiCad',ROOT/'hardware/tools/inspect_rev_c.py'],'pad-inspection.log')
        native=json.loads((OUT/'board-pads.json').read_text())
        migration=json.loads((DESIGN/'migration-summary.json').read_text())
        if len(components)!=migration['new_schematic_components'] or len(native['parts'])!=migration['new_total_footprints']:
            raise RuntimeError('Native inventory differs from migration counts')
        report['inventory']={k:migration[k] for k in ['old_schematic_components','old_total_footprints',
            'new_electrical_components','new_probe_pads','new_mounting_holes','new_total_footprints']}
        actual={(p['ref'],x['number']):x['net'].removeprefix('/') for p in native['parts'] for x in p['pads']}
        for key,net in nodes.items():
            if net.startswith('unconnected-'):continue
            if actual.get(key)!=net:raise RuntimeError(f'Schematic/copper-pad mismatch {key}: {net} != {actual.get(key)}')
        validate(actual)
        if native['tracks_vias'] or native['copper_pours'] or not native['electrical_inventory_unplaced']:
            raise RuntimeError('Input contains routed copper or electrical component placement')
        checks.append(dict(check='Native pads match schematic; all electrical parts unplaced; no routed copper',status='PASS',
                           footprints=len(native['parts']),connected_nodes=len(nodes)))
        run(CAD+['sch','erc','--format','json','--output',OUT/'erc.json',DESIGN/(NAME+'.kicad_sch')],'erc.log')
        erc=json.loads((OUT/'erc.json').read_text())
        violations=[v for s in erc.get('sheets',[]) for v in s.get('violations',[])]
        if violations:raise RuntimeError(f'ERC has {len(violations)} unresolved violations')
        checks.append(dict(check='Native KiCad electrical rules',status='PASS',violations=0))
        run(CAD+['pcb','drc','--format','json','--output',OUT/'drc.json',DESIGN/(NAME+'.kicad_pcb')],'drc.log')
        drc=json.loads((OUT/'drc.json').read_text())
        report['unplaced_drc_counts']={k:len(drc.get(k,[])) for k in ['violations','unconnected_items','schematic_parity']}
        report['unplaced_drc_types']=dict(Counter(x.get('type') for x in drc.get('violations',[])))
        report['full_native_unrouted_connections']=native['unrouted_connections']
        if any(x.get('type') in {'shorting_items','clearance','hole_clearance'} for x in drc.get('violations',[])):
            raise RuntimeError('Native DRC finds an electrical clearance/short within the unplaced inventory')
        checks.append(dict(check='Placement/routing/final DRC',status='BLOCKED',reason='Quilter placement and routing not performed; raw DRC retained'))
        if (DESIGN/'quilter-intent.json').exists():
            run([sys.executable,ROOT/'hardware/tools/check_rev_c_quilter.py'],'quilter-policy.log',timeout=180)
            report['quilter_policy']=json.loads((OUT/'quilter-policy/report.json').read_text())
            checks.append(dict(check='Native antenna policy / isolated positive and negative controls',status='PASS',cases=7))
        if args.spice:
            run([sys.executable,'-m','unittest','discover','-s','hardware/tests','-p','test_spice_results.py'],
                'spice-result-regression.log')
            checks.append(dict(check='Simulator result/abort regression',status='PASS',tests=6))
            (OUT/'spice-summary.json').unlink(missing_ok=True)
            run([sys.executable,ROOT/'hardware/tools/spice_rev_c.py'],'spice.log',timeout=240)
            report['spice']=json.loads((OUT/'spice-summary.json').read_text())
        report['available_design_checks']='PASS'
    except Exception as e:
        report['available_design_checks']='FAIL';report['error']=str(e)
    report['open_hardware_gates']=['Exact battery/holder and temperature profile acceptance',
        'Converter/charger model limitations and stability/thermal bench evidence',
        'RF/antenna constraints and returned-layout qualification','Real NXP provisioning, RNG and storage atomicity',
        'MCU peripheral/firmware, audio/DMA, trusted UI and hostile-radio hardware tests']
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 1 if report['available_design_checks']=='FAIL' else 0 if args.design_only else 2


if __name__=='__main__':sys.exit(main())
