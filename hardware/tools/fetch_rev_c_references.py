#!/usr/bin/env python3
"""Fetch hash-pinned public supplier models into the ignored local cache.

Use --all for the reference PDFs too. A supplier revision requires review and
an explicit manifest update; a changed download never silently replaces it.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Also fetch the datasheet/package PDFs')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'hardware/rev-c/references.json').read_text())
    cache = ROOT/manifest['cache_relative']
    cache.mkdir(parents=True, exist_ok=True)
    for source in manifest['sources']:
        if not args.all and 'model_member' not in source:
            continue
        target = cache/source['cache_file']
        if target.exists():
            data = target.read_bytes()
        else:
            print('Downloading', source['cache_file'], flush=True)
            request = Request(source['url'], headers={'User-Agent': 'VoiceVault-reference-check/1.0'})
            with urlopen(request, timeout=40) as response:
                data = response.read(32*1024*1024+1)
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise RuntimeError('Supplier content changed; review required: '+source['cache_file'])
        if not target.exists():
            target.write_bytes(data)
        if 'model_member' in source:
            # Read exactly the reviewed member, never extract arbitrary ZIP paths.
            member = source['model_member']
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                model = archive.read(member)
            output = cache/source['model_cache_directory']/member
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(model)
        print('Verified', source['cache_file'])


if __name__ == '__main__':
    main()
