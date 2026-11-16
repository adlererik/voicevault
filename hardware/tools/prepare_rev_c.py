#!/usr/bin/env python3
"""Build a separate Rev C circuit manifest and package library; no PCB placement/routing.

Run this with host Python, then use create_standalone_draft.py --unplaced in
KiCad's Python runtime. B0 inputs are read-only. Exact pack/holder acceptance,
manufacturer-model coverage and hardware qualification remain release gates.
"""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'hardware/rev-b'
NEW = ROOT / 'hardware/rev-c'
FP = 'VoiceVault_B0:'  # Reuse the reviewed local-library namespace, not B0 CAD.


def passive(ref, value, one, two, kind='R', footprint=None):
    footprint = footprint or {'R':'Resistor_SMD:R_0402_1005Metric',
        'C':'Capacitor_SMD:C_0603_1608Metric', 'L':'Inductor_SMD:L_4.0x4.0_H1.8'}[kind]
    return dict(ref=ref, value=value, kind=kind, nets={'1':one,'2':two},
                footprint=footprint, schematic=[0,0], pcb=[0,0])


def ic(ref, value, footprint, pins):
    return dict(ref=ref, value=value, footprint=footprint,
        pins=[dict(number=str(n), name=name, net=net, type=typ) for n,name,net,typ in pins],
        schematic=[0,0], pcb=[0,0])


