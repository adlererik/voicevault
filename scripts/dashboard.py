"""Read-only trace model and loopback EventSource server."""
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import os
import time
from pathlib import Path
import threading

TEMPLATE = Path(__file__).with_name("dashboard.html")
GROUPS = ("unit", "protocol", "lifecycle", "platform", "codec", "isolation", "fuzz", "kani",
          "dependencies", "timing", "dashboard")
STATUSES = {"info", "pass", "fail", "blocked"}
NODES = {"", "Alice", "Phone A", "Relay", "Phone B", "Bob"}
ACTIONS = {"send", "forward", "drop", "delay", "tamper", "replay", "inject",
           "duplicate", "receive", "reject", "playout", "verdict", "group", "check", "case", "progress", "device"}
FIELDS = {"test", "tick", "action", "from", "to", "expected", "observed", "status"}
LIMIT = 32768
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SERVICE_VERSION = 4


def trace(test, action, expected, observed, status="info"):
    return {"test": test, "tick": 0, "action": action, "from": "", "to": "",
            "expected": expected, "observed": observed, "status": status}


def case_events(check, log):
    """Extract reported outcomes, never infer a case pass from a group verdict."""
    result = []
    for name, outcome in re.findall(r"^test (\S+) \.\.\. (ok|FAILED|ignored)\s*$", log, re.M):
        status = {"ok": "pass", "FAILED": "fail", "ignored": "blocked"}[outcome]
        result.append(trace(f"{check} / {name}", "case", "reported Rust test result", outcome, status))
    for name, outcome in re.findall(r"^(testvector\d+): (PASS|FAIL)\s*$", log, re.M):
        result.append(trace(f"{check} / {name}", "case", "official Opus decoder vector", outcome,
                            "pass" if outcome == "PASS" else "fail"))
    for name, section in re.findall(r"Checking harness ([\w:]+)\.\.\.(.*?)(?=Checking harness |Manual Harness Summary:|\Z)", log, re.S):
        if "VERIFICATION:- SUCCESSFUL" in section:
            result.append(trace(f"{check} / {name}", "case", "bounded Kani proof", "Verified", "pass"))
        elif "VERIFICATION:- FAILED" in section:
            result.append(trace(f"{check} / {name}", "case", "bounded Kani proof", "Failed", "fail"))
    return result


def validate(event):
    if set(event) != FIELDS:
        raise ValueError("unexpected trace fields")
    if type(event["tick"]) is not int or not 0 <= event["tick"] <= 100_000:
        raise ValueError("invalid trace tick")
    for field in FIELDS - {"tick"}:
        if not isinstance(event[field], str) or len(event[field]) > 400:
            raise ValueError(f"invalid trace field {field}")
    if (event["action"] not in ACTIONS or event["status"] not in STATUSES
            or event["from"] not in NODES or event["to"] not in NODES):
        raise ValueError("invalid trace route, action or status")
    if event["action"] == "group" and (event["test"] not in GROUPS or event["status"] == "info"):
        raise ValueError("invalid suite verdict event")


