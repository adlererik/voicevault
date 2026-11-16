#!/usr/bin/env python3
"""Native CLI checks and isolated negative controls for the retry RF geometry."""
import json
import re
import subprocess
from pathlib import Path

from check_rev_c import validate
from finalize_rev_c_quilter_input import parse, child, children
from prepare_rev_c_retry import spans, fp_ref, ROOT, SOURCE, DEST, NAME

OUT = ROOT / '.lab-runs/hardware/quilter/2026-11-16-c0-diagnosis/retry-checks'
CONFIG = ROOT / '.lab-cache/kicad-revc-checks'


def drc(board, target):
    subprocess.run(['flatpak', 'run', '--user', f'--env=KICAD_CONFIG_HOME={CONFIG}',
                    '--command=kicad-cli', 'org.kicad.KiCad', 'pcb', 'drc',
                    '--format', 'json', '--output', str(target), str(board)], check=True,
                   timeout=60, capture_output=True, text=True)
    return json.loads(target.read_text())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    board = DEST / f'{NAME}.kicad_pcb'
    text = board.read_text()
    pcb = parse(text)
    actual = {(fp_ref(f), p[1]): child(p, 'net')[1] if child(p, 'net') else ''
              for f in children(pcb, 'footprint') for p in children(f, 'pad') if p[1]}
    assert validate(actual) == 72
    for p in SOURCE.glob('*.kicad_sch'):
        assert p.read_bytes() == (DEST / p.name).read_bytes()
    baseline = drc(board, OUT / 'baseline.json')
    assert not baseline['violations'], baseline['violations'][:2]
    # Construct a minimal isolated fixture. Its test antenna at (30,30) is never
    # an input to Quilter and does not alter any actual electrical placement.
    edits = []
    for a, b in spans(text, 'footprint'):
        f = parse(text[a:b])
        if fp_ref(f) == 'C201':
            # Keep a real GND pad so the native reader resolves the wrong-net
            # control to GND rather than an otherwise absent net name.
            continue
        if fp_ref(f) != 'AE201':
            edits.append((a, b, ''))
            continue
        fragment = text[a:b]
        x, y = map(float, child(f, 'at')[1:3])
        fragment = re.sub(r'\(at\s+420\s+210\)', '(at 30 30)', fragment, count=1)
        fragment = re.sub(r'\(xy\s+([\d.-]+)\s+([\d.-]+)\)',
                          lambda m: f'(xy {float(m[1])-x+30:g} {float(m[2])-y+30:g})', fragment)
        assert child(parse(fragment), 'at')[1:3] == ['30', '30']
        edits.append((a, b, fragment))
    edits += [(a, b, '') for a, b in spans(text, 'zone')]
    for a, b, value in sorted(edits, reverse=True):
        text = text[:a] + value + text[b:]
    cases = [
        ('same-side-feed', 'F.Cu', 'BLE_ANT_FEED', (26.9, 30, 28.55, 30), False),
        ('opposite-side-feed', 'B.Cu', 'BLE_ANT_FEED', (26.9, 30, 28.55, 30), True),
        ('inner-layer-feed', 'In3.Cu', 'BLE_ANT_FEED', (26.9, 30, 28.55, 30), True),
        # Do not touch the antenna pad: KiCad repairs the net of a touching
        # track to match the pad before DRC, obscuring this negative control.
        ('wrong-net-feed', 'F.Cu', 'GND', (26.9, 30, 27.5, 30), True),
        ('outside-corridor', 'F.Cu', 'BLE_ANT_FEED', (27.0, 31, 28.55, 31), True),
    ]
    results = []
    for name, layer, net, (x1,y1,x2,y2), expected in cases:
        path = OUT / f'{name}.kicad_pcb'
        path.with_suffix('.kicad_pro').write_bytes((DEST / f'{NAME}.kicad_pro').read_bytes())
        path.with_suffix('.kicad_dru').write_bytes((DEST / f'{NAME}.kicad_dru').read_bytes())
        track = f'(segment (start {x1} {y1}) (end {x2} {y2}) (width 0.12) (layer "{layer}") (net "{net}"))\n'
        path.write_text(text.rstrip()[:-1] + track + ')\n')
        report = drc(path, OUT / f'{name}.json')
        found = any(v['type'] == 'items_not_allowed' for v in report['violations'])
        assert found == expected, (name, report['violations'])
        results.append(dict(case=name, forbidden_item_detected=found, expected=expected, passed=True))
    summary = dict(status='PASS', native_input_drc_findings=0, critical_pin_nets=72,
                   schematic_files_byte_unchanged=16, rf_controls=results,
                   fabricated_or_routed=False, manufacturing_ready=False)
    (OUT / 'report.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
