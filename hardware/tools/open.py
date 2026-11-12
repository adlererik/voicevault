#!/usr/bin/env python3
"""Check graphics and open one copy of each engineering tool."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.lab-runs/hardware/latest'
OUT.mkdir(parents=True, exist_ok=True)


def checked(args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def already_open(name, document):
    processes = subprocess.check_output(['ps', '-eo', 'comm=,args='], text=True)
    for line in processes.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0] == name and str(document) in fields[1]:
            return True
    return False


if not (OUT / 'report.json').exists():
    checked([sys.executable, ROOT / 'hardware/tools/check.py', '--design-only'])

checked([sys.executable, ROOT / 'hardware/tools/setup_kicad.py'])

# Test the same graphics runtime before opening any editor windows.
graphics = subprocess.run(['flatpak', 'run', '--user', '--command=python3', 'org.kicad.KiCad',
                           str(ROOT / 'hardware/tools/graphics_probe.py')], cwd=ROOT,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(OUT / 'graphics.log').write_text(graphics.stderr)
if graphics.returncode:
    sys.exit('KiCad graphics preflight failed. ' + graphics.stdout + graphics.stderr)
(OUT / 'graphics.json').write_text(graphics.stdout)

views = OUT / 'views'
views.mkdir(exist_ok=True)
cad = ['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad']
checked(cad + ['sch', 'export', 'svg', '--output', views,
               ROOT / 'hardware/rev-a/voicevault-reva.kicad_sch'])
checked(cad + ['pcb', 'export', 'svg', '--layers', 'F.Cu,F.Silkscreen,Edge.Cuts',
               '--mode-single', '--fit-page-to-board', '--exclude-drawing-sheet',
               '--output', views / 'carrier.svg', ROOT / 'hardware/rev-a/voicevault-reva.kicad_pcb'])
for source, destination in [('carrier.svg', 'carrier.png'), ('voicevault-reva.svg', 'schematic.png')]:
    checked(['magick', '-background', 'white', '-density', '125', views / source, views / destination])
checked([sys.executable, ROOT / 'hardware/tools/present.py'])

app_log = (OUT / 'opened-apps.log').open('a')


def launch(args, cwd=ROOT, log=app_log):
    return subprocess.Popen(list(map(str, args)), cwd=cwd, stdout=log, stderr=log,
                            start_new_session=True)


try:
    with socket.create_connection(('127.0.0.1', 8766), timeout=1):
        with urllib.request.urlopen('http://127.0.0.1:8766/', timeout=2) as response:
            if b'VoiceVault Hardware Review' not in response.read(4096):
                sys.exit('Port 8766 is occupied by another application.')
except OSError:
    server_log = (OUT / 'server.log').open('a')
    launch([sys.executable, '-m', 'http.server', '8766', '--bind', '127.0.0.1',
            '--directory', OUT], log=server_log)

processes = []
for command, filename in [('kicad', 'voicevault-reva.kicad_pro'),
                           ('eeschema', 'voicevault-reva.kicad_sch'),
                           ('pcbnew', 'voicevault-reva.kicad_pcb')]:
    document = ROOT / 'hardware/rev-a' / filename
    if not already_open(command, document):
        app_command = ['flatpak', 'run', '--user']
        if command == 'pcbnew':
            temporary = Path.home() / '.var/app/org.kicad.KiCad/cache/vv-pcb'
            temporary.mkdir(mode=0o700, parents=True, exist_ok=True)
            app_command.append('--env=TMPDIR=' + str(temporary))
        app_command.extend(['--command=' + command, 'org.kicad.KiCad', document])
        process = launch(app_command)
        processes.append(process.pid)

interactive = OUT / 'headphone-interactive.cir'
if not already_open('ngspice', interactive):
    source = (ROOT / 'hardware/spice/headphone.cir').read_text().replace('quit', 'plot vm(headphone)')
    interactive.write_text(source)
    process = launch(['gnome-terminal', '--window', '--title=VoiceVault analog circuit', '--',
                      ROOT / '.lab-cache/bin/ngspice', '-i', interactive], cwd=OUT)
    processes.append(process.pid)

monitor = OUT / 'review.resc'
if not already_open('renode', monitor):
    source = (ROOT / 'hardware/renode/missing-peripheral.resc').read_text().replace('\nquit', '')
    monitor.write_text(source)
    process = launch(['gnome-terminal', '--window', '--title=VoiceVault incomplete STM32 model',
                      '--', ROOT / '.lab-cache/bin/renode', '--plain', monitor])
    processes.append(process.pid)

(OUT / 'opened-processes.json').write_text(json.dumps(processes) + '\n')
renderer = json.loads(graphics.stdout)['renderer']
print(f'Graphics verified with {renderer}. Engineering tools are open.')
print('Hardware report http://127.0.0.1:8766/')