def page(events, live=False, metadata=None):
    data = json.dumps({"live": live, "events": events, "meta": metadata or {}}, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.read_text().replace("@@REPORT@@", data)


class Trace:
    def __init__(self, directory=None, metadata=None):
        self.directory = Path(directory) if directory else None
        self.metadata = metadata or {"id": str(time.time_ns()), "started": time.time(), "owner_pid": os.getpid(), "kind": "verification"}
        self.events = []
        self.phase = "live"
        self.changed = threading.Condition()
        if self.directory:
            (self.directory / "live-events.ndjson").write_text("")
            self.save_state()

    def save_state(self):
        if self.directory:
            target = self.directory / "live-state.json"
            temp = target.with_suffix(".tmp")
            temp.write_text(json.dumps(self.metadata | {"phase": self.phase, "events": len(self.events)}))
            temp.replace(target)

    def add(self, event):
        validate(event)
        with self.changed:
            if len(self.events) >= LIMIT:
                raise ValueError("trace event limit reached")
            self.events.append(event)
            if self.directory:
                with (self.directory / "live-events.ndjson").open("a") as file:
                    file.write(json.dumps(event, separators=(",", ":")) + "\n")
            self.changed.notify_all()

    def set_phase(self, phase):
        with self.changed:
            self.phase = phase
            if phase in ("done", "interrupted", "error"):
                self.metadata["ended"] = time.time()
            self.save_state()
            self.changed.notify_all()

    def next(self, cursor, last_phase):
        with self.changed:
            self.changed.wait_for(lambda: last_phase != self.phase or cursor < len(self.events), timeout=.5)
            return self.phase, self.events[cursor:]


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(2)
        super().setup()

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.headers.get("Host") != self.server.host:
            self.send_error(403)
            return
        if self.path == "/":
            body = page([], live=True, metadata=self.server.trace.metadata).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; connect-src 'self'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            import hashlib
            body = json.dumps({"project": "VoiceVault", "version": SERVICE_VERSION,
                               "root": hashlib.sha256(str(Path(__file__).resolve().parents[1]).encode()).hexdigest(),
                               "pid": os.getpid()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/events":
            if not self.server.clients.acquire(blocking=False):
                self.send_error(503)
                return
            try:
                self.stream()
            except (BrokenPipeError, ConnectionError, TimeoutError):
                pass
            finally:
                self.server.clients.release()
        else:
            self.send_error(404)

    def do_POST(self):
        self.send_error(405)

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        cursor, last_phase, run_id = 0, None, None
        previous = self.headers.get("Last-Event-ID", "")
        resume_run, _, resume_cursor = previous.rpartition(":")
        trace_model = self.server.trace
        while not self.server.stopping.is_set():
            current_run = trace_model.metadata.get("id", "idle")
            if run_id != current_run:
                run_id, cursor, last_phase = current_run, 0, None
                if resume_run == run_id:
                    try: cursor = min(len(trace_model.events), max(0, int(resume_cursor)))
                    except ValueError: pass
                self.message("run", trace_model.metadata)
            phase, events = trace_model.next(cursor, last_phase)
            if trace_model.metadata.get("id", "idle") != run_id:
                continue
            if phase != last_phase:
                self.message("phase", phase); last_phase = phase
            for event in events:
                cursor += 1
                self.message("trace", event, f"{run_id}:{cursor}")
            self.message("clock", {"now": time.time(), "phase": phase, "ended": trace_model.metadata.get("ended")})

    def message(self, kind, data, event_id=None):
        header = "" if event_id is None else f"id: {event_id}\n"
        self.wfile.write(f"{header}event: {kind}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, trace, port=DEFAULT_PORT):
        super().__init__((DEFAULT_HOST, port), Handler)
        self.trace = trace
        self.host = f"127.0.0.1:{self.server_port}"
        self.url = f"http://{self.host}/"
        self.clients = threading.BoundedSemaphore(8)
        self.stopping = threading.Event()

    def start(self):
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()

    def stop(self):
        self.stopping.set()
        with self.trace.changed:
            self.trace.changed.notify_all()
        self.shutdown()
        self.server_close()


def check_mapping(events, verdict):
    mapped = {}
    for event in events:
        validate(event)
        if event["action"] == "group":
            if event["test"] in mapped:
                raise ValueError("duplicate suite verdict event")
            mapped[event["test"]] = event["status"]
    if mapped != {key: verdict[key] for key in GROUPS}:
        raise ValueError("dashboard verdicts differ from CLI")
    return mapped


def self_test():
    cases = case_events("sample", "test accepts ... ok\ntest rejects ... FAILED\n"
                        "test skipped ... ignored\ntestvector01: PASS\n"
                        "Checking harness proofs::closed...\nVERIFICATION:- SUCCESSFUL\n"
                        "Checking harness proofs::bad...\nVERIFICATION:- FAILED\n")
    assert [e["status"] for e in cases] == ["pass", "fail", "blocked", "pass", "pass", "fail"]
    assert not case_events("sample", "Checking harness proofs::unknown...\nno result reported\n")
    model = Trace(); server = Server(model, port=0); server.start()
    def event(response):
        kind, data = None, None
        while True:
            line = response.readline()
            assert line, "stream closed"
            if line.startswith(b"event:"): kind = line[6:].strip().decode()
            if line.startswith(b"data:"): data = json.loads(line[5:])
            if line == b"\n" and kind: return kind, data
    try:
        assert server.server_address[0] == DEFAULT_HOST
        for _ in range(8): assert server.clients.acquire(blocking=False)
        assert not server.clients.acquire(blocking=False)
        for _ in range(8): server.clients.release()
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=3)) as client:
            client.request("POST", "/events"); assert client.getresponse().status == 405
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=3)) as client:
            client.request("GET", "/", headers={"Host": "outside.invalid"}); assert client.getresponse().status == 403
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=3)) as client:
            client.request("GET", "/health"); response = client.getresponse()
            assert json.loads(response.read())["project"] == "VoiceVault"
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=3)) as client:
            client.request("GET", "/events"); response = client.getresponse()
            assert event(response)[0] == "run"
            assert event(response) == ("phase", "live")
            assert event(response)[0] == "clock"
            model.set_phase("timing")
            sample = trace("timing-idle", "progress", "measurement running", "Elapsed progress continues")
            model.add(sample)
            received = [event(response) for _ in range(3)]
            assert ("phase", "timing") in received and ("trace", sample) in received
        # Completion keeps the stream usable for the next run at the same URL.
        model.set_phase("done")
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=3)) as client:
            client.request("GET", "/events", headers={"Last-Event-ID": f'{model.metadata["id"]}:1'})
            response = client.getresponse()
            assert event(response)[0] == "run"
            assert event(response) == ("phase", "done")
            assert event(response)[0] == "clock"  # The already delivered trace is not duplicated.
            with model.changed:
                model.metadata = {"id": "next-run", "kind": "verification"}
                model.events = []; model.phase = "live"; model.changed.notify_all()
            next_event = trace("next", "check", "stream survives completion", "Running")
            model.add(next_event)
            messages = [event(response) for _ in range(4)]
            assert any(kind == "run" and data["id"] == "next-run" for kind, data in messages)
            assert ("trace", next_event) in messages
        for group in GROUPS: model.add(trace(group, "group", "expected", "observed", "pass"))
        verdict = dict.fromkeys(GROUPS, "pass"); check_mapping(model.events, verdict)
        html = page(model.events + [trace("escaping", "verdict", "</script>", "x")])
        assert "\\u003c/script\\u003e" in html
        data = html.split('<script id="initial" type="application/json">')[1].split("</script>")[0]
        assert json.loads(data)["events"][:-1] == model.events
        assert all(f'data-node="{node}"' in html for node in NODES - {""})
    finally: server.stop()
    from live_tests import self_test as live_tests
    live_tests()
    print("Read-only loopback, fixed-address ownership, live streaming, restart, progress, schema and mapping passed")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--serve"]:
        from live_server import serve
        serve()
    else: self_test()
