"""Read-only, bounded monitoring of actual decoded synthetic lab PCM.

This is a trusted-host observation path, never a phone/media API. Native
scored timing modes do not create monitor files. No audio goes in trace JSON.
"""
from pathlib import Path
import struct
from urllib.parse import parse_qs, urlsplit

SAMPLES = 320
FRAME_BYTES = 4 + SAMPLES * 2
MAX_FRAMES = 1500
BATCH = 8
SCENARIOS = {'live', 'live-faults'}


def active_source(model):
    with model.changed:
        check = next((event for event in reversed(model.events) if event['action'] == 'check'), None)
        directory = getattr(model, 'source_directory', None)
        if model.phase != 'live' or not directory or not check or check['status'] != 'info' or check['test'] not in SCENARIOS:
            return None
        return model.metadata['id'], check['test'], Path(directory)


def batch(model, request):
    """Return (status, headers, bytes), with at most eight frames per side."""
    query = parse_qs(urlsplit(request).query, strict_parsing=True)
    if set(query) != {'run', 'scenario', 'alice', 'bob'} or any(len(v) != 1 for v in query.values()):
        raise ValueError('invalid monitor query')
    query = {k:v[0] for k,v in query.items()}
    cursors = {side:int(query[side]) for side in ('alice','bob')}
    if any(not -1 <= cursor <= MAX_FRAMES for cursor in cursors.values()):
        raise ValueError('invalid monitor cursor')
    source = active_source(model)
    if source is None:
        return 204, {}, b''
    run_id, scenario, directory = source
    if query['run'] != run_id or query['scenario'] != scenario:
        return 409, {}, b''
    headers = {'X-Run-Id':run_id, 'X-Scenario':scenario}
    records = []
    for side_id, side in enumerate(('alice','bob')):
        path = directory / scenario / f'{side}-monitor.pcm'
        try:
            with path.open('rb') as file:
                total = path.stat().st_size // FRAME_BYTES
                if total > MAX_FRAMES:
                    raise ValueError('monitor file exceeds live-call bound')
                cursor = cursors[side]
                # Joining late or falling behind never plays an old backlog.
                if cursor < 0 or cursor > total or total - cursor > 20:
                    cursor = max(0, total - 4)
                count = min(BATCH, total - cursor)
                file.seek(cursor * FRAME_BYTES)
                data = file.read(count * FRAME_BYTES)
                count = len(data) // FRAME_BYTES
                for offset in range(0, count * FRAME_BYTES, FRAME_BYTES):
                    frame = data[offset:offset+FRAME_BYTES]
                    if struct.unpack_from('<I', frame)[0] >= MAX_FRAMES:
                        raise ValueError('invalid monitor slot')
                    records.append(bytes([side_id]) + frame)
                cursor += count
        except FileNotFoundError:
            cursor = 0
        headers[f'X-{side.title()}-Cursor'] = str(cursor)
    if active_source(model) != source:
        return 409, {}, b''
    return 200, headers, b''.join(records)
