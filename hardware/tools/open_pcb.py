#!/usr/bin/env python3
"""Open only the PCB editor needed by the local MCP connection."""
from pathlib import Path
import subprocess

from setup_kicad import configure

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / 'hardware/rev-b/voicevault-standalone-b0.kicad_pcb'


def main():
    processes = subprocess.check_output(['ps', '-eo', 'comm=,args='], text=True)
    for line in processes.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0] == 'pcbnew' and str(BOARD) in fields[1]:
            print('VoiceVault PCB editor is already open.')
            return
    configure(enable_api=True)
    temporary = Path.home() / '.var/app/org.kicad.KiCad/cache/vv-pcb'
    temporary.mkdir(mode=0o700, parents=True, exist_ok=True)
    logs = ROOT / '.lab-runs/hardware/latest'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / 'mcp-editor.log').open('a') as log:
        subprocess.Popen(['flatpak', 'run', '--user', '--env=TMPDIR=' + str(temporary),
                          '--command=pcbnew', 'org.kicad.KiCad', str(BOARD)],
                         cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
    print('Opening the VoiceVault PCB editor for MCP.')


if __name__ == '__main__':
    main()
