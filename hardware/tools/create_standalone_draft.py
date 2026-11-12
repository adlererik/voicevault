#!/usr/bin/env python3
"""Create the hierarchical standalone circuit and unrouted rectangular PCB draft.

Run inside the KiCad Flatpak Python runtime. This is intentionally an incomplete
circuit. It never exports Gerbers or assembly placements. Existing CAD files are
preserved unless --replace is explicitly supplied.
"""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import uuid

import pcbnew

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'hardware/rev-b'
NAMESPACE = uuid.UUID('a84b4cfe-8481-4292-b777-dc175451f1b4')
LIB = Path('/app/extensions/Library')


def uid(name):
    return str(uuid.uuid5(NAMESPACE, name))


def quote(value):
    return json.dumps(str(value))


def effects(size=1, extra=''):
    return f'(effects (font (size {size} {size})) {extra})'


def extract_symbol(source, name):
    start = source.index('(symbol ' + quote(name))
    depth = 0
    in_string = escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError('Unterminated source symbol')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--preserve-layout', type=Path)
    parser.add_argument('--schematic-only', action='store_true',
                        help='Regenerate sheets/library only; preserve existing project, PCB, rules and routed work.')
    args = parser.parse_args()
    name = 'voicevault-standalone-b0'
    if not (args.replace or args.schematic_only) and any((DEST / (name + suffix)).exists()
                                for suffix in ['.kicad_pro', '.kicad_sch', '.kicad_pcb']):
        raise SystemExit('CAD already exists; preserve edits or explicitly use --replace.')
    existing = DEST / (name + '.kicad_pcb')
    if existing.exists() and not args.schematic_only:
        previous = pcbnew.LoadBoard(str(existing))
        if list(previous.GetTracks()) or list(previous.Zones()):
            raise SystemExit('Preserve existing copper/rule areas. Use --schematic-only and explicitly merge PCB changes.')
    DEST.mkdir(parents=True, exist_ok=True)
    library = (LIB / 'symbols/MCU_ST_STM32U5.kicad_sym').read_text()
    symbol = extract_symbol(library, 'STM32U5G9ZJJxQ')
    # The installed library omits VDD11 balls J9 and D4. Restore both from
    # DS14102 Rev 5, UFBGA144 ballout (Figure 10 / Table 27).
    new_pins = []
    for ball, x in [('J9', -22.86), ('D4', -20.32)]:
        new_pins.append(f'(pin power_in line (at {x} 91.44 270) (length 5.08) '
                        f'(name "VDD11" {effects(1.27)}) (number "{ball}" {effects(1.27)}))')
    original_unit = extract_symbol(symbol, 'STM32U5G9ZJJxQ_1_1')
    symbol = symbol.replace(original_unit, original_unit[:-1] + ''.join(new_pins) + ')', 1)
    symbol = symbol.replace('"STM32U5G9ZJJxQ"', '"VoiceVault_B0:STM32U5G9ZJJxQ"', 1)
    symbol = symbol.replace('Package_BGA:UFBGA-144_10x10mm_Layout12x12_P0.8mm',
                            'VoiceVault_B0:UFBGA-144_10x10mm_Layout12x12_P0.8mm')
    # DS14102 describes VLXSMPS as the internal SMPS switch output. The stock
    # library's power-input type is incorrect for electrical-rule propagation.
    symbol = re.sub(r'\(pin power_in line(?=\s*\(at[^)]*\)\s*\(length[^)]*\)\s*\(name "VLXSMPS")',
                    '(pin power_out line', symbol)
    pins = []
    pattern = (r'\(pin \w+ \w+\s*\(at ([\-\d.]+) ([\-\d.]+) ([\-\d.]+)\)'
               r'.*?\(name "([^"]*)".*?\(number "([^"]+)"')
    for match in re.finditer(pattern, symbol, re.S):
        pins.append(dict(x=float(match[1]), y=float(match[2]), angle=float(match[3]),
                         name=match[4], number=match[5]))
    assert len(pins) == 144 and len({pin['number'] for pin in pins}) == 144
    # STDC14 is UM2910 Rev 4, table 4. The UART labels describe TARGET direction.
    debug = {'3': 'VDD_3V3', '4': 'MCU_SWDIO', '5': 'GND', '6': 'MCU_SWCLK',
             '7': 'GND', '8': 'MCU_SWO', '11': 'GND', '12': 'MCU_NRST',
             '13': 'MCU_UART_RX', '14': 'MCU_UART_TX'}
    mcu_signals = {'PA13': 'MCU_SWDIO', 'PA14': 'MCU_SWCLK', 'PB3': 'MCU_SWO',
                   'NRST': 'MCU_NRST', 'PC8': 'MCU_UART_RX', 'PC9': 'MCU_UART_TX'}
    circuits_file = DEST / 'circuits.json'
    if circuits_file.exists():
        mcu_signals.update(json.loads(circuits_file.read_text()).get('mcu_signals', {}))
    absent = set(mcu_signals) - {pin['name'] for pin in pins}
    if absent:
        raise RuntimeError('Signals assigned to pins absent from the selected UFBGA144 part: ' + ', '.join(sorted(absent)))
    expected = {'PA13': 'C10', 'PA14': 'B11', 'PB3': 'D6', 'NRST': 'J2',
                'PC8': 'D12', 'PC9': 'F8'}
    for pin_name, ball in expected.items():
        assert next(pin for pin in pins if pin['name'] == pin_name)['number'] == ball
    root_id = uid('schematic')
    instances, connected, mcu_nets = [], set(), {}

    def wire_label(x, y, angle, net, identifier, distance=7.62):
        end_x = round(x - math.cos(math.radians(angle)) * distance, 4)
        end_y = round(y + math.sin(math.radians(angle)) * distance, 4)
        key = (x, y, net)
        if key in connected:
            return
        connected.add(key)
        instances.append(f'(wire (pts (xy {x} {y}) (xy {end_x} {end_y})) '
                         f'(stroke (width 0) (type default)) (uuid "{uid(identifier + "wire")}"))')
        label_angle = 90 if angle in [90, 270] else 0
        instances.append(f'(global_label {quote(net)} (shape bidirectional) (at {end_x} {end_y} {label_angle}) '
                         f'{effects(.85, "(justify left bottom)")} (uuid "{uid(identifier + "label")}"))')

    for pin in pins:
        net = mcu_signals.get(pin['name'])
        if pin['name'] in ['VDD', 'VDDIO2', 'VDDDSI', 'VDDUSB', 'VDDA', 'VDDSMPS', 'VREF+']:
            net = 'VDD_3V3'
        if pin['name'] in ['VDD11', 'VDD11DSI']:
            net = 'MCU_VDD11'
        if pin['name'] == 'VLXSMPS':
            net = 'MCU_LX'
        if pin['name'] == 'VBAT':
            net = 'MCU_VBAT_3V3'
        if pin['name'] in ['VSS', 'VSSA', 'VSSDSI', 'VSSSMPS']:
            net = 'GND'
        if net:
            mcu_nets[pin['number']] = net
            wire_label(round(110.49 + pin['x'], 4), round(139.7 - pin['y'], 4),
                       pin['angle'], net, 'U1' + pin['number'])
        else:
            instances.append(f'(no_connect (at {round(110.49 + pin["x"], 4)} {round(139.7 - pin["y"], 4)}) '
                             f'(uuid "{uid("U1-unused-" + pin["number"])}"))')
    instances.append(f'''(symbol (lib_id "VoiceVault_B0:STM32U5G9ZJJxQ") (at 110.49 139.7 0)
      (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid('U1')}")
      (property "Reference" "U1" (at 90 51.1 0) {effects()})
      (property "Value" "STM32U5G9ZJJ6Q" (at 125 51.1 0) {effects()})
      (property "Footprint" "VoiceVault_B0:UFBGA-144_10x10mm_Layout12x12_P0.8mm" (at 110 140 0) {effects(1, '(hide yes)')})
      (instances (project "{name}" (path "/{root_id}" (reference "U1") (unit 1)))))''')
    header_pins = []
    for number in range(1, 15):
        net = debug.get(str(number))
        y = -2.54 * (number - 1)
        header_pins.append(f'(pin passive line (at -7.62 {y} 0) (length 2.54) '
                           f'(name {quote(net or "NC")} {effects(.8)}) (number "{number}" {effects(.8)}))')
        x, y = 242.57, round(59.69 - y, 4)
        if net:
            wire_label(x, y, 0, net, 'J101' + str(number))
        else:
            instances.append(f'(no_connect (at {x} {y}) (uuid "{uid("NC" + str(number))}"))')
    header = f'''(symbol "VoiceVault_B0:STDC14" (pin_names (offset .5)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 5.08 0) {effects()})
      (property "Value" "STDC14 SWD + UART" (at 0 2.54 0) {effects()})
      (symbol "STDC14_0_1" (rectangle (start -5.08 2.54) (end 25.4 -35.56)
        (stroke (width .254) (type default)) (fill (type background))))
      (symbol "STDC14_1_1" {''.join(header_pins)}))'''
    header_fp = 'Samtec_FTSH-107-01-L-DV'
    instances.append(f'''(symbol (lib_id "VoiceVault_B0:STDC14") (at 250.19 59.69 0)
      (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid('J101')}")
      (property "Reference" "J101" (at 260 52.38 0) {effects()})
      (property "Value" "FTSH-107-01-L-DV / STDC14" (at 260 54.92 0) {effects(.9)})
      (property "Footprint" "VoiceVault_B0:{header_fp}" (at 250 60 0) {effects(1, '(hide yes)')})
      (instances (project "{name}" (path "/{root_id}" (reference "J101") (unit 1)))))''')
    # Decoupling and internal SMPS draft. Values retain source references, with
    # explicit ST-specification changes below. Exact passive MPNs remain open.
    passives = []
    for number in range(6, 28):
        value = '4.7u 10V' if number in [6, 15, 19] else '100n 10V'
        net = 'VDD_3V3'
        if number == 6:
            net = 'MCU_VBAT_3V3'
        if number in [22, 23, 24, 27]:
            net = 'MCU_VDD11'
        if number == 25:
            value = '10u 10V'
        if number == 27:
            value = '2.2u 10V'
        passives.append(dict(ref='C' + str(number), value=value, kind='C',
                             nets={'1': net, '2': 'GND'}))
    for ref, value, net in [('C107', '2.2u 10V', 'MCU_VDD11'),
                             ('C108', '10u 10V', 'VDD_3V3'),
                             ('C109', '4.7u 10V', 'VDD_3V3'),
                             ('C110', '1u 10V', 'VDD_3V3'),
                             ('C111', '1u 10V', 'VDD_3V3'),
                             ('C112', '100n 10V', 'MCU_VBAT_3V3')]:
        passives.append(dict(ref=ref, value=value, kind='C', nets={'1': net, '2': 'GND'}))
    passives += [dict(ref='L1', value='2.2uH ISAT>0.5A DCR<0.2R', kind='L',
                      nets={'1': 'MCU_LX', '2': 'MCU_VDD11'}),
                 dict(ref='R101', value='0R - VBAT from regulated rail', kind='R',
                      nets={'1': 'VDD_3V3', '2': 'MCU_VBAT_3V3'})]
    device_source = (LIB / 'symbols/Device.kicad_sym').read_text()
    extra_symbols = []
    for kind in ['C', 'L', 'R']:
        body = extract_symbol(device_source, kind)
        extra_symbols.append(body.replace('(symbol "' + kind + '"',
                                           '(symbol "VoiceVault_B0:' + kind + '"', 1))
    passive_pins = {}
    for kind, body in zip(['C', 'L', 'R'], extra_symbols):
        passive_pins[kind] = [dict(x=float(m[1]), y=float(m[2]), angle=float(m[3]), number=m[5])
                             for m in re.finditer(pattern, body, re.S)]
        assert {p['number'] for p in passive_pins[kind]} == {'1', '2'}, kind
    for index, part in enumerate(passives):
        x = 195.58 + (index % 10) * 20.32
        y = 203.2 + (index // 10) * 15.24
        part['footprint_library'] = 'Capacitor_SMD' if part['kind'] == 'C' else ('Inductor_SMD' if part['kind'] == 'L' else 'Resistor_SMD')
        part['footprint'] = {'C': 'C_0402_1005Metric', 'L': 'L_0805_2012Metric', 'R': 'R_0402_1005Metric'}[part['kind']]
        override = json.loads(circuits_file.read_text()).get('root_parts', {}).get(part['ref'], {}) if circuits_file.exists() else {}
        if 'footprint' in override:
            part['footprint_library'], part['footprint'] = override['footprint'].split(':')
        if 'value' in override:
            part['value'] = override['value']
        # Positions are placement placeholders, to be moved adjacent to their
        # actual BGA supply balls during routing. They are not routed decoupling.
        part['position'] = (48 + (index % 10) * 2.1, 36 + (index // 10) * 2)
        if part['ref'] == 'L1':
            part['position'] = (60, 54)
        for pin in passive_pins[part['kind']]:
            wire_label(round(x + pin['x'], 4), round(y - pin['y'], 4), pin['angle'],
                       part['nets'][pin['number']], part['ref'] + pin['number'], distance=2.54)
        instances.append(f'''(symbol (lib_id "VoiceVault_B0:{part['kind']}") (at {x} {y} 0)
          (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(part['ref'])}")
          (property "Reference" {quote(part['ref'])} (at {x+2.54} {y-1.27} 0) {effects(.8)})
          (property "Value" {quote(part['value'])} (at {x+2.54} {y+1.27} 0) {effects(.65)})
          (property "Footprint" "VoiceVault_B0:{part['footprint']}" (at {x} {y} 0) {effects(1, '(hide yes)')})
          (instances (project "{name}" (path "/{root_id}" (reference {quote(part['ref'])}) (unit 1)))))''')
    from circuit_pages import build_pages
    sheets, child_symbols, child_parts = build_pages(ROOT, DEST, name, root_id, uid, quote, effects, extract_symbol)
    instances.extend(sheets)
    for x, y, message in [
        (25, 15, 'VOICEVAULT B0 | STANDALONE SECURE AUDIO ENDPOINT | CIRCUIT REVIEW'),
        (25, 23, 'NOT FOR FABRICATION. Hierarchical circuits under review; all PCB routing remains incomplete.'),
        (190, 125, 'STDC14 pin 3 is target voltage sense, NOT a power input.'),
        (190, 133, 'Use an external STLINK-V3MINIE. Target supply is separate.'),
        (190, 141, 'Pins 13/14 use TARGET RX/TX naming. UART6 on PC8/PC9.'),
        (190, 158, 'Power, radio, secure elements, controls and offline-update interfaces: see child sheets.'),
        (190, 166, 'Main debug and radio debug are separate; probes measure target voltage only.'),
        (190, 174, 'Display/touch, haptic, Qi and NFC are on separate reviewed-source circuit sheets.'),
        (190, 182, 'Audio codec, CTIA headset, physical microphone disconnect and microSD are additions.'),
        (25, 258, 'Prototype has open debug access and public diagnostic material. Physical security remains unqualified.'),
        (25, 266, 'Safe 7 source: TS7 rev_D, STM32U5G9ZJJ6Q / UFBGA144. New PCB outline is provisional 70 x 45 mm.'),
    ]:
        instances.append(f'(text {quote(message)} (at {x} {y} 0) {effects(1, "(justify left)")} (uuid "{uid(message)}"))')
    (DEST / (name + '.kicad_sch')).write_text(f'''(kicad_sch (version 20250114) (generator "eeschema")
      (uuid "{root_id}") (paper "A2") (title_block (title "VoiceVault B0 - standalone circuit review")
      (rev "B0-INCOMPLETE") (company "VoiceVault"))
      (lib_symbols {symbol} {header} {''.join(extra_symbols)}) {''.join(instances)} (sheet_instances (path "/" (page "1"))))''')
    local_lib = (symbol + header + ''.join(extra_symbols) + ''.join(child_symbols)).replace('(symbol "VoiceVault_B0:', '(symbol "')
    (DEST / 'VoiceVault_B0.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") ' + local_lib + ')')
    (DEST / 'sym-lib-table').write_text('(sym_lib_table (lib (name "VoiceVault_B0") (type "KiCad") (uri "${KIPRJMOD}/VoiceVault_B0.kicad_sym") (options "") (descr "MCU and development connector")))')
    (DEST / 'fp-lib-table').write_text('(fp_lib_table (lib (name "VoiceVault_B0") (type "KiCad") (uri "${KIPRJMOD}/VoiceVault_B0.pretty") (options "") (descr "Stock footprint starting points - connector MPN pending")))')
    if args.schematic_only:
        print('Regenerated schematic/library only. PCB, project and rule areas preserved; merge/check PCB changes explicitly.')
        return
    project = {'meta': {'filename': name + '.kicad_pro', 'version': 1},
               'net_settings': {'meta': {'version': 3}, 'classes': [
                   {'name': 'Default', 'clearance': .1, 'track_width': .15,
                    'via_diameter': .45, 'via_drill': .2,
                    'description': 'Review candidate within published HDI line/space capability; stackup/via process not released'}]},
               'board': {'design_settings': {'rules': {
                   'min_clearance': .1, 'min_track_width': .1,
                   'min_via_diameter': .45, 'min_through_hole_diameter': .2,
                   'min_via_annular_width': .1}}}}
    (DEST / (name + '.kicad_pro')).write_text(json.dumps(project, indent=2) + '\n')
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(6)
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.0))
    nets = {}
    for net_name in sorted(set(debug.values()) | set(mcu_nets.values()) |
                           {n for part in child_parts for n in part['nets'].values()}):
        net = pcbnew.NETINFO_ITEM(board, net_name)
        board.Add(net)
        nets[net_name] = net
    footprints = DEST / 'VoiceVault_B0.pretty'
    footprints.mkdir(exist_ok=True)
    pcb_parts = [
        ('U1', 'Package_BGA', 'UFBGA-144_10x10mm_Layout12x12_P0.8mm', 'STM32U5G9ZJJ6Q', (58, 47), mcu_nets),
        ('J101', 'VoiceVault_B0', header_fp, 'FTSH-107-01-L-DV / STDC14', (32, 48), debug),
    ] + [(p['ref'], p['footprint_library'], p['footprint'], p['value'], p['position'], p['nets']) for p in passives]
    pcb_parts += [(p['ref'], p['library'], p['footprint'], p['value'], p['position'], p['nets']) for p in child_parts]
    mechanical = json.loads(circuits_file.read_text()).get('mechanical', []) if circuits_file.exists() else []
    pcb_parts += [(p['ref'], p['footprint'].split(':')[0], p['footprint'].split(':')[1],
                   p['value'], p['position'], p.get('nets', {})) for p in mechanical]
    preserved = json.loads(args.preserve_layout.read_text()) if args.preserve_layout else {}
    for ref, library_name, fp_name, value, position, pin_nets in pcb_parts:
        if ref in preserved:
            position = (preserved[ref]['x'], preserved[ref]['y'])
        source = footprints if library_name == 'VoiceVault_B0' else LIB / ('footprints/' + library_name + '.pretty')
        if source != footprints:
            shutil.copyfile(source / (fp_name + '.kicad_mod'), footprints / (fp_name + '.kicad_mod'))
        fp = pcbnew.FootprintLoad(str(source), fp_name)
        if fp is None:
            raise RuntimeError('Missing footprint ' + fp_name)
        fp.SetFPID(pcbnew.LIB_ID('VoiceVault_B0', fp_name))
        path = pcbnew.KIID_PATH()
        path.push_back(pcbnew.KIID(root_id))
        child = next((p for p in child_parts if p['ref'] == ref), None)
        if child:
            path.push_back(pcbnew.KIID(child['sheet_id']))
        path.push_back(pcbnew.KIID(uid(ref)))
        fp.SetPath(path)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.Value().SetVisible(False)
        if ref.startswith(('C', 'R')):
            # Dense 0402 reference designators belong on the assembly drawing;
            # default silkscreen text would collide with adjacent copper.
            fp.Reference().SetVisible(False)
        fp.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in position)))
        # KiCad 10 resolves layer pairs through the parent board during Flip.
        # Flipping a detached footprint can crash the native library.
        board.Add(fp)
        if ref in preserved and preserved[ref].get('back', False):
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if ref in ['U1', 'L1']:
            label_position = (74, 47) if ref == 'U1' else (60, 57.5)
            fp.Reference().SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in label_position)))
        if ref in preserved:
            fp.SetOrientationDegrees(preserved[ref]['angle'])
        if ref in {p['ref'] for p in mechanical}:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        for pad in fp.Pads():
            if pad.GetNumber() in pin_nets:
                pad.SetNet(nets[pin_nets[pad.GetNumber()]])
    for start, end in [((25, 25), (95, 25)), ((95, 25), (95, 70)),
                       ((95, 70), (25, 70)), ((25, 70), (25, 25))]:
        line = pcbnew.PCB_SHAPE()
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetStart(pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in start)))
        line.SetEnd(pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in end)))
        line.SetWidth(pcbnew.FromMM(.05))
        board.Add(line)
    for message, x, y, size in [('VOICEVAULT B0 DEV', 60, 30, 1.5),
                               ('INCOMPLETE - DO NOT FABRICATE', 60, 65, 1),
                               ('CIRCUIT REVIEW - UNROUTED', 60, 68, .8)]:
        label = pcbnew.PCB_TEXT(board)
        label.SetText(message)
        label.SetLayer(pcbnew.F_SilkS)
        label.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        label.SetTextThickness(pcbnew.FromMM(.15))
        board.Add(label)
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(DEST / (name + '.kicad_pcb')), board)
    print(f'Created hierarchical circuit draft with {len(pcb_parts)} footprints. No manufacturing outputs generated.')


if __name__ == '__main__':
    main()
