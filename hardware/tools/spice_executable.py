"""Locate the real simulator, with an explicit local override for other hosts."""
import os
from pathlib import Path
import shutil


def ngspice():
    root = Path(__file__).resolve().parents[2]
    choice = os.environ.get('VOICEVAULT_NGSPICE')
    cached = root / '.lab-cache/bin/ngspice'
    choice = choice or (str(cached) if cached.is_file() else shutil.which('ngspice'))
    if not choice:
        raise RuntimeError('Install ngspice 47 or set VOICEVAULT_NGSPICE to its executable.')
    return choice
