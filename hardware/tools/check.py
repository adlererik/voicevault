#!/usr/bin/env python3
"""Run available CAD/circuit/negative checks. Hardware qualification stays blocked."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / '.lab-runs/hardware/latest')
parser.add_argument('--design-only', action='store_true', help='Exit based on available design checks, preserving blocked hardware status')
args = parser.parse_args()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
results = []


def command(argv, log, cwd=ROOT, timeout=120, env=None):
    process = subprocess.run(list(map(str, argv)), cwd=cwd, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, env=env)
    (OUT / log).write_text(process.stdout)
    return process


def record(name, status, detail):
    results.append(dict(name=name, status=status, detail=detail))
    print(f'{status.upper()} {name} - {detail}', flush=True)


def spice_case(circuit, parameters, label, bounds):
    directory = OUT / label
    directory.mkdir(exist_ok=True)
    source = (ROOT / 'hardware/spice' / (circuit + '.cir')).read_text()
    for key, value in parameters.items():
        source = re.sub(r'\b' + re.escape(key) + r'=[^\s]+', f'{key}={value}', source)
    (directory / 'input.cir').write_text(source)
    result = command([ROOT / '.lab-cache/bin/ngspice', '-b', '-o', directory / 'ngspice.log', directory / 'input.cir'], label + '.log', cwd=directory)
    log = (directory / 'ngspice.log').read_text()
    values = {}
    for key in bounds:
        match = re.search(r'^' + re.escape(key) + r'\s*=\s*([-+\d.eE]+)', log, re.M)
        if match is None:
            raise RuntimeError(label + ' missing measurement ' + key)
        value = float(match.group(1))
        low, high = bounds[key]
        if not low <= value <= high:
            raise RuntimeError(f'{label} {key}={value} outside [{low}, {high}]')
        values[key] = value
    if result.returncode or re.search(r'\b(error|warning|failed)\b', log, re.I):
        raise RuntimeError(label + ' simulator error or warning')
    return dict(case=label, parameters=parameters, measurements=values)


try:
    test = command([sys.executable, '-m', 'unittest', 'discover', '-s', 'hardware/tests', '-v'], 'trace-checker-tests.log')
    if test.returncode:
        raise RuntimeError('Evidence checker regression failed')
    record('Evidence checker negative cases', 'pass', '9 tests including missing fields, samples, DMA IRQs, timeout and unqualified model')

    cad = ['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad']
    erc = command(cad + ['sch','erc','--exit-code-violations','--output', OUT / 'erc.rpt', ROOT / 'hardware/rev-a/voicevault-reva.kicad_sch'], 'erc-command.log')
    if erc.returncode:
        raise RuntimeError('KiCad ERC reported violations')
    record('KiCad schematic connectivity', 'pass', 'Native schematic ERC has zero violations. Passive ports do not check module circuitry.')
    netlist = OUT / 'netlist.xml'
    exported = command(cad + ['sch','export','netlist','--format','kicadxml','--output',netlist, ROOT / 'hardware/rev-a/voicevault-reva.kicad_sch'], 'netlist-command.log')
    if exported.returncode:
        raise RuntimeError('KiCad netlist export failed')
    nets = ET.parse(netlist).getroot().find('nets')
    radio = set()
    for net in nets:
        if any(node.get('ref') == 'J7' for node in net.findall('node')):
            radio.add(net.get('name').removeprefix('/'))
    expected_radio = {'5V_SYS','GND','MCU_TX_TO_RADIO','RADIO_TX_TO_MCU','RADIO_CREDIT','RADIO_PENDING'}
    if radio != expected_radio:
        raise RuntimeError('Radio interface netlist mismatch ' + repr(radio))
    record('Radio interface netlist', 'pass', 'Exactly the six declared carrier connections, including shared supply and ground')

    drc = command(cad + ['pcb','drc','--exit-code-violations','--format','json','--output',OUT / 'drc.json',ROOT / 'hardware/rev-a/voicevault-reva.kicad_pcb'], 'drc-command.log')
    drc_data = json.loads((OUT / 'drc.json').read_text())
    unrouted = len(drc_data.get('unconnected_items', []))
    violations = len(drc_data.get('violations', []))
    record('PCB manufacturing gate', 'blocked', f'Placement draft has {unrouted} unrouted connections and {violations} layout violations. Routing and review required.')

    cases = []
    for tolerance in (.95, 1, 1.05):
        cases.append(spice_case('microphone', {'tol':tolerance}, f'mic-{tolerance}', {'gain_300':(.4,.55),'gain_3400':(.25,.4)}))
    cases.append(spice_case('microphone', {'switch_r':'1e12','mute_r':'.05'}, 'mic-disconnected', {'gain_300':(0,1e-6),'gain_3400':(0,1e-6)}))
    for load in (16,32,64,300):
        for cap in ('176u','220u','264u'):
            cases.append(spice_case('headphone', {'load':load,'cap':cap}, f'headphone-{load}-{cap}', {'gain_300':(.84,1),'gain_3400':(.88,1),'v(headphone)':(-1e-6,1e-6)}))
    for resistance in (.1,.25,.5):
        for capacitance in ('11u','22u'):
            cases.append(spice_case('supply', {'series_r':resistance,'bulk_c':capacitance}, f'supply-{resistance}-{capacitance}', {'rail_min':(4.7,5.01),'rail_max':(4.7,5.01)}))
    (OUT / 'spice.json').write_text(json.dumps(cases,indent=2)+'\n')
    record('Analog circuit sensitivity', 'pass', f'{len(cases)} actual ngspice cases. Linear microphone, headphone coupling and supply impedance models only.')

    cpu_env = os.environ | {'CARGO_HOME':str(ROOT / '.lab-cache/cargo'), 'PATH':str(ROOT / '.lab-cache/bin') + ':' + str(Path.home() / '.cargo/bin') + ':' + os.environ['PATH']}
    cpu_env.pop('RUSTUP_TOOLCHAIN',None)
    cpu = command([sys.executable, ROOT / 'scripts/platform_check.py', OUT / 'cpu'], 'cpu-command.log', timeout=240, env=cpu_env)
    if cpu.returncode:
        raise RuntimeError('Cortex-M33 CPU diagnostic failed')
    record('Cortex-M33 software execution', 'pass', 'Actual hybrid handshake and 32 codec/media frames on QEMU MPS2 AN505. Target peripherals are outside this check.')

    renode = command([ROOT / '.lab-cache/bin/renode','--plain', ROOT / 'hardware/renode/missing-peripheral.resc'], 'renode-negative-control.log', timeout=45)
    if renode.returncode:
        raise RuntimeError('Renode negative control exited with an error')
    warning_log = renode.stdout
    if warning_log.count('[WARNING]') != 3 or '[ERROR]' in warning_log:
        raise RuntimeError('Renode negative control produced unexpected warnings or errors')
    for address in ('0x40015800','0x40020000','0x40032400'):
        if not re.search(r'non existing peripheral at ' + address, warning_log, re.I):
            raise RuntimeError('Expected missing-peripheral warning absent for ' + address)
    record('Incomplete emulator negative control', 'pass', 'Actual SAI2, GPDMA1 and GTZC1 accesses were detected as unsupported even when Renode exits successfully')
    record('STM32 audio and DMA qualification', 'blocked', 'No qualified peripheral model or matching board trace. Expected samples and completion IRQs remain unobserved.')
    record('STM32 TrustZone and DMA isolation', 'blocked', 'CPU and DMA denial must be observed on revision-Z silicon and compared with a qualified model.')
except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as error:
    record('Hardware design checks', 'fail', str(error))

failed = any(row['status'] == 'fail' for row in results)
report = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), status='fail' if failed else 'blocked',
              target=json.loads((ROOT / 'hardware/reference/target.json').read_text()), checks=results,
              scope='Review-stage carrier and explicit partial circuit models. Hardware qualification remains blocked.')
(OUT / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Report saved to {OUT / "report.json"}', flush=True)
sys.exit(1 if failed else (0 if args.design_only else 2))
