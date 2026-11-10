"""Bounded, incremental progress extraction from actual subprocess output."""
import json
import os
import re
import selectors
import signal
import subprocess
import time
from dashboard import case_events, trace

MAX_LINE = 16384


class OutputParser:
    def __init__(self, name, model, *, events=False, recorded=False):
        self.name, self.model = name, model
        self.events, self.recorded = events, recorded
        self.partial = ""
        self.seen = set()
        self.harness = None
        self.rust_case = None
        self.last_progress = 0.0
        self.progress_text = "Process running; waiting for reported progress"

    def emit_case(self, event):
        key = (event['test'], event['status'])
        if key not in self.seen:
            self.seen.add(key)
            self.model.add(event)

    def start_case(self, name, detail="Running reported test"):
        self.emit_case(trace(f"{self.name} / {name}", "case", "reported test outcome", detail))

    def feed(self, chunk):
        # Input is decoded by an incremental UTF-8 decoder in pump().
        self.partial += chunk.replace('\r', '\n')
        while '\n' in self.partial:
            line, self.partial = self.partial.split('\n', 1)
            self.line(line[:MAX_LINE])
        if len(self.partial) > MAX_LINE:
            self.partial = self.partial[-MAX_LINE:]
        match = re.match(r'^test (\S+) \.\.\.', self.partial)
        if match:
            self.start_case(match[1])

    def line(self, line):
        if self.events and line.startswith('{'):
            try:
                event = json.loads(line)
                if self.recorded and event.get('action') not in ('verdict', 'group'):
                    event['test'] = 'recorded-' + event['test']
                self.model.add(event)
            except (ValueError, TypeError, KeyError):
                raise ValueError(f'{self.name}: invalid structured telemetry') from None
            return
        start = re.match(r'^test (\S+) \.\.\.', line)
        if start:
            self.rust_case = start[1]
            self.start_case(start[1])
        # Rust is invoked with one test thread. With nocapture, a property-test
        # diagnostic may split the name and final outcome onto separate lines.
        outcome = line.strip()
        if self.rust_case and outcome in ('ok', 'FAILED', 'ignored'):
            status = {'ok': 'pass', 'FAILED': 'fail', 'ignored': 'blocked'}[outcome]
            self.emit_case(trace(f'{self.name} / {self.rust_case}', 'case', 'reported Rust test result', outcome, status))
            self.rust_case = None
        harness = re.match(r'Checking harness ([\w:]+)\.\.\.', line)
        if harness:
            self.harness = harness[1]
            self.start_case(self.harness, 'Checking bounded proof')
        if self.harness and 'VERIFICATION:- ' in line:
            if 'SUCCESSFUL' in line or 'FAILED' in line:
                status = 'pass' if 'SUCCESSFUL' in line else 'fail'
                self.emit_case(trace(f'{self.name} / {self.harness}', 'case', 'bounded Kani proof', line.strip()[:300], status))
                self.harness = None
        vector = re.match(r'^(testvector\d+): RUNNING$', line)
        if vector:
            self.start_case(vector[1], 'Checking official decoder vector')
        for event in case_events(self.name, line):
            self.emit_case(event)
            if self.rust_case and event["test"] == f"{self.name} / {self.rust_case}":
                self.rust_case = None
        fuzz = re.match(r'^#(\d+)\s+.*?exec/s:\s*(\d+).*?rss:\s*(\S+)', line)
        done = re.search(r'Done (\d+) runs in (\d+) second', line)
        if fuzz:
            self.progress_text = f'{int(fuzz[1]):,} fuzz executions · {fuzz[2]}/s · process memory {fuzz[3]}'
        elif done:
            self.progress_text = f'{int(done[1]):,} fuzz executions completed in {done[2]} seconds'
        elif line.lstrip().startswith(('Compiling ', 'Checking ', 'Finished ', 'Downloading ')):
            self.progress_text = line.strip()[:220]
        elif line.startswith(('running ', 'Test vector ', 'Opus quality metric:')):
            self.progress_text = line.strip()[:220]
        self.heartbeat()

    def heartbeat(self, force=False):
        now = time.monotonic()
        if force or now - self.last_progress >= 1:
            self.last_progress = now
            self.model.add(trace(self.name, 'progress', 'actual process output and elapsed time', self.progress_text))

    def finish(self):
        if self.partial:
            self.line(self.partial)
            self.partial = ''


def pump(command, *, cwd, env, logfile, name, model, timeout, events=False, recorded=False):
    """Tee output without waiting for exit; slow browsers never block this pipe."""
    import codecs
    parser = OutputParser(name, model, events=events, recorded=recorded)
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    started = time.monotonic()
    with logfile.open('wb') as log:
        import shlex
        log.write(('$ ' + shlex.join(map(str, command)) + '\n').encode()); log.flush()
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while selector.get_map():
                if time.monotonic() - started > timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                for key, _ in selector.select(.1):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    log.write(data); log.flush()
                    parser.feed(decoder.decode(data))
                parser.heartbeat()
            parser.feed(decoder.decode(b'', final=True)); parser.finish()
            return process.wait(timeout=max(.1, timeout - (time.monotonic() - started)))
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        finally:
            selector.close()
            process.stdout.close()
