#!/usr/bin/env python3
"""Archive actual C0 reports and plot their recorded radio-switch waveform."""
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'.lab-runs/hardware/standalone-c0'
DEST = ROOT/'hardware/evidence/2026-11-16/rev-c'


def main():
    report = json.loads((OUT/'report.json').read_text())
    if report['available_design_checks'] != 'PASS':
        raise RuntimeError('Inspect failures before recording the checked C0 snapshot')
    for name, expected in report['input_sha256'].items():
        actual = hashlib.sha256((ROOT/'hardware/rev-c'/name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError('Circuit input changed after checks: '+name)
    DEST.mkdir(parents=True, exist_ok=True)
    for name in ['report.json', 'spice-summary.json', 'erc.json', 'drc.json']:
        shutil.copyfile(OUT/name, DEST/name)
    shutil.copyfile(OUT/'spice-result-regression.log', DEST/'spice-result-regression.log')
    converter = ROOT/'.lab-cache/hardware-research/2026-11-15/revc/converter-compatibility'
    for name in ['execution.json', 'execution-short.json', 'ngspice-short.log']:
        if (converter/name).exists():
            shutil.copyfile(converter/name, DEST/('converter-'+name))
    for directory in ['spice-radio-switch', 'spice-model-logic']:
        for name in ['input.cir', 'ngspice.log']:
            shutil.copyfile(OUT/directory/name, DEST/(directory+'-'+name))
    waveform = OUT/'spice-radio-switch/waveform.txt'
    data = np.loadtxt(waveform, skiprows=1)
    t, voltage, fault, current = data[:, 0]*1000, data[:, 1], data[:, 3], data[:, 5]*1000
    switch = next(g for g in report['spice']['groups'] if g['name'] == 'Supplier radio-switch model')
    if switch['status'] != 'PASS':
        raise RuntimeError('Cannot plot a successful supplier-switch result: check the report')
    values = switch['measurements']
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
    axes[0].plot(t, voltage, color='#126c9c', label='Radio supply')
    axes[0].plot(t, fault, color='#987100', linestyle='--', label='Fault signal')
    axes[0].axvspan(6, 21, color='#dd7744', alpha=.13, label='Applied overload')
    axes[0].set(xlim=(0, 30), ylim=(-.1, 3.6), xlabel='Time (ms)', ylabel='Voltage (V)',
                title='Start • overload • recovery')
    axes[0].legend(fontsize=8, loc='lower right')
    axes[1].plot(t, current, color='#126c9c')
    axes[1].axvspan(6, 21, color='#dd7744', alpha=.13)
    axes[1].set(xlim=(0, 30), ylim=(-3, current.max()*1.12), xlabel='Time (ms)',
                ylabel='Input current (mA)', title='Transient and steady overload')
    axes[1].annotate(f"{values['limited_a']*1000:.0f} mA steady",
                     xy=(17, values['limited_a']*1000), xytext=(13, 270),
                     arrowprops={'arrowstyle': '->', 'color': '#555'})
    peak = current.argmax()
    axes[1].annotate(f'{current[peak]:.0f} mA transient peak', xy=(t[peak], current[peak]),
                     xytext=(11, 570), arrowprops={'arrowstyle': '->', 'color': '#555'})
    axes[2].plot(t-30, voltage, color='#126c9c')
    axes[2].axhline(.1, color='#9b3c29', linestyle=':', label='0.1 V check threshold')
    axes[2].plot(100, values['disabled_v'], 'o', color='#126c9c')
    axes[2].annotate(f"{values['disabled_v']*1000:.0f} mV at 100 ms",
                     xy=(100, values['disabled_v']), xytext=(45, 1.15),
                     arrowprops={'arrowstyle': '->', 'color': '#555'})
    axes[2].set(xlim=(0, 110), ylim=(-.1, 3.6), xlabel='Time after disable (ms)',
                ylabel='Radio voltage (V)', title='Power-off with load disconnected')
    axes[2].legend(fontsize=8, loc='upper right')
    for axis in axes:
        axis.grid(alpha=.2)
    fig.suptitle('VoiceVault C0 • ngspice 47 supplier-model experiment', fontsize=15, fontweight='bold')
    fig.text(.5, -.035, 'Simulation only: not physical measurements or complete device qualification.',
             ha='center', fontsize=10, color='#555')
    fig.savefig(DEST/'radio-switch.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    artifacts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.iterdir())
                 if p.is_file() and p.name != 'artifact-sha256.json'}
    (DEST/'artifact-sha256.json').write_text(json.dumps({
        'source_waveform': str(waveform.relative_to(ROOT)),
        'source_waveform_sha256': hashlib.sha256(waveform.read_bytes()).hexdigest(),
        'files': artifacts}, indent=2)+'\n')
    print('Archived', len(artifacts), 'files and plotted', len(data), 'actual waveform samples')


if __name__ == '__main__':
    main()
