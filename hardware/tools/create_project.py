#!/usr/bin/env python3
"""Rebuild the native review-stage KiCad carrier from the interface manifest."""
import json
import shutil
import uuid
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'hardware/rev-a'
DESIGN = json.loads((DEST / 'interfaces.json').read_text())
NAMESPACE = uuid.UUID('e3a9dbb0-8277-4d65-8b3a-a213820c7a11')

def uid(name):
    return str(uuid.uuid5(NAMESPACE, name))

def quoted(value):
    return json.dumps(str(value))

def text_effect(size=1.0, extra=''):
    return f'(effects (font (size {size} {size})) {extra})'

root_id = uid('schematic')
footprints = DEST / 'VoiceVault.pretty'
footprints.mkdir(exist_ok=True)
parts = []
for port in DESIGN['ports']:
    item = dict(port)
    item['pins'] = {str(i + 1): net for i, net in enumerate(port['pins'])}
    item['footprint'] = ('Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical'
                         if port.get('columns') == 2 else
                         f'Connector_PinHeader_2.54mm:PinHeader_1x{len(item["pins"]):02}_P2.54mm_Vertical')
    parts.append(item)

parts += [
    dict(ref='R1', name='2.2k mic bias', pins={'1':'MICBIAS','2':'CODEC_MIC'}, at=[140,113], sch=[240,160], footprint='Resistor_SMD:R_0603_1608Metric'),
    dict(ref='R2', name='10k mute sense', pins={'1':'3V3','2':'MIC_SENSE'}, at=[105,112], sch=[240,175], footprint='Resistor_SMD:R_0603_1608Metric'),
    dict(ref='R3', name='47k SD deselect', pins={'1':'3V3','2':'SD_CS'}, at=[110,100], sch=[170,190], footprint='Resistor_SMD:R_0603_1608Metric'),
    dict(ref='R4', name='10k SE deselect', pins={'1':'3V3','2':'SE_CS'}, at=[60,103], sch=[170,205], footprint='Resistor_SMD:R_0603_1608Metric'),
    dict(ref='C1', name='100n 16V', pins={'1':'3V3','2':'GND'}, at=[65,110], sch=[40,210], footprint='Capacitor_SMD:C_0603_1608Metric'),
    dict(ref='C2', name='10u 16V', pins={'1':'3V3','2':'GND'}, at=[70,110], sch=[100,210], footprint='Capacitor_SMD:C_0805_2012Metric'),
    dict(ref='C3', name='22u 16V', pins={'1':'5V_SYS','2':'GND'}, at=[85,110], sch=[40,225], footprint='Capacitor_SMD:C_1210_3225Metric'),
    dict(ref='C4', name='220u 10V HP left', pins={'1':'HP_L_RAW','2':'HP_L'}, at=[163,112], sch=[320,110], footprint='Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'),
    dict(ref='C5', name='220u 10V HP right', pins={'1':'HP_R_RAW','2':'HP_R'}, at=[163,124], sch=[320,125], footprint='Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'),
    dict(ref='SW1', name='Physical mic disconnect', pins={'1':'HEADSET_MIC','2':'CODEC_MIC','3':'GND','4':'GND','5':'MIC_SENSE','6':None}, at=[125,110], sch=[250,205], footprint='Button_Switch_THT:SW_CK_JS202011CQN_DPDT_Straight'),
]

symbols = []
instances = []
for part in parts:
    ref = part['ref']
    pins = part['pins']
    x, y = [round(v / 1.27) * 1.27 for v in part['sch']]
    name = 'VoiceVault:' + ref
    height = max(5.08, 2.54 * (len(pins) - 1) + 5.08)
    pin_defs = []
    for index, (number, net) in enumerate(pins.items()):
        local_y = -2.54 * index
        pin_defs.append(f'(pin passive line (at -7.62 {local_y} 0) (length 2.54) (name {quoted(net or "NC")} {text_effect(.8)}) (number {quoted(number)} {text_effect(.8)}))')
        py = round(y - local_y, 4)
        if net is None or net.startswith('SPARE_'):
            instances.append(f'(no_connect (at {x-7.62} {py}) (uuid "{uid(ref+number+"nc")}"))')
        else:
            instances.append(f'(wire (pts (xy {x-7.62} {py}) (xy {x-17.78} {py})) (stroke (width 0) (type default)) (uuid "{uid(ref+number+"wire")}"))')
            instances.append(f'(label {quoted(net)} (at {x-17.78} {py} 0) {text_effect(.8, "(justify left bottom)")} (uuid "{uid(ref+number+"label")}"))')
    symbols.append(f'''(symbol {quoted(name)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes)
      (property "Reference" {quoted(ref)} (at 0 5.08 0) {text_effect()})
      (property "Value" {quoted(part['name'])} (at 0 2.54 0) {text_effect()})
      (symbol {quoted(ref+'_0_1')} (rectangle (start -5.08 2.54) (end 27.94 {2.54-height}) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol {quoted(ref+'_1_1')} {''.join(pin_defs)}))''')
    instances.append(f'''(symbol (lib_id {quoted(name)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")
      (property "Reference" {quoted(ref)} (at {x+10} {y-7.62} 0) {text_effect()})
      (property "Value" {quoted(part['name'])} (at {x+10} {y-5.08} 0) {text_effect(.9)})
      (property "Footprint" {quoted('VoiceVault:' + part['footprint'].split(':')[1])} (at {x} {y} 0) {text_effect(1,'(hide yes)')})
      (instances (project "voicevault-reva" (path "/{root_id}" (reference {quoted(ref)}) (unit 1)))))''')