def page(name, title, parts, notes=()):
    # Schematic drawing positions only. The PCB generator ignores pcb=[0,0]
    # in --unplaced mode and parks electrical inventory outside the outline.
    block = 0
    small = 0
    for p in parts:
        if 'pins' in p:
            p['schematic'] = [75 + (block % 2)*110, 35 + (block//2)*85]
            block += 1
        else:
            p['schematic'] = [280 + (small % 3)*55, 35 + (small//3)*22]
            small += 1
    return dict(name=name,title=title,parts=parts,paper='A2',notes=list(notes),notes_y=330)


def rename(value, names):
    if isinstance(value,dict): return {k:rename(v,names) for k,v in value.items()}
    if isinstance(value,list): return [rename(v,names) for v in value]
    return names.get(value,value) if isinstance(value,str) else value


def main():
    NEW.mkdir(exist_ok=True)
    original = json.loads((OLD/'circuits.json').read_text())
    data = copy.deepcopy(original)
    data['revision']='C0'
    removed_pages = {'power','secure','qi','qi-control','nfc','nfc-matching','nfc-interface'}
    removed = [p['ref'] for pg in data['pages'] if pg['name'] in removed_pages for p in pg['parts']]
    data['pages'] = [p for p in data['pages'] if p['name'] not in removed_pages]
    data = rename(data, {'AUX_3V3':'VDD_3V3','PMIC_VBUS':'USB_5V_FUSED',
        'AUD_3V3_REG':'AUD_2V8_REG','AUD_LDOIN_3V3':'AUD_LDOIN_2V8','BAT_NTC':'BAT_TS',
        'PMIC_SDA':'HAPTIC_SDA','PMIC_SCL':'HAPTIC_SCL'})
    signals = data['mcu_signals']
    for pin in list(signals):
        if signals[pin].startswith(('TR_','OP_','QI_','NFC_','PMIC_')):
            del signals[pin]
    signals.update(PD12='SE_SCL',PD13='SE_SDA',PD10='SE_ENABLE',
                   PH10='RADIO_POWER_EN',PB11='RADIO_FAULT_N',
                   PA10='CHARGER_PGOOD_N',PH12='CHARGER_CHG_N')
    by_page = {p['name']:p for p in data['pages']}
    entry=by_page['power-entry']
    entry['parts']=[p for p in entry['parts'] if p['ref'] not in ['D501','D502','SW503']]
    removed.extend(['D501','D502','SW503'])
    battery=next(p for p in entry['parts'] if p['ref']=='J502')
    battery['value']='S2B-PH-SM4-TB(LF)(SN); BL-5C holder harness; exact holder pending'
    entry['parts'] += [passive('R501','5.1k 1%','USB_CC1','GND'),
                      passive('R502','5.1k 1%','USB_CC2','GND')]
    entry['notes']=['Power-only USB-C. No D+/D- or firmware transport.',
        'BL-5C pack and holder harness require acceptance. Third BSI terminal is not temperature sensing.',
        'J503 requires a real pack-temperature NTC; open/short sensor must inhibit charging.']
    entry.update(page(entry['name'],entry['title'],entry['parts'],entry['notes']))

    pwr=ic('U3','BQ24074RGTR',
        'Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm',[
        (1,'TS','BAT_TS','input'),(2,'BAT','BAT_PACK','passive'),(3,'BAT','BAT_PACK','passive'),
        (4,'CE_N','GND','input'),(5,'EN2','GND','input'),(6,'EN1','CHARGER_500_EN','input'),
        (7,'PGOOD_N','CHARGER_PGOOD_N','open_collector'),(8,'VSS','GND','power_in'),
        (9,'CHG_N','CHARGER_CHG_N','open_collector'),(10,'OUT','VSYS','power_out'),
        (11,'OUT','VSYS','passive'),(12,'ILIM','CHARGER_ILIM','input'),
        (13,'IN','USB_5V_FUSED','power_in'),(14,'TMR','CHARGER_TMR','input'),
        (15,'ITERM',None,'input'),(16,'ISET','CHARGER_ISET','input'),(17,'EP_GND','GND','power_in')])
    charger=[pwr,passive('R503','100k','CHARGER_500_EN','GND'),
        passive('R504','4.42k 1%','CHARGER_ISET','GND'),
        passive('R505','68.1k 1%','CHARGER_TMR','GND'),
        passive('R506','3.48k 1%','CHARGER_ILIM','GND'),
        passive('R507','47k','CHARGER_PGOOD_N','VDD_3V3'),
        passive('R508','47k','CHARGER_CHG_N','VDD_3V3'),
        passive('C503','4.7u 16V','USB_5V_FUSED','GND','C'),
        passive('C504','10u 10V','VSYS','GND','C'),
        passive('C505','10u 10V','BAT_PACK','GND','C'),
        ic('JP501','OPEN default 100mA input; bridge only with qualified 500mA supply',
           'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm',
           [(1,'USB_PRESENT','USB_5V_FUSED','passive'),(2,'500mA_MODE','CHARGER_500_EN','passive')])]
    data['pages'].insert(0,page('charging','Wired lithium-ion charger and system power path',charger,[
        'BQ24074: TS=10k pack NTC; CE low; timer active; ITERM open selects default.',
        'ISET 4.42k: approximately 201mA target, subject to actual pack acceptance.',
        'JP501 open selects 100mA source limit. Bridge only for an appropriate 5V source; no USB data enumeration.',
        'Input/system and battery paths need real charger/pack qualification; no complete charger SPICE model asserted.']))

    converter=ic('U1201','TPS63070RNMR',FP+'TPS63070_RNM0015A',[
        (1,'PS_SYNC','GND','input'),(2,'PG','MCU_NRST','open_collector'),
        (3,'VAUX','REG_VAUX','passive'),(4,'GND','GND','power_in'),
        (5,'FB','REG_FB','input'),(6,'FB2',None,'passive'),
        (7,'VOUT','VDD_3V3','power_out'),(8,'VOUT','VDD_3V3','passive'),
        (9,'L2','REG_L2','passive'),(10,'PGND','GND','power_in'),
        (11,'L1','REG_L1','passive'),(12,'VIN','VSYS','power_in'),
        (13,'VIN','VSYS','passive'),(14,'EN','REG_ENABLE','input'),(15,'VSEL','GND','input')])
    regulation=[converter,
        ic('SW503','JS102011SAQN; hard system power; charging remains connected',
           'Button_Switch_SMD:SW_SPDT_CK_JS102011SAQN',
           [(1,'ON_UVLO','REG_UVLO','passive'),(2,'COMMON','REG_ENABLE','passive'),(3,'OFF','GND','passive')]),
        passive('L1201','XFL4020-152MEC / 1.5uH; saturation acceptance pending','REG_L1','REG_L2','L',
                FP+'Coilcraft_XFL4020'),
        passive('R1201','312k 0.1%','VDD_3V3','REG_FB'),
        passive('R1202','100k 0.1%','REG_FB','GND'),
        passive('R1203','180k 0.1%','VSYS','REG_UVLO'),
        passive('R1204','100k 0.1%','REG_UVLO','GND'),
        passive('R1209','100k 0.1%','REG_ENABLE','GND'),
        passive('C1201','10u 25V X7S','VSYS','GND','C','Capacitor_SMD:C_0805_2012Metric'),
        passive('C1202','10u 25V X7S','VSYS','GND','C','Capacitor_SMD:C_0805_2012Metric'),
        passive('C1203','22u 16V X6S','VDD_3V3','GND','C','Capacitor_SMD:C_0805_2012Metric'),
        passive('C1204','22u 16V X6S','VDD_3V3','GND','C','Capacitor_SMD:C_0805_2012Metric'),
        passive('C1205','22u 16V X6S','VDD_3V3','GND','C','Capacitor_SMD:C_0805_2012Metric'),
        passive('C1206','100n 25V','REG_VAUX','GND','C')]
    data['pages'].insert(1,page('regulation','Regulated main supply and hardware power switch',regulation,[
        'Forced PWM; nominal main output 0.8*(1+312k/100k)=3.296V. PG is open drain on shared reset.',
        'ON: 180k/(100k || 100k) EN divider; nominal rising 3.68V / falling 3.22V. EN also defined during switch transition.',
        'Electrical inventory is unplaced. Quilter must preserve short power loops and return paths.',
        'Manufacturer converter model omits temperature and operating/shutdown current; bench gates remain.']))

    se_pins={1:('ANT_LB','GND','passive'),2:('NC',None,'passive'),
        3:('IO1',None,'bidirectional'),4:('NC',None,'passive'),5:('NC',None,'passive'),
        6:('NC',None,'passive'),7:('NC',None,'passive'),8:('NC',None,'passive'),
        9:('SDA','SE_SDA','bidirectional'),10:('SCL','SE_SCL','input'),
        11:('ENA','SE_ENABLE','input'),12:('VIN','VDD_3V3','power_in'),
        13:('CLK',None,'input'),14:('RST_N','SE_VCC','input'),
        15:('VOUT','SE_VCC','power_out'),16:('IO2',None,'bidirectional'),
        17:('ANT_LA','GND','passive'),18:('VCC','SE_VCC','power_in'),
        19:('VSS','GND','power_in'),20:('NC',None,'passive'),21:('EP','GND','passive')}
    secure=[ic('U11','SE050E2HQ1/Z01Z3Z',FP+'NXP_SOT1969-1',
        [(n,*v) for n,v in se_pins.items()]),
        passive('R1101','4.7k 1%','SE_SDA','VDD_3V3'),
        passive('R1102','4.7k 1%','SE_SCL','VDD_3V3'),
        passive('R1103','100k','SE_ENABLE','GND'),
        passive('C1101','100n 10V','VDD_3V3','GND','C'),
        passive('C1102','100n 10V','SE_VCC','GND','C'),
        passive('C1103','1u 10V','VDD_3V3','GND','C')]
    data['pages'].insert(2,page('secure','One secure element: Ed25519, entropy and protected state',secure,[
        'NXP E variant only. Unused antenna pins grounded. VOUT connects to VCC for deep power-down.',
        'MCU PD12/PD13 use I2C4 at initial 100kHz; 4.7k pull-ups require sink/rise-time check.',
        'ENA defaults low; firmware must initialize/provision a protected channel before key/entropy use.',
        'Private-key, counter, durable-storage and real RNG behavior require chip-backed tests; no silicon simulation claimed.']))

    switches=[]
    for ref,net,enable in [('U1202','RADIO_3V3','RADIO_POWER_EN'),('U401','SD_3V3','SD_POWER_EN')]:
        prefix='RADSW' if ref=='U1202' else 'SDSW'
        pins=[
            (1,'VIN','VDD_3V3','power_in'),(2,'GND','GND','power_in'),
            (3,'ON',enable,'input'),(4,'CT',prefix+'_CT','passive'),
            (5,'QOD',prefix+'_QOD','passive'),(6,'VOUT',net,'power_out')]
        if ref=='U1202':
            pins=[(1,'IN','VDD_3V3','power_in'),(2,'GND','GND','power_in'),
                (3,'EN',enable,'input'),(4,'FAULT_N','RADIO_FAULT_N','open_collector'),
                (5,'ILIM','RADSW_ILIM','passive'),(6,'OUT',net,'power_out')]
        sw=ic(ref,'TPS2553DBVR' if ref=='U1202' else 'TPS22918DBVR',
              'Package_TO_SOT_SMD:SOT-23-6',pins)
        if ref=='U401':
            pg=by_page['microsd'];pg['parts']=[p for p in pg['parts'] if p['ref']!='U401'];pg['parts'].insert(0,sw)
        else:switches.append(sw)
        if ref=='U1202':
            switches.extend([passive('C1207','100n 10V','VDD_3V3','GND','C'),
                passive('R1205','232k 1%','RADSW_ILIM','GND'),
                passive('R1207','100k',enable,'GND'),
                passive('R1210','47k','RADIO_FAULT_N','VDD_3V3'),
                passive('R1211','3.3k','RADIO_3V3','GND')])
        else:
            switches.extend([passive('C1208','10n','SDSW_CT','GND','C'),
                             passive('R1206','100','SDSW_QOD',net)])
    data['pages'].append(page('load-switches','Default-off radio and card power controls',switches,[
        'Radio: TPS2553 current-limited/reverse-blocking switch, 232k ILIM, default disabled, local fault input.',
        'Card: TPS22918 controlled slew/discharge; not overcurrent/reverse-current isolation.',
        'Radio and card interface isolation remains required while their supplies are off.']))

    ap=by_page['audio-power']
    ap['parts']=[p for p in ap['parts'] if p['ref']!='U602']
    ap['parts'].insert(0,ic('U602','TPS7A2028PDBVR','Package_TO_SOT_SMD:SOT-23-5',[
        (1,'IN','VDD_3V3','power_in'),(2,'GND','GND','power_in'),
        (3,'EN','AUD_POWER_EN','input'),(4,'NC',None,'passive'),(5,'OUT','AUD_2V8_REG','power_out')]))
    for x in ap['parts']:
        if x['ref']=='C614':x['nets']['1']='VDD_3V3'
    ap['notes']=['Dedicated 2.8V low-noise audio LDO from regulated main supply, default off.',
        'Codec LDOIN range 1.9-3.6V. Revalidate headphone settings/sequence for 2.8V; no acoustic claim.']
    # Card switch now derives from main 3.3V; remove raw-system input capacitor dependency.
    for x in by_page['microsd']['parts']:
        if x['ref']=='C401' and 'nets' in x:x['nets']['1']='VDD_3V3'
    by_page['microsd']['notes']=['TPS22918 switches regulated main 3.3V; I/O isolation remains default disabled.',
        'Card peak current and real inrush need bench qualification; this switch is not a current limiter.']
    by_page['haptic']['parts'].extend([passive('R810','4.7k','HAPTIC_SDA','VDD_3V3'),
                                     passive('R811','4.7k','HAPTIC_SCL','VDD_3V3')])

    radio=by_page['radio']
    old_radio=next(p for p in radio['parts'] if p['ref']=='U6')
    qfn=[]
    for row in csv.DictReader((NEW/'ble-pin-migration.csv').open()):
        n='49' if row['qfn_terminal']=='EP' else row['qfn_terminal']
        net=row['b0_net'] or None
        if n=='32':net=None  # Nordic QFAA reference C6 is not mounted; DEC2 floats.
        typ='power_in' if row['function'] in ['VDD','VSS'] else 'bidirectional' if row['function'].startswith('P0.') else 'passive'
        qfn.append((n,row['function'],net,typ))
    old_radio.update(ic('U6','nRF52832-QFAA-G-R7',
        'Package_DFN_QFN:QFN-48-1EP_6x6mm_P0.4mm_EP4.66x4.66mm',qfn))
    radio['parts']=[p for p in radio['parts'] if p['ref']!='C206']
    removed.append('C206')
    for p in radio['parts']:
        if p['ref']=='L201':p['value']='3.9nH RF 5%';p['footprint']='Inductor_SMD:L_0402_1005Metric'
        if p['ref']=='C203':p['value']='0.8p C0G 5%';p['footprint']='Capacitor_SMD:C_0402_1005Metric'
    radio.setdefault('notes',[]).extend(['QFAA LDO circuit: DEC2 NC, DCC NC; package-specific RF C=0.8pF/L=3.9nH.',
        'Crystal load and complete antenna matching/keepout require final-layout/RF qualification.'])
    for name in ['microsd','audio-power','radio','haptic']:
        pg=by_page[name];pg.update(page(name,pg['title'],pg['parts'],pg.get('notes',[])))

    # Put probe pads in the electrical schematic so cloud placement can place
    # them too. Keep only the existing four outline mounting holes mechanical.
    probes=[]
    probe_names={'TP4':'REG_ENABLE','TP7':'SE_VCC','TP8':'SE_SCL','TP10':'SE_SDA'}
    for p in data['mechanical']:
        if not p['ref'].startswith('TP') or p['ref']=='TP12':continue
        net=probe_names.get(p['ref'],p['nets']['1'])
        x=ic(p['ref'],'PROBE '+net,p['footprint'],[(1,'PROBE',net,'passive')]);x['in_bom']=False
        probes.append(x)
    data['mechanical']=[p for p in data['mechanical'] if p['ref'].startswith('H')]
    data['pages'].append(page('test-access','Probe access (cloud placement)',probes))
    for i,p in enumerate(probes):p['schematic']=[70+115*(i%4),35+65*(i//4)]
    for pg in data['pages']:
        pg['power_flags']=[n for n in pg.get('power_flags',[]) if not n.startswith(('QI_','NFC_','TR_','OP_','PMIC_'))]
    refs=[p['ref'] for pg in data['pages'] for p in pg['parts']]
    assert len(refs)==len(set(refs))
    assert not any(n.startswith(('QI_','NFC_','TR_','OP_','PMIC_')) for n in data['mcu_signals'].values())
    (NEW/'circuits.json').write_text(json.dumps(data,indent=2)+'\n')
    # Reviewed legacy footprints are copied as library assets, never PCB copper/poses.
    dest=NEW/'VoiceVault_B0.pretty';dest.mkdir(exist_ok=True)
    shutil.copyfile(OLD/'VoiceVault_B0.pretty/Samtec_FTSH-107-01-L-DV.kicad_mod',
                    dest/'Samtec_FTSH-107-01-L-DV.kicad_mod')
    shutil.copyfile(OLD/'LICENSE',NEW/'LICENSE')
    for p in [p for pg in data['pages'] for p in pg['parts']] + data['mechanical']:
        lib,name=p['footprint'].split(':')
        source=OLD/'VoiceVault_B0.pretty'/(name+'.kicad_mod')
        if source.exists():shutil.copyfile(source,dest/source.name)
    old_electrical=32+sum(len(pg['parts']) for pg in original['pages'])
    new_electrical=32+len(refs)
    report=dict(status='CIRCUIT MANIFEST; generated CAD and verification reported separately',
        old_schematic_components=old_electrical,old_total_footprints=old_electrical+len(original['mechanical']),
        new_schematic_components=new_electrical,new_total_footprints=new_electrical+len(data['mechanical']),
        new_probe_pads=len(probes),new_mounting_holes=len(data['mechanical']),
        new_electrical_components=new_electrical-len(probes),
        removed_legacy_references=sorted(set(removed)),
        b0_circuit_sha256=hashlib.sha256((OLD/'circuits.json').read_bytes()).hexdigest(),
        placement='Electrical components unplaced; no placement/routing performed',
        unresolved=['Exact BL-5C pack and holder/harness acceptance','Real chip drivers/provisioning',
                    'Charging/thermal and RF hardware qualification','Final layout, electrical and hardware qualification pending'])
    (NEW/'migration-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k.startswith(('old_','new_'))},indent=2))


if __name__=='__main__':main()
