#!/usr/bin/env python3
"""Native C1 ERC/parity, complete MCU pin/function and cloud-settings audit."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from check_rev_c import validate
from evaluate_lqfp_candidate import vendor, FUNCTIONS
from finalize_rev_c_quilter_input import parse, child, children
from prepare_rev_c_retry import fp_ref

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c1'
OUT=ROOT/'.lab-runs/hardware/standalone-c1'
EVIDENCE=ROOT/'hardware/evidence/2026-11-16/c1-preparation'
NAME='voicevault-standalone-c1'
PROFILE=ROOT/'.lab-cache/kicad-revc-checks'
CAD=['flatpak','run','--user',f'--env=KICAD_CONFIG_HOME={PROFILE}',
     '--command=kicad-cli','org.kicad.KiCad']


def native(arguments,log):
    p=subprocess.run(CAD+list(map(str,arguments)),capture_output=True,text=True,timeout=120)
    (OUT/log).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(log,p.returncode,p.stderr[-1000:])


def check_connections(nodes,manifest,pins):
    assert validate(nodes,mcu_package='lqfp')==72
    signals={'PA13':'MCU_SWDIO','PA14':'MCU_SWCLK','PB3':'MCU_SWO','NRST':'MCU_NRST',
             'PC8':'MCU_UART_RX','PC9':'MCU_UART_TX'} | manifest['mcu_signals']
    assert signals.get('PB13')=='SD_SCK_MCU' and 'PC0' not in signals
    expected={}
    function_checks=0
    for pin,info in pins.items():
        net=signals.get(info['name'])
        if info['name'] in ['VDD','VDDIO2','VDDDSI','VDDUSB','VDDA','VDDSMPS','VREF+']:
            net='VDD_3V3'
        if info['name'] in ['VDD11','VDD11DSI']:net='MCU_VDD11'
        if info['name'] in ['VSS','VSSA','VSSDSI','VSSSMPS']:net='GND'
        if info['name']=='VBAT':net='MCU_VBAT_3V3'
        if info['name']=='VLXSMPS':net='MCU_LX'
        actual=nodes.get(('U1',pin),'')
        if actual.startswith('unconnected-'):actual=''
        assert actual==(net or ''),(pin,info['name'],net,actual)
        if net:expected[pin]=net
        if info['name'] in signals:
            required=FUNCTIONS.get(net,'RESET' if info['name']=='NRST' else 'GPIO')
            assert required=='RESET' or required in info['functions'],(pin,net,required)
            function_checks+=1
    assert function_checks==55 and len(expected)==91
    assert nodes[('C113','1')]=='VDD_3V3' and nodes[('C114','1')]=='VDD_3V3'
    assert nodes[('C115','1')]=='MCU_VDD11'
    for ref in ['C113','C114','C115']:assert nodes[(ref,'2')]=='GND'
    assert nodes[('L1','1')]=='MCU_LX' and nodes[('L1','2')]=='MCU_VDD11'
    return expected


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((DESIGN/'circuits.json').read_text())
    _,pins=vendor(ROOT/'.lab-cache/hardware-research/2026-11-16/lqfp-evaluation/STM32U5G9ZJTxQ.xml','lqfp')
    native(['sch','export','netlist','--format','kicadxml','--output',OUT/'netlist.xml',DESIGN/(NAME+'.kicad_sch')],'netlist.log')
    xml=ET.parse(OUT/'netlist.xml').getroot()
    nodes={(n.get('ref'),n.get('pin')):net.get('name').removeprefix('/')
           for net in xml.findall('./nets/net') for n in net.findall('node')}
    comps={c.get('ref'):c for c in xml.findall('./components/comp')}
    expected=check_connections(nodes,manifest,pins)
    negative=[]
    for key,value in [(('U1','70'),'GND'),(('U1','29'),'SD_SCK_MCU'),
                      (('U1','20'),'VDD_3V3'),(('U1','142'),'VDD_3V3'),
                      (('U1','107'),'GND'),(('U6','26'),'SE_SDA'),(('C115','1'),'VDD_3V3')]:
        try:check_connections(nodes|{key:value},manifest,pins)
        except (AssertionError,ValueError):negative.append({'corrupt_pin':'.'.join(key),'detected':True})
        else:raise AssertionError(('Corrupt pin accepted',key))
    board=parse((DESIGN/(NAME+'.kicad_pcb')).read_text())
    footprints={fp_ref(f):f for f in children(board,'footprint')}
    assert len(footprints)==216
    assert not any(children(board,k) for k in ['segment','via','arc'])
    assert all(child(z,'keepout') for z in children(board,'zone'))
    actual={(ref,p[1]):child(p,'net')[1] if child(p,'net') else ''
            for ref,f in footprints.items() for p in children(f,'pad') if p[1]}
    functional={key:net for key,net in nodes.items() if not net.startswith('unconnected-')}
    for key,net in functional.items():assert actual.get(key)==net,(key,net,actual.get(key))
    for key,net in actual.items():
        if net:assert nodes.get(key)==net,(key,net,nodes.get(key))
    assert check_connections(actual,manifest,pins)==expected
    for ref,f in footprints.items():
        if ref.startswith('H'):continue
        assert float(child(f,'at')[1])>100 and not children(f,'locked'),ref
        assert child(f,'layer')[1]=='F.Cu',ref
    for ref,c in comps.items():
        assert child(footprints[ref],'property')  # Presence separately checked by native parity.
        value=next(p[2] for p in children(footprints[ref],'property') if p[1]=='Value')
        assert value==c.findtext('value'),(ref,value,c.findtext('value'))
    assert comps['U1'].findtext('value')=='STM32U5G9ZJT6Q'
    assert footprints['U1'][1]=='VoiceVault_B0:LQFP-144_20x20mm_P0.5mm'
    assert len(children(footprints['AE201'],'zone'))==3
    # Every bypass definition must point to a real pad sharing the cap's rail.
    with (DESIGN/'quilter-settings/bypass_capacitors.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        capnets={nodes[(r['capacitor'],p)] for p in ['1','2']}-{'GND'}
        assert len(capnets)==1 and nodes[(r['bypassed_component'],r['bypassed_pin'])] in capnets,r
    assert len(rows)==76
    # Each of ten VDD and both DSI-core supply pins has a specific 100 nF entry.
    for pin,p in pins.items():
        if p['name'] in ['VDD','VDD11DSI']:
            assert any(r['bypassed_component']=='U1' and r['bypassed_pin']==pin and r['capacitance']=='100' for r in rows),pin
    native(['sch','erc','--format','json','--output',OUT/'erc.json',DESIGN/(NAME+'.kicad_sch')],'erc.log')
    erc=json.loads((OUT/'erc.json').read_text())
    errors=[v for s in erc['sheets'] for v in s.get('violations',[])]
    assert not errors,errors[:3]
    native(['pcb','drc','--schematic-parity','--format','json','--output',OUT/'drc.json',DESIGN/(NAME+'.kicad_pcb')],'drc.log')
    drc=json.loads((OUT/'drc.json').read_text())
    assert not drc.get('violations'),drc.get('violations',[])[:3]
    assert not drc.get('schematic_parity'),drc.get('schematic_parity',[])[:3]
    p=subprocess.run(['flatpak','run','--user',f'--env=KICAD_CONFIG_HOME={PROFILE}',
        '--command=python3','org.kicad.KiCad',str(ROOT/'hardware/tools/inspect_rev_c.py'),
        '--board',str(DESIGN/(NAME+'.kicad_pcb')),'--out',str(OUT)],
        capture_output=True,text=True,timeout=120)
    (OUT/'pad-inspection.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr
    native_board=json.loads((OUT/'board-pads.json').read_text())
    assert native_board['input_board_sha256']==hashlib.sha256((DESIGN/(NAME+'.kicad_pcb')).read_bytes()).hexdigest()
    assert native_board['electrical_inventory_unplaced'] and native_board['copper_layers']==6
    before=json.loads((EVIDENCE/'preserved-input-hashes.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in before.items())
    report=dict(revision='C1',available_circuit_checks='PASS',manufacturing_ready=False,
        layout='UNPLACED / UNROUTED — QUILTER INPUT',mcu='STM32U5G9ZJT6Q',
        footprints=216,electrical_components=199,probe_pads=13,mounting_holes=4,
        erc_violations=0,drc_layout_violations=0,schematic_parity_violations=0,
        netlist_nodes=len(nodes),functional_pin_nets=len(functional),
        checked_mcu_pins=144,connected_mcu_pins=91,available_signal_functions=55,
        prior_critical_checks=72,negative_controls=negative,
        bypass_entries=len(rows),tracks=0,vias=0,copper_pours=0,
        unconnected_items_in_report=len(drc.get('unconnected_items',[])),
        full_native_unrouted_connections=native_board['unrouted_connections'],native_copper_layers=6,
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DESIGN.iterdir()
                       if p.suffix in ['.kicad_sch','.kicad_pcb','.kicad_pro','.kicad_dru']},
        warnings=['Native no-error checks apply to off-board inventory, not a placed/routed board.',
                  'Silicon, clock/DMA firmware, full power/charging, RF and physical security remain unqualified.'])
    for file in ['erc.json','drc.json']:
        (EVIDENCE/file).write_bytes((OUT/file).read_bytes())
    (EVIDENCE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (EVIDENCE/'mcu-pin-net.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['pin','function','net'])
        w.writerows((pin,p['name'],expected.get(pin,'')) for pin,p in sorted(pins.items(),key=lambda i:int(i[0])))
    with (DESIGN/'BOM-REVIEW.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['reference','value','footprint','status'])
        for ref,c in sorted(comps.items()):w.writerow([ref,c.findtext('value'),c.findtext('footprint'),'REVIEW — not purchasing/fabrication approval'])
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_hashes','negative_controls']},indent=2))


if __name__=='__main__':main()
