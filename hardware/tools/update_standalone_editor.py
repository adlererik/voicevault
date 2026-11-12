#!/usr/bin/env python3
"""Back up the live unrouted draft, regenerate, verify native export and reload."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from kipy import KiCad

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
CACHE = ROOT / '.lab-cache/hardware/standalone-update'
CACHE.mkdir(parents=True, exist_ok=True)
client = KiCad(socket_path='ipc://' + str(Path.home() / '.var/app/org.kicad.KiCad/cache/vv-pcb/kicad/api.sock'), timeout_ms=5000)
board = client.get_board()
assert (Path(board.document.project.path) / board.name).resolve() == DESIGN / 'voicevault-standalone-b0.kicad_pcb'
assert not board.get_tracks() and not board.get_vias() and not board.get_zones(), 'Preserve existing routed work; merge it explicitly.'
board.save()
backup = ROOT / '.lab-cache/hardware/rev-b-backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True)
for path in DESIGN.glob('*.kicad_*'):
    shutil.copyfile(path, backup / path.name)
positions = {item.reference_field.text.value: dict(x=item.position.x / 1e6, y=item.position.y / 1e6,
             angle=item.orientation.degrees, back=board.get_layer_name(item.layer) == 'B.Cu')
             for item in board.get_footprints()}
layout = CACHE / 'preserved-layout.json'
layout.write_text(json.dumps(positions))
try:
    subprocess.run(['flatpak', 'run', '--user', '--command=python3', 'org.kicad.KiCad',
                    str(ROOT / 'hardware/tools/create_standalone_draft.py'), '--replace', '--preserve-layout', str(layout)], check=True)
    subprocess.run(['flatpak', 'run', '--user', '--command=kicad-cli', 'org.kicad.KiCad', 'sch',
                    'export', 'netlist', '--format', 'kicadxml', '--output', str(CACHE / 'netlist.xml'),
                    str(DESIGN / 'voicevault-standalone-b0.kicad_sch')], check=True)
    netlist = ET.parse(CACHE / 'netlist.xml').getroot()
    manifest = json.loads((DESIGN / 'circuits.json').read_text())
    expected = 32 + sum(len(page['parts']) for page in manifest['pages'])
    expected_physical = expected + len(manifest.get('mechanical', []))
    assert len(netlist.findall('./components/comp')) == expected, 'Missing hierarchical components'
except BaseException:
    for path in backup.iterdir():
        shutil.copyfile(path, DESIGN / path.name)
    raise
board.revert()
board = client.get_board()
assert len(board.get_footprints()) == expected_physical
print(f'Updated the open VoiceVault board: {expected} circuit components / {expected_physical} footprints. Existing positions/sides preserved. Circuit checks still required.')
