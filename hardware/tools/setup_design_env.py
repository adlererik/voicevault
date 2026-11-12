#!/usr/bin/env python3
"""Create an OS-upgrade-independent environment for local KiCad IPC/MCP tools."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / '.lab-cache/hardware/mcp-venv'
PYTHON = '3.12.14'


def main():
    uv = shutil.which('uv')
    if not uv:
        raise SystemExit('Install uv first; this script does not change the system Python.')
    subprocess.run([uv, 'python', 'install', PYTHON], check=True)
    if not ENV.exists():
        subprocess.run([uv, 'venv', '--python', PYTHON, str(ENV)], check=True)
    actual = subprocess.check_output([str(ENV / 'bin/python'), '-c',
                                     'import platform;print(platform.python_version())'], text=True).strip()
    if actual != PYTHON:
        raise SystemExit(f'Existing environment uses {actual}. Preserve/rename it before creating the pinned environment.')
    subprocess.run([uv, 'pip', 'install', '--python', str(ENV / 'bin/python'),
                    '-r', str(ROOT / 'hardware/requirements-design.txt')], check=True)
    print('Pinned local KiCad/MCP/design environment ready. Run ./hardware/open.')


if __name__ == '__main__':
    main()
