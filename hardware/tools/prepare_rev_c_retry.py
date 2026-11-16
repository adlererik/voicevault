#!/usr/bin/env python3
"""Prepare a separate, unrouted Quilter retry without native Python mutations.

This does not choose electrical component positions or create routed copper.
The completed first attempt and its hash-bound input remain untouched.
"""
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

from finalize_rev_c_quilter_input import parse, child, children

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'hardware/rev-c'
DEST = SOURCE / 'quilter-retry-01'
NAME = 'voicevault-standalone-c0'


def spans(text, kind):
    """Lossless direct-child spans in a single S-expression."""
    depth = 0
    start = None
    head = None
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text, re.S):
        token = m[0]
        if token == '(':
            depth += 1
            if depth == 2:
                start, head = m.start(), None
        elif token == ')':
            if depth == 2 and head == kind:
                yield start, m.end()
            depth -= 1
        elif depth == 2 and head is None:
            head = token
    assert depth == 0


def fp_ref(fp):
    return next(p[2] for p in children(fp, 'property') if p[1] == 'Reference')


def main():
    DEST.mkdir(exist_ok=True)
    existing = DEST / f'{NAME}.kicad_pcb'
    if existing.exists():
        old = parse(existing.read_text())
        assert not any(children(old, k) for k in ['segment', 'via', 'arc']), 'Preserve returned routing'
        assert all(float(child(f, 'at')[1]) > 100 for f in children(old, 'footprint')
                   if not fp_ref(f).startswith('H')), 'Preserve returned placement'
    source = SOURCE / f'{NAME}.kicad_pcb'
    original = source.read_text()
    pcb = parse(original)
    assert not any(children(pcb, k) for k in ['segment', 'via', 'arc'])
    assert len(children(pcb, 'footprint')) == 213
    assert all(child(z, 'keepout') for z in children(pcb, 'zone'))
    assert all(float(child(f, 'at')[1]) > 100 and not children(f, 'locked')
               for f in children(pcb, 'footprint') if not fp_ref(f).startswith('H'))

    matches = [(a, b) for a, b in spans(original, 'footprint')
               if fp_ref(parse(original[a:b])) == 'AE201']
    assert len(matches) == 1
    a, b = matches[0]
    antenna = original[a:b]
    exclusions = [antenna[x:y] for x, y in spans(antenna, 'zone')
                  if child(parse(antenna[x:y]), 'name')[1] == 'VV_ANTENNA_NO_COPPER']
    assert len(exclusions) == 1
    other = exclusions[0]
    other = re.sub(r'\(layers[^)]*\)', '(layers "B.Cu" "In1.Cu" "In2.Cu" "In3.Cu" "In4.Cu")', other, count=1)
    other = re.sub(r'\(uuid\s+[^)]+\)', f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, "voicevault/rev-c/retry01/antenna-other-layers")}")', other, count=1)
    other = other.replace('VV_ANTENNA_NO_COPPER', 'VV_ANTENNA_OTHER_LAYERS')
    other = other.replace('(tracks allowed)', '(tracks not_allowed)')
    other = other.replace('(footprints not_allowed)', '(footprints allowed)')
    assert child(parse(other), 'layers')[1:] == ['B.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu']
    updated = original[:a] + antenna[:-1] + '\n' + other + '\n)' + original[b:]
    after = parse(updated)
    for before_fp, after_fp in zip(children(pcb, 'footprint'), children(after, 'footprint')):
        assert fp_ref(before_fp) == fp_ref(after_fp)
        # Only the antenna's rule-area list changes; all placements/pads/nets stay exact.
        assert [x for x in before_fp if not (isinstance(x, list) and x and x[0] == 'zone')] == [
            x for x in after_fp if not (isinstance(x, list) and x and x[0] == 'zone')]
    assert len(children(next(f for f in children(after, 'footprint') if fp_ref(f) == 'AE201'), 'zone')) == 3
    for p in SOURCE.glob('*.kicad_sch'):
        shutil.copy2(p, DEST / p.name)
    (DEST / source.name).write_text(updated)
    project = json.loads((SOURCE / f'{NAME}.kicad_pro').read_text())
    # Published standard JLCPCB inner via-hole-to-copper/track minimum is 0.20mm.
    # Keep the original report with 0.25mm separately; this is an explicit study rule.
    project['board']['design_settings']['rules']['min_hole_clearance'] = 0.20
    (DEST / f'{NAME}.kicad_pro').write_text(json.dumps(project, indent=2) + '\n')
    shutil.copytree(SOURCE / 'VoiceVault_B0.pretty', DEST / 'VoiceVault_B0.pretty', dirs_exist_ok=True)
    library_path = DEST / 'VoiceVault_B0.pretty/Johanson_2450AT18x100.kicad_mod'
    library = library_path.read_text()
    local_other = [library[x:y] for x, y in spans(library, 'zone')
                   if child(parse(library[x:y]), 'name')[1] == 'VV_ANTENNA_NO_COPPER'][0]
    local_other = re.sub(r'\(layers[^)]*\)', '(layers "B.Cu" "In1.Cu" "In2.Cu" "In3.Cu" "In4.Cu")', local_other, count=1)
    local_other = re.sub(r'\(uuid\s+[^)]+\)', f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, "voicevault/rev-c/retry01/antenna-other-layers")}")', local_other, count=1)
    local_other = local_other.replace('VV_ANTENNA_NO_COPPER', 'VV_ANTENNA_OTHER_LAYERS').replace('(tracks allowed)', '(tracks not_allowed)').replace('(footprints not_allowed)', '(footprints allowed)')
    library_path.write_text(library.rstrip()[:-1] + '\n' + local_other + '\n)\n')
    (DEST / 'fp-lib-table').write_bytes((SOURCE / 'fp-lib-table').read_bytes())
    (DEST / 'sym-lib-table').write_text((SOURCE / 'sym-lib-table').read_text().replace('${KIPRJMOD}/', '${KIPRJMOD}/../'))
    # Zone fills are excluded by native keepout geometry. A zone object's outline
    # can intersect an exclusion despite its filled copper respecting the cutout;
    # do not mistake that outline for a filled-copper intrusion.
    rules = '''(version 1)
(rule "VV antenna: only antenna feed in exclusion"
 (condition "A.intersectsArea('VV_ANTENNA_NO_COPPER') && A.NetName != 'BLE_ANT_FEED'")
 (constraint disallow track via micro_via buried_via))
'''
    (DEST / f'{NAME}.kicad_dru').write_text(rules)
    report = dict(
        source_board_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        retry_board_sha256=hashlib.sha256(updated.encode()).hexdigest(),
        component_positions_values_pads_and_nets_unchanged=True,
        footprints=213, electrical_components=196, tracks=0, vias=0, copper_pours=0,
        antenna_change='A third footprint-attached keepout blocks ALL tracks on the opposite outer layer and every inner layer. The same-side feed corridor remains. This follows footprint flips; same-side RF routing is required on either outer face.',
        native_rule_change='Native geometry excludes zone fills. Custom net rule checks routed items, avoiding false findings against whole-zone outlines.',
        hole_clearance_mm=0.20,
        hole_clearance_source='https://jlcpcb.com/capabilities/pcb-capabilities',
        planned_cloud_changes=['Force automatic BGA fanout for U1', 'Add RF and converter proximity requirements', 'Retain reviewed 6-layer ordinary-via stack and circuit settings'],
        fabrication_ready=False,
    )
    (DEST / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
