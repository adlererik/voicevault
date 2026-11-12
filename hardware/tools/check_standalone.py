#!/usr/bin/env python3
"""Check actual native draft outputs and report its incomplete release state."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
OUT = ROOT / '.lab-runs/hardware/standalone-b0'
CAD = ['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad']
NAME = 'voicevault-standalone-b0'


def run(arguments, log, timeout=60):
    result = subprocess.run(list(map(str, arguments)), cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    (OUT / log).write_text(result.stdout)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--design-only', action='store_true',
                        help='Exit 0 for passing available checks; retain the blocked manufacturing verdict.')
    parser.add_argument('--spice', action='store_true', help='Also run the 799 B0 ngspice cases and power-allocation study.')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    manifest = json.loads((DESIGN / 'reference/source-manifest.json').read_text())
    hashed = 0
    for item in manifest['files']:
        if 'local_copy' not in item:
            continue
        content = (DESIGN / item['local_copy']).read_bytes()
        if hashlib.sha256(content).hexdigest() != item['sha256']:
            raise RuntimeError('Reference hash mismatch: ' + item['local_copy'])
        hashed += 1
    checks.append(dict(check='Unmodified reference copies', result='pass', files=hashed))
    export = run(CAD + ['sch', 'export', 'netlist', '--format', 'kicadxml', '--output',
                        OUT / 'netlist.xml', DESIGN / (NAME + '.kicad_sch')], 'netlist.log')
    if export.returncode:
        raise RuntimeError('Native schematic netlist export failed')
    tree = ET.parse(OUT / 'netlist.xml').getroot()
    nets = {net.get('name').removeprefix('/'): {(node.get('ref'), node.get('pin'))
             for node in net.findall('node')} for net in tree.findall('./nets/net')}
    # Independently inspect KiCad's export against UM2910 and the published MCU
    # ball assignments. This detects a disconnected or wrongly numbered pin.
    expected = {'MCU_SWDIO': {('J101', '4'), ('U1', 'C10')},
                'MCU_SWCLK': {('J101', '6'), ('U1', 'B11')},
                'MCU_SWO': {('J101', '8'), ('U1', 'D6')},
                'MCU_NRST': {('J101', '12'), ('U1', 'J2'), ('U4', '1'), ('R301', '2'), ('C306', '1')},
                'MCU_UART_RX': {('J101', '13'), ('U1', 'D12')},
                'MCU_UART_TX': {('J101', '14'), ('U1', 'F8')}}
    for name, members in expected.items():
        if nets.get(name) != members:
            raise RuntimeError('Incorrect exported debug connection: ' + name)
    if not {('J101', p) for p in ['5', '7', '11']} <= nets.get('GND', set()):
        raise RuntimeError('Missing debug connector grounds')
    if ('J101', '3') not in nets.get('VDD_3V3', set()):
        raise RuntimeError('Missing target-voltage reference')
    checks.append(dict(check='Exported MCU / STDC14 connections', result='pass',
                       exact_signal_nets=len(expected), grounds_and_vref=True))
    core = {('U1', 'J9'), ('U1', 'D4'), ('U1', 'G3'), ('L1', '2'),
            ('C22', '1'), ('C23', '1'), ('C24', '1'), ('C27', '1'), ('C107', '1')}
    if nets.get('MCU_VDD11') != core:
        raise RuntimeError('Incorrect MCU core supply network or missing VDD11 pins')
    if nets.get('MCU_LX') != {('U1', 'M7'), ('L1', '1')}:
        raise RuntimeError('Incorrect internal SMPS switching-node connection')
    if nets.get('MCU_VBAT_3V3') != {('U1', 'C2'), ('R101', '2'), ('C6', '1'), ('C112', '1')}:
        raise RuntimeError('Incorrect regulated backup supply connection')
    for ref in ['C' + str(n) for n in range(6, 28)] + ['C' + str(n) for n in range(107, 113)]:
        if (ref, '2') not in nets['GND']:
            raise RuntimeError('Unconnected decoupling capacitor ground: ' + ref)
    mcu_part = next(part for part in tree.findall('./libparts/libpart')
                    if part.get('part') == 'STM32U5G9ZJJxQ')
    balls = {pin.get('num'): pin.get('name') for pin in mcu_part.findall('./pins/pin')}
    if len(balls) != 144 or balls.get('J9') != 'VDD11' or balls.get('D4') != 'VDD11':
        raise RuntimeError('Incomplete or incorrect local MCU power-pin symbol')
    checks.append(dict(check='Exported MCU power network', result='pass',
                       mcu_symbol_balls=len(balls), decoupling_capacitors=28,
                       note='Connectivity only; routing, effective capacitance and physical power behavior remain unqualified.'))
    # Independent manufacturer data for the exact package, pinned separately
    # from the KiCad symbol and circuit generator.
    vendor = json.loads((DESIGN / 'reference/st-ufbga144-ballout.json').read_text())
    normalize = lambda name: name.split(' (')[0].split('-')[0]
    expected_balls = {ball: normalize(pin['name']) for ball, pin in vendor['pins'].items()}
    if balls != expected_balls:
        raise RuntimeError('KiCad MCU ballout differs from pinned ST package data')
    by_name = {normalize(pin['name']): pin for pin in vendor['pins'].values()}
    for name, function in vendor['selected_peripheral_functions'].items():
        if function not in by_name[name]['signals']:
            raise RuntimeError('Unsupported selected MCU peripheral function: ' + name)
    checks.append(dict(check='Independent ST ballout/peripheral data', result='pass',
                       balls=len(balls), selected_functions=len(vendor['selected_peripheral_functions']),
                       source_commit=vendor['source_commit']))
    circuit = json.loads((DESIGN / 'circuits.json').read_text())
    expected_count = 32 + sum(len(page['parts']) for page in circuit['pages'])
    components = {p.get('ref'): p for p in tree.findall('./components/comp')}
    if len(components) != expected_count:
        raise RuntimeError('Missing native schematic components')
    inspect = run(['flatpak', 'run', '--user', '--command=python3', 'org.kicad.KiCad',
                   ROOT / 'hardware/tools/inspect_standalone_board.py'], 'pad-inspection.log')
    if inspect.returncode:
        raise RuntimeError('Cannot inspect actual PCB pads')
    board_data = json.loads((OUT / 'board-pads.json').read_text())
    physical = board_data['parts']
    mechanical = {p['ref'] for p in circuit.get('mechanical', [])}
    if {p['reference'] for p in physical} != set(components) | mechanical:
        raise RuntimeError('Schematic and PCB component references disagree')
    actual_pads = {(p['reference'], pad['number']): pad['net'].removeprefix('/')
                   for p in physical for pad in p['pads'] if pad['number']}
    for item in circuit.get('mechanical', []):
        for pin, net in item.get('nets', {}).items():
            if actual_pads.get((item['ref'], pin)) != net:
                raise RuntimeError('Incorrect board-only test access: ' + item['ref'])
    for name, members in {
        'AUD_3V3_REG': {('U602','1'), ('C615','1'), ('R609','1')},
        'AUD_LDOIN_3V3': {('U601','26'), ('C605','1'), ('C606','1'), ('R609','2')},
    }.items():
        if nets.get(name) != members:
            raise RuntimeError('Incorrect dedicated audio supply: ' + name)
    for ref, output in [('U602','AUD_3V3_REG'),('U401','SD_3V3'),('U1001','NFC_3V3')]:
        for pin, net in [('1',output),('3','GND'),('6','VSYS'),('7','GND')]:
            if actual_pads.get((ref,pin)) != net:
                raise RuntimeError('Incorrect WSON LDO pin/thermal pad: ' + ref)
    count = 0
    intentional_nc = 0
    for net, nodes in nets.items():
        if net.startswith('unconnected-') and len(nodes) == 1:
            node = next(iter(nodes))
            if actual_pads.get(node) != '':
                raise RuntimeError('Intentional NC pin has copper-net assignment or no physical pad: ' + repr(node))
            intentional_nc += 1
            continue
        for node in nodes:
            if actual_pads.get(node) != net:
                raise RuntimeError('Schematic/physical copper-pad mismatch: ' + repr(node))
            count += 1
    # Explicit boundary nets: hardware directions and debug separation are
    # checked against actual exported copper, not just a drawing label.
    critical = {'RAD_TX': {('U6', 'F7'), ('U201', '13')},
                'RAD_RX': {('U6', 'G7'), ('U201', '14')},
                'RAD_RTS': {('U6', 'E7'), ('U201', '11')},
                'RAD_CTS': {('U6', 'F6'), ('U201', '12')},
                'RAD_SWDIO': {('U6', 'G1'), ('J102', '2')},
                'RAD_SWDCLK': {('U6', 'F1'), ('J102', '4')},
                'AUD_DAC_DATA': {('U1', 'D3'), ('U601', '4')},
                'AUD_ADC_DATA': {('U1', 'B2'), ('U601', '5')},
                'HEADSET_MIC': {('J601', '1'), ('SW601', '1'), ('D604', '1')}}
    for name, members in critical.items():
        if nets.get(name) != members:
            raise RuntimeError('Incorrect critical boundary connection: ' + name)
    for reference in ['U6', 'J102']:
        for pad in next(p for p in physical if p['reference'] == reference)['pads']:
            if pad['net'].startswith(('MCU_SW', 'TR_', 'OP_', 'AUD_', 'HEADSET_')):
                raise RuntimeError('Forbidden radio/debug connection to trusted interface')
    checks.append(dict(check='Actual copper-pad / schematic and boundary correspondence', result='pass',
                       components=len(components), footprints=len(physical), connected_pad_nodes=count, intentional_nc_pads=intentional_nc,
                       exact_critical_nets=len(critical)))
    if args.spice:
        for script in ['spice_core_sensitivity.py', 'spice_audio_backlight.py', 'power_budget.py']:
            result = subprocess.run([sys.executable, str(ROOT / 'hardware/tools' / script)],
                                    cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=180)
            (OUT / (script + '.log')).write_text(result.stdout)
            if result.returncode:
                raise RuntimeError('Circuit/model check failed: ' + script)
        checks.append(dict(check='ngspice passive/static sensitivity studies', result='pass',
                           simulator='ngspice 47', cases=799,
                           limitation='Ideal sources and static/passive networks; no semiconductor/charging/RF/thermal qualification'))
    erc = run(CAD + ['sch', 'erc', '--exit-code-violations', '--output', OUT / 'erc.rpt',
                     DESIGN / (NAME + '.kicad_sch')], 'erc.log')
    drc = run(CAD + ['pcb', 'drc', '--exit-code-violations', '--format', 'json', '--output',
                     OUT / 'drc.json', DESIGN / (NAME + '.kicad_pcb')], 'drc.log')
    if erc.returncode not in [0, 5] or not (OUT / 'erc.rpt').exists():
        raise RuntimeError('ERC could not inspect the native schematic')
    if drc.returncode not in [0, 5] or not (OUT / 'drc.json').exists():
        raise RuntimeError('DRC could not inspect the native PCB')
    negative = run([sys.executable, ROOT/'hardware/tools/check_antenna_keepout.py'], 'antenna-negative.log')
    if negative.returncode:
        raise RuntimeError('Antenna keepout negative control failed')
    checks.append(dict(check='Antenna keepout negative control', result='pass',
                       rejected=['unrelated track','ground via'], allowed=['RF-feed track'],
                       live_design_unchanged=True, scope='Native DRC rule enforcement, not RF qualification'))
    import_control = run([sys.executable, ROOT/'hardware/tools/check_routing_import.py'],
                         'import-control.log', timeout=240)
    if import_control.returncode:
        raise RuntimeError('Copper import positive/negative control failed')
    checks.append(dict(check='Copper import positive/negative control', result='pass',
                       retained=['allowed existing-net RF connection'],
                       rejected=['unrelated antenna-area route'],
                       original_pads_and_copper_preserved=True, live_design_unchanged=True,
                       scope='Copy-only CAD acceptance guard; not signal-integrity or manufacturing qualification'))
    laser_audit=run([sys.executable,ROOT/'hardware/tools/check_hdi_geometry.py'],'hdi-geometry.log')
    if laser_audit.returncode:
        raise RuntimeError('Laser-via geometry/negative control failed')
    laser_data=json.loads((OUT/'hdi-geometry.json').read_text())
    checks.append(dict(check='Supplemental laser-via geometry',result='pass',
                       laser_vias=laser_data['laser_vias'],negative_control='pass',
                       live_design_unchanged=True,scope=laser_data['scope'],
                       unresolved=laser_data['unresolved']))
    data = json.loads((OUT / 'drc.json').read_text())
    available_failed = erc.returncode != 0 or bool(data.get('violations'))
    checks.append(dict(check='Draft electrical/layout state', result='fail' if available_failed else 'incomplete',
                       erc_exit_code=erc.returncode, drc_exit_code=drc.returncode,
                       unrouted=board_data['unrouted_connections'],
                       unconnected_violations_listed=len(data.get('unconnected_items', [])),
                       tracks_and_vias=board_data['tracks_and_vias'], zones=board_data['zones'],
                       layout_violations=len(data.get('violations', [])),
                       detail='Unrouted circuit connections remain visible; a clean clearance check is not a routed-board release.'))
    blockers = ['Final passive/connector/assembly order codes and procurement acceptance incomplete',
                'Rail current, startup, thermal and fault design review incomplete',
                'Package land-pattern reviews and replacement-antenna tuning incomplete',
                'Stackup, routing, footprint and independent electrical review incomplete',
                'No JLCPCB accepted exact BOM / CPL / DFM or functional-test release',
                'No assembled-board measurements or hardware qualification']
    report = dict(project='VoiceVault standalone B0', manufacturing='BLOCKED',
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  native_components=expected_count, native_nets=len(nets),
                  named_copper_nets=len({v for v in actual_pads.values() if v}),
                  source_hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(set(DESIGN.glob('*.kicad_sch')) |
                                     {DESIGN/(NAME+s) for s in ['.kicad_pcb','.kicad_pro','.kicad_dru']} |
                                     {DESIGN/'circuits.json'})},
                  checks=checks, blockers=blockers,
                  hardware_security_or_functionality_proven=False)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if available_failed else (0 if args.design_only else 2)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print('Draft check failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