notes = [
    (25,15,'VoiceVault Rev A | DK2 cabled carrier | electrical review draft'),
    (25,22,'Reference STM32U5G9ZJT6Q revision Z. Verify actual DBGMCU ID before bench qualification.'),
    (25,28,'Ports are harness connectors. Follow pin map and module wiring guide. Passive port ERC checks connectivity only.'),
    (25,35,'PCB placement is unrouted. Manufacturing release requires electrical, routing, thermal and bench review.'),
    (25,260,'Radio is untrusted. Only 3.3V UART and credit signals cross the boundary. No audio, reset, SWD or update line.'),
    (25,267,'SW1 common pins 2 and 5. MIC OFF connects 2 to 3, grounds codec input, disconnects headset mic and releases sense.'),
    (25,274,'BQ24074 powered from Qi. Battery plugs into charger directly. Select 500mA input limit and 500mA charging.'),
    (25,281,'5V regulator output feeds DK2 CN5.5 only after correct DK2 power selection. Never parallel bench power supplies.'),
]
for x,y,message in notes:
    instances.append(f'(text {quoted(message)} (at {x} {y} 0) {text_effect(1.1,"(justify left)")} (uuid "{uid(message)}"))')
schematic = f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{root_id}") (paper "A3")
 (title_block (title "VoiceVault Rev A serviceable carrier") (rev "A0-review") (company "VoiceVault"))
 (lib_symbols {''.join(symbols)}) {''.join(instances)}
 (sheet_instances (path "/" (page "1"))))'''
(DEST / 'voicevault-reva.kicad_sch').write_text(schematic)

board = pcbnew.BOARD()
board.SetCopperLayerCount(2)
settings = board.GetDesignSettings()
settings.SetBoardThickness(pcbnew.FromMM(1.6))
net_names = sorted({net for part in parts for net in part['pins'].values() if net and not net.startswith('SPARE_')})
net_map = {}
for name in net_names:
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    net_map[name] = net
for part in parts:
    library, footprint_name = part['footprint'].split(':')
    footprint = pcbnew.FootprintLoad('/app/extensions/Library/footprints/' + library + '.pretty', footprint_name)
    if footprint is None:
        raise RuntimeError('Unavailable footprint ' + part['footprint'])
    shutil.copyfile('/app/extensions/Library/footprints/' + library + '.pretty/' + footprint_name + '.kicad_mod', footprints / (footprint_name + '.kicad_mod'))
    footprint.SetFPID(pcbnew.LIB_ID('VoiceVault', footprint_name))
    path = pcbnew.KIID_PATH()
    path.push_back(pcbnew.KIID(root_id))
    path.push_back(pcbnew.KIID(uid(part['ref'])))
    footprint.SetPath(path)
    footprint.SetReference(part['ref'])
    footprint.SetValue(part['name'])
    footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(part['at'][0]),pcbnew.FromMM(part['at'][1])))
    board.Add(footprint)
    for pad in footprint.Pads():
        net_name = part['pins'].get(pad.GetNumber())
        if net_name and not net_name.startswith('SPARE_'):
            pad.SetNet(net_map[net_name])
    footprint.Value().SetVisible(False)
for start,end in [((25,25),(175,25)),((175,25),(175,145)),((175,145),(25,145)),((25,145),(25,25))]:
    line = pcbnew.PCB_SHAPE()
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetLayer(pcbnew.Edge_Cuts)
    line.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start[0]),pcbnew.FromMM(start[1])))
    line.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end[0]),pcbnew.FromMM(end[1])))
    line.SetWidth(pcbnew.FromMM(.05))
    board.Add(line)
for index, (x,y) in enumerate([(29,29),(171,29),(29,141),(171,141)],1):
    hole=pcbnew.FootprintLoad('/app/extensions/Library/footprints/MountingHole.pretty','MountingHole_3.2mm_M3')
    hole.SetReference('H'+str(index)); hole.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    hole.Value().SetVisible(False); hole.Reference().SetVisible(False); board.Add(hole)
for message,x,y,size in [('VOICEVAULT',125,137,2.8),('REV A0 | REVIEW DRAFT | UNROUTED',69,140,1.2),('TRUSTED MCU / DK2',85,29,1.4),('AUDIO',155,30,1.4),('UNTRUSTED RADIO',152,70,1.0),('OFFLINE CARD',110,75,1.0),('SECURE ELEMENTS',72,75,1.1),('POWER / QI',53,120,1.2)]:
    label=pcbnew.PCB_TEXT(board); label.SetText(message); label.SetLayer(pcbnew.F_SilkS)
    label.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size),pcbnew.FromMM(size)))
    label.SetTextThickness(pcbnew.FromMM(.18)); board.Add(label)
board.BuildConnectivity()
pcbnew.SaveBoard(str(DEST / 'voicevault-reva.kicad_pcb'),board)
(DEST / 'VoiceVault.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") ' + ''.join(symbols).replace('VoiceVault:', '') + ')')
(DEST / 'sym-lib-table').write_text('(sym_lib_table (lib (name "VoiceVault") (type "KiCad") (uri "${KIPRJMOD}/VoiceVault.kicad_sym") (options "") (descr "Carrier ports and components")))')
(DEST / 'fp-lib-table').write_text('(fp_lib_table (lib (name "VoiceVault") (type "KiCad") (uri "${KIPRJMOD}/VoiceVault.pretty") (options "") (descr "Used KiCad stock footprints")))')
project = {'meta':{'filename':'voicevault-reva.kicad_pro','version':1},'net_settings':{'classes':[{'name':'Default','clearance':0.25,'track_width':0.25,'via_diameter':0.8,'via_drill':0.4,'description':'Review-stage carrier'}],'meta':{'version':3}}}
(DEST / 'voicevault-reva.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
print(f'Created native KiCad project with {len(parts)} components, {len(net_names)} nets and a 150 x 120 mm board outline. Routing pending.')
