#!/usr/bin/env python3
"""Read native CAD, verify the corrected input, and prepare reviewed CSV settings.

Uses host Python and native CLI exports, never KiCad's Python mutation API.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from check_rev_c import validate

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-c'
OUT=ROOT/'.lab-runs/hardware/standalone-c0/final-input'
CSV=DESIGN/'quilter-settings'


def parse(text):
    stack=[];root=None
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text,re.S):
        token=m[0]
        if token=='(':
            node=[]
            if stack:stack[-1].append(node)
            else:root=node
            stack.append(node)
        elif token==')':stack.pop()
        else:stack[-1].append(json.loads(token) if token.startswith('"') else token)
    assert not stack
    return root


def children(node,name):return [x for x in node if isinstance(x,list) and x and x[0]==name]
def child(node,name):return next(iter(children(node,name)),[])


def write_csv(name,fields,rows):
    with (CSV/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    CSV.mkdir(exist_ok=True)
    pcb=parse((DESIGN/'voicevault-standalone-c0.kicad_pcb').read_text())
    footprints=children(pcb,'footprint');actual={}
    for fp in footprints:
        ref=next(p[2] for p in children(fp,'property') if p[1]=='Reference')
        if not ref.startswith('H'):assert float(child(fp,'at')[1])>100
        for pad in children(fp,'pad'):
            if pad[1]:actual[(ref,pad[1])]=child(pad,'net')[1] if child(pad,'net') else ''
    assert len(footprints)==213 and not any(children(pcb,t) for t in ['segment','via','arc'])
    assert all(child(z,'keepout') for z in children(pcb,'zone'))
    assert validate(actual)==72
    xml=ET.parse(OUT/'netlist.xml').getroot()
    comps={c.get('ref'):c for c in xml.findall('./components/comp')}
    libs={(p.get('lib'),p.get('part')):p for p in xml.findall('./libparts/libpart')}
    nodes={(n.get('ref'),n.get('pin')):net.get('name').removeprefix('/')
           for net in xml.findall('./nets/net') for n in net.findall('node')}
    functional={key:net for key,net in nodes.items() if not net.startswith('unconnected-')}
    for key,net in functional.items():assert actual.get(key)==net,(key,net,actual.get(key))
    assert validate(nodes)==72
    erc=json.loads((OUT/'erc.json').read_text());drc=json.loads((OUT/'drc.json').read_text())
    assert not [v for s in erc['sheets'] for v in s.get('violations',[])]
    assert not drc['violations']
    pins={}
    for ref,c in comps.items():
        s=c.find('libsource');pins[ref]={p.get('num'):dict(p.attrib) for p in libs[(s.get('lib'),s.get('part'))].findall('./pins/pin')}
    manifest=json.loads((DESIGN/'circuits.json').read_text())
    pages={p['ref']:page['name'] for page in manifest['pages'] for p in page['parts']}
    overrides={
      'C6':('U1','C2'),'C112':('U1','C2'),
      **{'C'+str(c):('U1',p) for c,p in [(7,'H5'),(8,'E3'),(9,'G10'),(10,'F5'),(11,'E8'),(12,'G8'),
          (13,'D10'),(14,'J10'),(16,'E10'),(17,'H7'),(18,'E6'),(20,'J4'),(21,'H3'),(26,'M8')]},
      'C15':('U1','H5'),'C19':('U1','E8'),'C25':('U1','M8'),'C108':('U1','M8'),
      'C109':('U1','J4'),'C110':('U1','E3'),'C111':('U1','D10'),
      'C22':('U1','D4'),'C23':('U1','G3'),'C24':('U1','J9'),'C27':('U1','J9'),'C107':('U1','D4'),
      'C306':('U1','J2'),'C502':('J502','1'),
      'C205':('U6','36'),'C208':('U6','13'),
      'C213':('U201','16'),'C214':('U201','15'),'C215':('U202','16'),'C216':('U202','15'),
      'C401':('U401','1'),'C402':('U401','6'),'C403':('J401','4'),
      'C404':('U402','16'),'C405':('U402','15'),
      'C1101':('U11','12'),'C1102':('U11','18'),'C1103':('U11','12'),
      'C1201':('U1201','12'),'C1202':('U1201','13'),'C1203':('U1201','7'),
      'C1204':('U1201','8'),'C1205':('U1201','7'),'C1206':('U1201','3'),'C1207':('U1202','1'),
      'C701':('J701','7'),'C702':('J701','8'),'C703':('J702','1')}
    bypass=[];excluded=[]
    for ref,comp in comps.items():
        if not re.fullmatch(r'C\d+',ref):continue
        capnets={nodes.get((ref,p)) for p in pins[ref]}-{'GND',None}
        if 'GND' not in {nodes.get((ref,p)) for p in pins[ref]}:
            excluded.append(ref);continue  # Series coupling/matching, not a bypass.
        assert len(capnets)==1,(ref,capnets)
        net=next(iter(capnets));target=overrides.get(ref)
        if target is None:
            candidates=[(r,p) for (r,p),n in nodes.items() if n==net and r.startswith('U')]
            power=[(r,p) for r,p in candidates if pins[r][p].get('type','').startswith('power')]
            samepage=[key for key in power if pages.get(key[0])==pages.get(ref)]
            candidates=samepage or power or candidates
            assert candidates,('No reviewed bypass parent',ref,net)
            target=sorted(candidates)[0]
        assert nodes.get(target)==net,(ref,target,net,nodes.get(target))
        value=comp.findtext('value');m=re.match(r'([\d.]+)\s*([pnuµ])',value)
        assert m,(ref,value)
        nf=float(m[1])*{'p':.001,'n':1,'u':1000,'µ':1000}[m[2]]
        bypass.append(dict(capacitor=ref,bypassed_component=target[0],bypassed_pin=target[1],capacitance=f'{nf:g}'))
    write_csv('bypass_capacitors.csv',['capacitor','bypassed_component','bypassed_pin','capacitance'],bypass)
    currents=[('VDD_3V3',500,'U1201','7'),('VSYS',1000,'U3','10'),('BAT_PACK',1000,'J502','1'),
      ('USB_5V_RAW',500,'J501','A9'),('USB_5V_FUSED',500,'F501','2'),
      ('RADIO_3V3',160,'U1202','6'),('SD_3V3',500,'U401','6'),
      ('AUD_2V8_REG',200,'U602','5'),('AUD_LDOIN_2V8',200,'R609','2'),
      ('AUD_AVDD_1V8',100,'U601','24'),('AUD_DVDD_1V72',100,'U601','29'),
      ('MCU_VBAT_3V3',10,'R101','2'),('MCU_VDD11',200,'L1','2'),('SE_VCC',100,'U11','15')]
    rows=[]
    for net,current,ref,pin in currents:
        assert nodes.get((ref,pin))==net,(net,ref,pin,nodes.get((ref,pin)))
        rows.append(dict(net_name=net,max_current=current,use_power_pour='false',source_component=ref,source_pin=pin))
    write_csv('high_current_nets.csv',['net_name','max_current','use_power_pour','source_component','source_pin'],rows)
    converters=[dict(switching_converter=u,inductor=l,input_capacitor=ci,output_capacitor=co)
                for u,l,ci,co in [('U1','L1','C108','C107'),('U1201','L1201','C1201','C1203'),('U9','L701','C704','C705')]]
    assert all(all(x in comps for x in row.values()) for row in converters)
    write_csv('switching_converters.csv',['switching_converter','inductor','input_capacitor','output_capacitor'],converters)
    write_csv('single_ended_impedance_signals.csv',['net_name','single_ended_impedance','frequency'],
              [dict(net_name='RAD_RF_50',single_ended_impedance=50,frequency=2.4)])
    report=dict(status='PASS',verification='Host read of native board plus fresh native CLI netlist/ERC/DRC; no native Python mutations',
      footprints=213,total_netlist_nodes=len(nodes),functional_pin_nets_verified=len(functional),critical_pin_nets=72,
      erc_violations=0,drc_violations=0,tracks_and_vias=0,copper_pours=0,
      bypass_entries=len(bypass),series_capacitors_excluded=excluded,
      current_limits='Provisional routing allocations, not measured loads or battery approval',
      controlled_impedance='RAD_RF_50 only; antenna cutout/feed still requires RF qualification',
      sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DESIGN.iterdir()
               if p.suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru']},
      configuration_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in CSV.glob('*.csv')},
      manufacturing_ready=False)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
