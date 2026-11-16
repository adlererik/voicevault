#!/usr/bin/env python3
"""Read-only C0 MCU package audit; writes evaluation evidence, never CAD.

ST XML inputs must be the pinned versions below. KiCad files are read as text
on the host; this does not load pcbnew or start an editor/router.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from finalize_rev_c_quilter_input import parse, child, children

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '7d1f1514ed5583ec5007ad91236b4e1d377295b1'
HASHES = {
    'bga': '0e1f9cc90b2de934061711ce525709518007fb00caa73cf5ea61f0aa1213b6fe',
    'lqfp': 'b568a8ab9ea2fc7baf33c5848f39e6bb02618ab1f35411e8523f0913eef1a55e',
}
# Intended peripheral functions, independently checked against ST's pin data.
# Remaining connected GPIOs are local controls/status/interrupt inputs.
FUNCTIONS = {
    'LINK_TX': 'USART2_TX', 'LINK_RX': 'USART2_RX',
    'LINK_RTS': 'USART2_RTS', 'LINK_CTS': 'USART2_CTS',
    'MCU_UART_RX': 'USART6_RX', 'MCU_UART_TX': 'USART6_TX',
    'MCU_SWDIO': 'DEBUG_JTMS-SWDIO', 'MCU_SWCLK': 'DEBUG_JTCK-SWCLK',
    'MCU_SWO': 'DEBUG_JTDO-SWO',
    'MCU_HSE_IN': 'RCC_OSC_IN', 'MCU_HSE_OUT': 'RCC_OSC_OUT',
    'MCU_LSE_IN': 'RCC_OSC32_IN', 'MCU_LSE_OUT': 'RCC_OSC32_OUT',
    'SD_SCK_MCU': 'SPI2_SCK', 'SD_MOSI_MCU': 'SPI2_MOSI',
    'SD_MISO_MCU': 'SPI2_MISO',
    'AUD_MCLK': 'SAI1_MCLK_A', 'AUD_WCLK': 'SAI1_FS_A',
    'AUD_BCLK': 'SAI1_SCK_A', 'AUD_DAC_DATA': 'SAI1_SD_A',
    'AUD_ADC_DATA': 'SAI1_SD_B',
    'AUD_SDA': 'I2C2_SDA', 'AUD_SCL': 'I2C2_SCL',
    'LCD_SCK': 'SPI3_SCK', 'LCD_SDO': 'SPI3_MISO', 'LCD_SDI': 'SPI3_MOSI',
    'TOUCH_SDA': 'I2C5_SDA', 'TOUCH_SCL': 'I2C5_SCL',
    'SE_SCL': 'I2C4_SCL', 'SE_SDA': 'I2C4_SDA',
    'BACKLIGHT_PWM': 'TIM4_CH4',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def name(value):
    # Vendor names include reset/debug/oscillator suffixes.
    m = re.match(r'P[A-K]\d+', value)
    return m[0] if m else value


def vendor(path, key):
    assert sha(path) == HASHES[key], f'Unexpected vendor input: {path}'
    root = ET.parse(path).getroot()
    ns = {'s': 'http://dummy.com'}
    pins = {p.get('Position'): {
        'name': name(p.get('Name')), 'vendor_name': p.get('Name'),
        'type': p.get('Type'),
        'functions': sorted({s.get('Name') for s in p.findall('s:Signal', ns)}),
    } for p in root.findall('s:Pin', ns)}
    assert len(pins) == 144
    return root, pins


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bga', type=Path, required=True)
    ap.add_argument('--lqfp', type=Path, required=True)
    ap.add_argument('--symbols', type=Path, required=True)
    ap.add_argument('--footprint', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    board_path = ROOT / 'hardware/rev-c/voicevault-standalone-c0.kicad_pcb'
    circuits_path = ROOT / 'hardware/rev-c/circuits.json'
    # Bind the evaluation to the preserved clean input, not a returned layout.
    protected = [board_path, circuits_path,
                 ROOT / 'hardware/rev-b/voicevault-standalone-b0.kicad_pcb',
                 ROOT / 'hardware/rev-c/local-repair-01/voicevault-standalone-c0.kicad_pcb']
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    br, bga = vendor(args.bga, 'bga')
    lr, lqfp = vendor(args.lqfp, 'lqfp')
    for tag in ['Core', 'Die', 'Ram', 'Flash', 'IONb', 'TrustZone']:
        q = '{http://dummy.com}' + tag
        assert br.findtext(q) == lr.findtext(q), tag
    by_name = collections.defaultdict(list)
    for pin, info in lqfp.items():
        by_name[info['name']].append(pin)

    board = parse(board_path.read_text())
    u1 = next(fp for fp in children(board, 'footprint')
              if any(p[1:3] == ['Reference', 'U1'] for p in children(fp, 'property')))
    nets = {p[1]: child(p, 'net')[1] if child(p, 'net') else ''
            for p in children(u1, 'pad')}
    assert set(nets) == set(bga)
    signal_rows, group_nets = [], collections.defaultdict(set)
    for ball, info in bga.items():
        net = nets[ball]
        if not net or net.startswith('unconnected-'):
            continue
        group_nets[info['name']].add(net)
        if info['type'] == 'Power' or info['name'] == 'VREF+':
            continue
        candidates = by_name[info['name']]
        assert len(candidates) == 1
        pin = candidates[0]
        required = FUNCTIONS.get(net, 'RESET' if info['name'] == 'NRST' else 'GPIO')
        matches = required == 'RESET' or required in lqfp[pin]['functions']
        bga_matches = required == 'RESET' or required in info['functions']
        assert matches == bga_matches, ('package function difference', net)
        signal_rows.append(dict(net=net, gpio=info['name'], bga_ball=ball,
                                lqfp_pin=pin, intended_function=required,
                                function_available=matches,
                                proposed_gpio='PB13' if net == 'SD_SCK_MCU' else info['name'],
                                proposed_lqfp_pin='70' if net == 'SD_SCK_MCU' else pin))
    signal_rows.sort(key=lambda r: r['net'])
    # Fail closed on new/unexplained mismatches; retain the known failed result.
    failures = [r['net'] for r in signal_rows if not r['function_available']]
    assert failures == ['SD_SCK_MCU'], failures
    assert not nets['M10']  # PB13 is currently unused, not a reused control.
    assert lqfp['70']['name'] == 'PB13' and 'SPI2_SCK' in lqfp['70']['functions']
    for row in signal_rows:
        pin = row['proposed_lqfp_pin']
        assert row['intended_function'] == 'RESET' or row['intended_function'] in lqfp[pin]['functions']
    assert len({r['proposed_lqfp_pin'] for r in signal_rows}) == len(signal_rows)

    # Cross-check installed KiCad symbol by every physical pin, not just count.
    symbols = parse(args.symbols.read_text())
    symbol = next(s for s in children(symbols, 'symbol') if s[1] == 'STM32U5G9ZJTxQ')
    kpins = {child(p, 'number')[1]: name(child(p, 'name')[1])
             for unit in children(symbol, 'symbol') for p in children(unit, 'pin')}
    assert kpins == {pin: p['name'] for pin, p in lqfp.items()}
    fp = parse(args.footprint.read_text())
    pads = children(fp, 'pad')
    assert len(pads) == 144 and {p[1] for p in pads} == set(lqfp)
    for pad in pads:
        i = int(pad[1])
        expected = ((-10.6625, -8.75 + .5 * (i - 1)) if i <= 36 else
                    (-8.75 + .5 * (i - 37), 10.6625) if i <= 72 else
                    (10.6625, 8.75 - .5 * (i - 73)) if i <= 108 else
                    (8.75 - .5 * (i - 109), -10.6625))
        assert all(abs(float(v) - e) < 1e-6 for v, e in zip(child(pad, 'at')[1:3], expected))
    courtyard = [child(line, point)[1:] for line in children(fp, 'fp_line')
                 if child(line, 'layer') == ['layer', 'F.CrtYd'] for point in ['start', 'end']]
    bounds = [min(float(p[i]) for p in courtyard) for i in [0, 1]] + [
        max(float(p[i]) for p in courtyard) for i in [0, 1]]

    pin_rows = []
    for pin, info in sorted(lqfp.items(), key=lambda item: int(item[0])):
        balls = [ball for ball, b in bga.items() if b['name'] == info['name']]
        n = group_nets[info['name']]
        assert len(n) <= 1
        pin_rows.append(dict(lqfp_pin=pin, function=info['name'],
                             bga_balls_same_function=';'.join(balls),
                             current_net=next(iter(n), ''),
                             proposed_net='SD_SCK_MCU' if pin == '70' else
                             '' if pin == '29' else next(iter(n), ''),
                             mapping='supply-group-not-one-to-one' if len(balls) > 1 or
                             len(by_name[info['name']]) > 1 else 'unique-function'))
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'hardware/evidence')
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'signal-migration.csv', signal_rows)
    write_csv(out / 'all-lqfp-pins.csv', pin_rows)
    report = {
        'date': '2026-11-16', 'status': 'evaluation-only-candidate-recommended-with-correction',
        'cad_changed': False, 'manufacturing_ready': False,
        'current_part': 'STM32U5G9ZJJ6Q', 'candidate_part': 'STM32U5G9ZJT6Q',
        'vendor_commit': COMMIT, 'vendor_xml_sha256': HASHES,
        'shared_vendor_metadata': {tag: br.findtext('{http://dummy.com}' + tag)
                                  for tag in ['Core', 'Die', 'Ram', 'Flash', 'IONb', 'TrustZone']},
        'protected_input_sha256': before,
        'connected_bga_pins_including_supplies': sum(bool(n) for n in nets.values()),
        'signal_count': len(signal_rows),
        'unavailable_selected_peripheral_functions': failures,
        'proposed_sd_clock_correction': {'from': 'PC0 / BGA K2 / LQFP 29',
                                         'to': 'PB13 / BGA M10 / LQFP 70',
                                         'applied': False},
        'proposed_signal_functions_available': len(signal_rows),
        'kicad_symbol_matches_vendor_all_pins': True,
        'kicad_footprint_pad_count': len(pads),
        'kicad_footprint_perimeter_numbering_and_0_5mm_pitch_checked': True,
        'kicad_footprint_courtyard_bounds_mm': bounds,
        'kicad_footprint': args.footprint.name,
        'kicad_footprint_sha256': sha(args.footprint),
        'kicad_symbol_library_sha256': sha(args.symbols),
        'supply_pin_counts': {label: dict(collections.Counter(p['name'] for p in data.values()
                           if p['type'] == 'Power')) for label, data in [('bga', bga), ('lqfp', lqfp)]},
        'not_checked': ['populated-board mechanical fit', 'placement or routing',
                        'firmware AF register settings, clock tree and DMA allocation',
                        'power integrity, EMC, RF, audio quality, thermal behavior',
                        'actual silicon revision, hardware isolation and security qualification'],
    }
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'signal_count',
        'unavailable_selected_peripheral_functions', 'proposed_signal_functions_available',
        'cad_changed']}, indent=2))


if __name__ == '__main__':
    main()
