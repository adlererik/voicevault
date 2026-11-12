#!/usr/bin/env python3
"""Run actual ngspice sensitivity experiments for the B0 passive networks.

An ideal regulator/source is an explicit assumption, never a silicon model.
The static LED models bound chosen forward voltages; they do not predict LED
temperature, brightness, startup, EMI or the TPS61062 feedback loop.
"""
from pathlib import Path
import itertools
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from spice_executable import ngspice

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
OUT = ROOT / '.lab-runs/hardware/standalone-b0/spice-audio-backlight'
SPICE = ngspice()


def experiment(group, index, source, measurements):
    directory = OUT / group / str(index)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'input.cir').write_text(source)
    result = subprocess.run([str(SPICE), '-b', 'input.cir'], cwd=directory,
                            capture_output=True, text=True, timeout=15)
    log = result.stdout + result.stderr
    (directory / 'ngspice.log').write_text(log)
    values = {}
    for name in measurements:
        match = re.search(re.escape(name) + r'\s*=\s*([\d.eE+-]+)', log)
        if match:
            values[name] = float(match[1])
    if result.returncode or set(values) != set(measurements):
        raise RuntimeError(f'Incomplete {group}/{index}: {log[-1800:]}')
    return dict(case=index, **values)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output([str(SPICE), '--version'], text=True)
    assert 'ngspice-47' in version, 'Record and review a changed simulator version.'
    (OUT / 'version.txt').write_text(version)
    measurements = ['gain_100', 'gain_1000', 'gain_16000']
    headphones = []
    template = (DESIGN / 'spice/headset-ac.cir').read_text()
    for index, (load, cap, esr, driver) in enumerate(itertools.product(
            [16, 32, 300], [176e-6, 220e-6, 264e-6], [.015, .2], [0.1, 4])):
        params = f'.param cval={cap} esr={esr} rdriver={driver} rseries=10 rload={load}'
        result = experiment('headphone', index, re.sub(r'^\.param.*', params, template, flags=re.M), measurements)
        result.update(load_ohm=load, cap_f=cap, esr_ohm=esr, driver_ohm=driver)
        if result['gain_100'] - result['gain_1000'] < -1.0:
            raise RuntimeError('Headphone passive response exceeds 1dB relative loss at 100Hz')
        headphones.append(result)
    print(f'Headphone: {len(headphones)} passive AC cases completed.', flush=True)
    microphone = []
    template = (DESIGN / 'spice/microphone-ac.cir').read_text()
    for index, (mute, ron, coff, cap, impedance) in enumerate(itertools.product(
            [0, 1], [.1, 1], [.1e-12, 10e-12], [.5e-6, 1e-6], [10000, 40000])):
        params = f'.param ron={ron} coff={coff} cin={cap} rin={impedance} muting={mute}'
        result = experiment('microphone', index, re.sub(r'^\.param.*', params, template, flags=re.M), measurements)
        result.update(mute=bool(mute), contact_ohm=ron, assumed_off_cap_f=coff, cap_f=cap, adc_input_ohm=impedance)
        if mute and result['gain_16000'] > -100:
            raise RuntimeError('Modeled physical mute falls below the chosen 100dB attenuation target')
        microphone.append(result)
    print(f'Microphone: {len(microphone)} AC/contact sensitivity cases completed.', flush=True)
    # Match the current native design's intended resistor network. Native
    # connectivity is checked separately; this catches stale simulation values.
    manifest = json.loads((DESIGN / 'circuits.json').read_text())
    parts = {p['ref']: p for page in manifest['pages'] for p in page['parts']}
    assert parts['R707']['value'].startswith('12R ')
    assert all(parts['R' + str(n)]['value'].startswith('200R ') for n in range(709, 713))
    subprocess.run(['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad',
                    'sch', 'export', 'netlist', '--format', 'kicadxml', '--output',
                    str(OUT / 'native-netlist.xml'),
                    str(DESIGN / 'voicevault-standalone-b0.kicad_sch')], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    native = ET.parse(OUT / 'native-netlist.xml').getroot()
    values = {p.get('ref'): p.findtext('value') for p in native.findall('./components/comp')}
    for reference in ['R707', 'R709', 'R710', 'R711', 'R712', 'R604', 'R605', 'R606', 'R607']:
        assert values[reference] == parts[reference]['value'], 'Stale native circuit: ' + reference
    led_cases = []
    vf_sets = [[2.7]*4, [3.1]*4, [3.5]*4]
    vf_sets += [[2.7 if i == low else 3.5 for i in range(4)] for low in range(4)]
    vf_sets += [[3.5 if i == high else 2.7 for i in range(4)] for high in range(4)]
    combinations = itertools.product(vf_sets, range(16), [(.485, 12.12), (.515, 11.88)], [5.9, 7.3])
    for index, (vf, mask, (feedback, sense), zener) in enumerate(combinations):
        # Explicit engineering envelope for zener knee/slope, not a fitted
        # manufacturer's model. Open LEDs are represented by 1T-ohm branches.
        branch = []
        for i in range(4):
            resistance = 1e12 if mask & (1 << i) else (198 if i == 0 else 202)
            branch += [f'Vmon{i+1} anode p{i+1} 0',
                       f'Bled{i+1} p{i+1} fb I=max((v(p{i+1},fb)-{vf[i]})/{resistance},0)']
        source = '\n'.join(['VoiceVault B0 static backlight sharing / open-load sensitivity',
                  '* Ideal total-current regulator and fixed-Vf LED branches. NO converter silicon model.',
                  f'Ireg 0 anode {feedback/sense}', f'Rsense fb 0 {sense}', 'Rleak anode 0 1e9',
                  *branch, f'Bclamp anode fb I=max((v(anode,fb)-{zener})/10,0)',
                  '.nodeset v(anode)=6 v(fb)=.5', '.control', 'op',
                  'print v(anode) v(fb) i(vmon1) i(vmon2) i(vmon3) i(vmon4)', 'quit', '.endc', '.end', ''])
        result = experiment('backlight', index, source,
                            ['v(anode)', 'v(fb)'] + [f'i(vmon{i})' for i in range(1, 5)])
        result.update(vf_v=vf, open_mask=mask, reference_v=feedback,
                      sense_ohm=sense, assumed_zener_knee_v=zener)
        healthy = [result[f'i(vmon{i+1})'] for i in range(4) if not mask & (1 << i)]
        if any(current > .025 for current in healthy):
            raise RuntimeError(f'Healthy LED exceeds 25mA in static envelope: {index}')
        if result['v(anode)'] > 10:
            raise RuntimeError('Modeled open-load voltage exceeds 10V envelope')
        led_cases.append(result)
    report = dict(simulator='ngspice 47', status='MODELED CHECKS COMPLETED',
                  limitations=['No MCU/codec/LED-converter silicon/control-loop model',
                    'ADC input impedance, driver impedance and switch off capacitance are explicit sensitivity assumptions',
                    'LED fixed-Vf and zener envelope are not temperature/brightness/thermal qualification',
                    'Power budget, startup/transients, acoustic quality, EMI and assembled hardware remain unverified'],
                  headphone=headphones, microphone=microphone, backlight=led_cases)
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Backlight: {len(led_cases)} static cases, all healthy branches below 25mA in the stated envelope.', flush=True)
    print('Completed modeled sensitivity checks; no physical-functionality or silicon-stability claim.')


if __name__ == '__main__':
    main()
