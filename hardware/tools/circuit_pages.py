"""Render explicit circuit manifests as native KiCad child sheets.

Pins and connections must come from reviewed manufacturer references. This module
only serializes that data; successful serialization is not an electrical review.
"""
import json
from pathlib import Path


def build_pages(root, destination, project_name, root_id, uid, quote, effects, extract_symbol):
    manifest_path = destination / 'circuits.json'
    if not manifest_path.exists():
        return [], [], []
    manifest = json.loads(manifest_path.read_text())
    source = Path('/app/extensions/Library/symbols/Device.kicad_sym').read_text()
    symbols = {kind: extract_symbol(source, kind) for kind in ['C', 'R', 'L']}
    flag_source = Path('/app/extensions/Library/symbols/power.kicad_sym').read_text()
    flag = extract_symbol(flag_source, 'PWR_FLAG')
    parent_sheets, local_symbols, pcb_parts = [], [], []
    for page_number, page in enumerate(manifest['pages'], 2):
        sheet_id = uid('sheet-' + page['name'])
        page_id = uid('page-' + page['name'])
        instance_path = '/' + root_id + '/' + sheet_id
        filename = 'circuit-' + page['name'] + '.kicad_sch'
        page_symbols, instances = [], []

        def connect(x, y, side, net, identity):
            if net is None:
                instances.append(f'(no_connect (at {x} {y}) (uuid "{uid(identity + "nc")}"))')
                return
            end = round(x + (5.08 if side == 'right' else -5.08), 4)
            instances.append(f'(wire (pts (xy {x} {y}) (xy {end} {y})) '
                             f'(stroke (width 0) (type default)) (uuid "{uid(identity + "wire")}"))')
            angle = 0 if side == 'left' else 180
            instances.append(f'(global_label {quote(net)} (shape bidirectional) (at {end} {y} {angle}) '
                             f'{effects(.8)} (uuid "{uid(identity + "net")}"))')

        for part in page['parts']:
            reference = part['ref']
            # Place electrical endpoints on KiCad's 50-mil grid. Text and PCB
            # placement have separate coordinates and must not be snapped here.
            x, y = [round(round(v / 1.27) * 1.27, 4) for v in part['schematic']]
            symbol_name = part.get('kind', reference + '_circuit')
            if 'pins' in part:
                pins = part['pins']
                count_left = (len(pins) + 1) // 2
                definitions = []
                for index, pin in enumerate(pins):
                    right = index >= count_left
                    row = index - count_left if right else index
                    px, py, angle = (30.48 if right else -30.48), -row * 2.54, (180 if right else 0)
                    definitions.append(f'(pin {pin["type"]} line (at {px} {py} {angle}) (length 5.08) '
                                       f'(name {quote(pin["name"])} {effects(.8)}) '
                                       f'(number {quote(pin["number"])} {effects(.8)}))')
                    connect(round(x + px, 4), round(y - py, 4),
                            'right' if right else 'left', pin['net'], reference + pin['number'])
                height = (count_left - 1) * 2.54 + 5.08
                body = f'''(symbol {quote(symbol_name)} (pin_names (offset .5)) (in_bom yes) (on_board yes)
                  (property "Reference" "U" (at 0 7.62 0) {effects()})
                  (property "Value" {quote(part['value'])} (at 0 5.08 0) {effects()})
                  (symbol {quote(symbol_name + '_0_1')} (rectangle (start -25.4 5.08) (end 25.4 {-height})
                    (stroke (width .254) (type default)) (fill (type background))))
                  (symbol {quote(symbol_name + '_1_1')} {''.join(definitions)}))'''
                pin_nets = {pin['number']: pin['net'] for pin in pins if pin['net'] is not None}
            else:
                # Standard C/R/L symbols are rotated by 90 degrees so their
                # terminals and named net stubs are horizontal and readable.
                kind = part['kind']
                body = symbols[kind]
                # Pin 1 is above the origin in these library symbols. Rotation
                # by 90 degrees maps it to the left of the schematic instance.
                offset = 3.81
                connect(round(x - offset, 4), y, 'left', part['nets']['1'], reference + '1')
                connect(round(x + offset, 4), y, 'right', part['nets']['2'], reference + '2')
                pin_nets = part['nets']
            lib_id = 'VoiceVault_B0:' + symbol_name
            if symbol_name not in [n for n, _ in page_symbols]:
                page_symbols.append((symbol_name, body.replace('(symbol ' + quote(symbol_name),
                                                               '(symbol ' + quote(lib_id), 1)))
                if symbol_name not in ['C', 'R', 'L']:
                    local_symbols.append(body)
            rotation = 0 if 'pins' in part else 90
            fp_name = part['footprint'].split(':')[1]
            instances.append(f'''(symbol (lib_id {quote(lib_id)}) (at {x} {y} {rotation}) (unit 1)
              (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(reference)}")
              (property "Reference" {quote(reference)} (at {x} {y-6.35} 0) {effects()})
              (property "Value" {quote(part['value'])} (at {x} {y-3.81} 0) {effects(.85)})
              (property "Footprint" {quote('VoiceVault_B0:' + fp_name)} (at {x} {y} 0) {effects(1, '(hide yes)')})
              (instances (project {quote(project_name)} (path {quote(instance_path)} (reference {quote(reference)}) (unit 1)))))''')
            pcb_parts.append(dict(ref=reference, library=part['footprint'].split(':')[0],
                                  footprint=fp_name, value=part['value'], position=part['pcb'],
                                  nets=pin_nets, sheet_id=sheet_id))
        if page.get('power_flags'):
            lib_flag = flag.replace('(symbol "PWR_FLAG"', '(symbol "VoiceVault_B0:PWR_FLAG"', 1)
            page_symbols.append(('PWR_FLAG', lib_flag))
            if not any('"PWR_FLAG"' in s for s in local_symbols):
                local_symbols.append(flag)
            for index, net in enumerate(page['power_flags']):
                x, y = 35.56 + index * 66.04, 233.68
                ref = '#FLG' + str(page_number * 100 + index)
                identity = uid(ref)
                connect(x, y, 'left', net, ref)
                instances.append(f'''(symbol (lib_id "VoiceVault_B0:PWR_FLAG") (at {x} {y} 0) (unit 1)
                  (in_bom no) (on_board no) (dnp no) (uuid "{identity}")
                  (property "Reference" {quote(ref)} (at {x} {y+2.54} 0) {effects(.8, '(hide yes)')})
                  (property "Value" "PWR_FLAG" (at {x} {y-5.08} 0) {effects(.8)})
                  (instances (project {quote(project_name)} (path {quote(instance_path)} (reference {quote(ref)}) (unit 1)))))''')
        for index, note in enumerate(page.get('notes', [])):
            notes_y = page.get('notes_y', 330 if page.get('paper') == 'A2' else 246)
            instances.append(f'(text {quote(note)} (at 20 {notes_y+index*6} 0) '
                             f'{effects(1, "(justify left)")} (uuid "{uid(page["name"]+note)}"))')
        text = f'''(kicad_sch (version 20250114) (generator "eeschema") (uuid "{page_id}") (paper {quote(page.get('paper', 'A3'))})
          (title_block (title {quote(page['title'])}) (rev "B0-REVIEW") (company "VoiceVault"))
          (lib_symbols {''.join(s for _, s in page_symbols)}) {''.join(instances)}
          (sheet_instances (path {quote(instance_path)} (page "{page_number}"))))'''
        (destination / filename).write_text(text)
        index = page_number - 2
        sheet_x, y = (440, 30 + index * 23) if index < 14 else (280, 290 + (index - 14) * 23)
        if y + 28 > 400:
            raise RuntimeError('Root sheet index needs a larger page or another hierarchy level.')
        parent_sheets.append(f'''(sheet (at {sheet_x} {y}) (size 125 16) (stroke (width .1524) (type solid))
          (fill (color 0 0 0 0)) (uuid "{sheet_id}")
          (property "Sheetname" {quote(page['title'])} (at {sheet_x} {y-1} 0) {effects(1, '(justify left bottom)')})
          (property "Sheetfile" {quote(filename)} (at {sheet_x} {y+17} 0) {effects(.8, '(justify left top)')})
          (instances (project {quote(project_name)} (path "/{root_id}" (page "{page_number}")))))''')
    return parent_sheets, local_symbols, pcb_parts
