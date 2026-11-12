#!/usr/bin/env python3
"""Complete missing KiCad 10 Flatpak setup using the upstream wizard defaults."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PROFILE = Path.home() / '.var/app/org.kicad.KiCad'
CONFIG = PROFILE / 'config/kicad/10.0'
BACKUP = ROOT / '.lab-cache/hardware/kicad-setup-backup' / datetime.now().strftime('%Y%m%d-%H%M%S')


def replace_with_backup(path, content):
    if path.exists() and path.read_text() == content:
        return
    if path.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, BACKUP / path.name)
    path.write_text(content)


def configure(enable_api=False):
    CONFIG.mkdir(parents=True, exist_ok=True)
    common = CONFIG / 'kicad_common.json'
    if not common.exists():
        raise RuntimeError('Initialize KiCad settings with kicad-cli before configuring the GUI.')
    data = json.loads(common.read_text())
    prompts = data.setdefault('do_not_show_again', {})
    if not prompts.get('data_collection_prompt', False):
        for marker in (PROFILE / 'cache/kicad').rglob('sentry-opt-in'):
            BACKUP.mkdir(parents=True, exist_ok=True)
            marker.rename(BACKUP / 'sentry-opt-in')
    prompts['data_collection_prompt'] = True
    prompts['update_check_prompt'] = True
    if enable_api:
        data.setdefault('api', {})['enable_server'] = True
    variables = data.setdefault('environment', {}).setdefault('vars', {})
    for name, directory in [('SYMBOL', 'symbols'), ('FOOTPRINT', 'footprints'),
                            ('3DMODEL', '3dmodels'), ('TEMPLATE', 'template')]:
        variables.setdefault('KICAD10_' + name + '_DIR', '/app/extensions/Library/' + directory)
    replace_with_backup(common, json.dumps(data, indent=2) + '\n')
    for filename in ('sym-lib-table', 'fp-lib-table'):
        destination = CONFIG / filename
        if not destination.exists():
            content = subprocess.check_output(['flatpak', 'run', '--user', '--command=cat',
                       'org.kicad.KiCad', '/app/extensions/Library/template/' + filename], text=True)
            replace_with_backup(destination, content)
    blocks = CONFIG / 'design-block-lib-table'
    if not blocks.exists():
        replace_with_backup(blocks, '(design_block_lib_table (version 7))\n')
    print('KiCad settings, three library tables, and completed privacy/update choices are saved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable-api', action='store_true')
    configure(parser.parse_args().enable_api)
