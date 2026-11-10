"""Persistent read-only UI. Test processes publish locally, never through HTTP."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from dashboard import DEFAULT_HOST, DEFAULT_PORT, SERVICE_VERSION, LIMIT, Server, Trace, validate

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / '.lab-runs'
CURRENT = RUNS / 'current.json'
URL = f'http://{DEFAULT_HOST}:{DEFAULT_PORT}/'


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value) + '\n'); temporary.replace(path)


def publish(directory):
    RUNS.mkdir(exist_ok=True)
    atomic(CURRENT, {'directory': str(Path(directory).resolve())})


class FileTrace(Trace):
    def __init__(self, pointer=CURRENT):
        super().__init__(metadata={'id': 'idle', 'kind': 'idle', 'started': None})
        self.phase = 'idle'; self.pointer = pointer; self.offset = 0; self.source_directory = None
        self.stop_polling = threading.Event()
        self.worker = threading.Thread(target=self.poll, daemon=True)

    def refresh(self):
        if not self.pointer.is_file(): return
        info = json.loads(self.pointer.read_text())
        directory = Path(info['directory'])
        state = json.loads((directory / 'live-state.json').read_text())
        with self.changed:
            if state['id'] != self.metadata['id']:
                self.events = []; self.offset = 0
            self.metadata = state
            self.source_directory = directory
            phase = state['phase']
            if phase not in ('done', 'interrupted', 'error'):
                try: os.kill(state['owner_pid'], 0)
                except ProcessLookupError: phase = 'interrupted'
            changed = self.phase != phase
            self.phase = phase
            with (directory / 'live-events.ndjson').open() as file:
                file.seek(self.offset)
                while True:
                    offset = file.tell(); line = file.readline(16385)
                    if not line: break
                    if len(line) > 16384: raise ValueError('oversized journal event')
                    if not line.endswith('\n'): file.seek(offset); break
                    event = json.loads(line); validate(event)
                    if len(self.events) >= LIMIT: raise ValueError('event limit exceeded')
                    self.events.append(event); changed = True
                self.offset = file.tell()
            if changed: self.changed.notify_all()

    def poll(self):
        while not self.stop_polling.is_set():
            try: self.refresh()
            except (FileNotFoundError, json.JSONDecodeError): pass  # Initial atomic publication may still be in flight.
            except (OSError, ValueError, KeyError):
                with self.changed:
                    self.phase = 'error'; self.changed.notify_all()
            self.stop_polling.wait(.1)


def serve():
    RUNS.mkdir(exist_ok=True)
    model = FileTrace(); model.worker.start()
    server = Server(model)
    try: server.serve_forever(poll_interval=.1)
    finally:
        model.stop_polling.set(); server.server_close()


def health():
    connection = http.client.HTTPConnection(DEFAULT_HOST, DEFAULT_PORT, timeout=.5)
    try:
        connection.request('GET', '/health'); response = connection.getresponse()
        if response.status != 200: raise ValueError('address is occupied by another application')
        data = json.loads(response.read())
        expected = hashlib.sha256(str(ROOT).encode()).hexdigest()
        if data.get('project') != 'VoiceVault' or data.get('version') != SERVICE_VERSION or data.get('root') != expected:
            raise ValueError('fixed address is occupied by a different service/version')
        return data
    finally: connection.close()


def ensure_service():
    try: health(); return URL
    except (ConnectionRefusedError, ConnectionResetError): pass
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise ValueError(f'{URL} unavailable: {error}; no alternate port was selected') from None
    RUNS.mkdir(exist_ok=True)
    with (RUNS / 'ui-service.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, ROOT / 'scripts/dashboard.py', '--serve'],
                                   cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    for _ in range(50):
        try: health(); return URL
        except (ConnectionRefusedError, ConnectionResetError, OSError):
            if process.poll() is not None: break
            time.sleep(.05)
    raise ValueError(f'Could not start fixed dashboard at {URL}; see .lab-runs/ui-service.log')
