"""Read-only trace model and loopback EventSource server."""
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import threading

TEMPLATE = Path(__file__).with_name("dashboard.html")
GROUPS = ("unit", "protocol", "lifecycle", "platform", "codec", "isolation", "fuzz", "kani",
          "dependencies", "timing", "dashboard")
STATUSES = {"info", "pass", "fail", "blocked"}
NODES = {"", "Alice", "Phone A", "Relay", "Phone B", "Bob"}
ACTIONS = {"send", "forward", "drop", "delay", "tamper", "replay", "inject",
           "duplicate", "receive", "reject", "playout", "verdict", "group", "check", "case"}
FIELDS = {"test", "tick", "action", "from", "to", "expected", "observed", "status"}
LIMIT = 4096


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


def page(events, live=False):
    data = json.dumps({"live": live, "events": events}, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.read_text().replace("@@REPORT@@", data)


class Trace:
    def __init__(self):
        self.events = []
        self.phase = "live"
        self.changed = threading.Condition()

    def add(self, event):
        validate(event)
        with self.changed:
            if len(self.events) >= LIMIT:
                raise ValueError("trace event limit reached")
            self.events.append(event)
            self.changed.notify_all()

    def set_phase(self, phase):
        with self.changed:
            self.phase = phase
            self.changed.notify_all()

    def next(self, cursor, last_phase):
        with self.changed:
            self.changed.wait_for(
                lambda: last_phase != self.phase or (
                    self.phase != "timing" and cursor < len(self.events)),
                timeout=1,
            )
            events = [] if self.phase == "timing" else self.events[cursor:]
            return self.phase, events


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
            body = page([], live=True).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; connect-src 'self'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
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
        cursor, last_phase = 0, None
        try:
            cursor = min(LIMIT, max(0, int(self.headers.get("Last-Event-ID", 0))))
        except ValueError:
            pass
        trace = self.server.trace
        while not self.server.stopping.is_set():
            phase, events = trace.next(cursor, last_phase)
            if phase == "timing":
                if last_phase != phase:
                    self.message("phase", phase)
                    last_phase = phase
                continue
            if last_phase != phase and phase != "done":
                self.message("phase", phase)
                last_phase = phase
            for event in events:
                if trace.phase == "timing":
                    break
                cursor += 1
                self.message("trace", event, cursor)
            if phase == "done":
                self.message("phase", phase)
                return

    def message(self, kind, data, event_id=None):
        header = "" if event_id is None else f"id: {event_id}\n"
        self.wfile.write(f"{header}event: {kind}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, trace):
        super().__init__(("127.0.0.1", 0), Handler)
        self.trace = trace
        self.host = f"127.0.0.1:{self.server_port}"
        self.url = f"http://{self.host}/"
        self.clients = threading.BoundedSemaphore(4)
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
    assert [event["status"] for event in cases] == ["pass", "fail", "blocked", "pass", "pass", "fail"]
    assert not case_events("sample", "Checking harness proofs::unknown...\nno result reported\n")
    assert not case_events("sample", "40 tests passed\n")
    for event in cases:
        validate(event)
    model = Trace()
    server = Server(model)
    server.start()
    try:
        assert server.server_address[0] == "127.0.0.1"
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=2)) as client:
            client.request("POST", "/events")
            assert client.getresponse().status == 405
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=2)) as client:
            client.request("GET", "/", headers={"Host": "outside.invalid"})
            assert client.getresponse().status == 403
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=2)) as client:
            client.request("GET", "/")
            response = client.getresponse()
            assert response.status == 200 and b'"live":true' in response.read()
        model.set_phase("timing")
        # Opening the UI mid-measurement must still show the paused dashboard.
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=2)) as client:
            client.request("GET", "/")
            response = client.getresponse()
            assert response.status == 200 and b'"live":true' in response.read()
        model.add(trace("format", "check", "complete formatting check", "Running"))
        example = trace("protocol", "group", "expected", "observed", "fail")
        model.add(example)
        with contextlib.closing(http.client.HTTPConnection(server.host, timeout=2)) as client:
            client.request("GET", "/events")
            response = client.getresponse()
            assert response.status == 200
            assert response.readline() == b"event: phase\n"
            assert json.loads(response.readline()[6:]) == "timing"
            assert response.readline() == b"\n"
            assert model.next(0, "timing") == ("timing", [])
            model.set_phase("live")
            assert response.readline() == b"event: phase\n"
            assert json.loads(response.readline()[6:]) == "live"
            assert response.readline() == b"\n"
            assert response.readline() == b"id: 1\n"
            assert response.readline() == b"event: trace\n"
            assert json.loads(response.readline()[6:]) == model.events[0]
            assert response.readline() == b"\n"
            assert response.readline() == b"id: 2\n"
            assert response.readline() == b"event: trace\n"
            assert json.loads(response.readline()[6:]) == example
        for group in GROUPS:
            if group != "protocol":
                model.add(trace(group, "group", "expected", "observed", "blocked"))
        verdict = dict.fromkeys(GROUPS, "blocked") | {"protocol": "fail"}
        check_mapping(model.events, verdict)
        html = page(model.events + [trace("escaping", "verdict", "</script>", "x")])
        assert "\\u003c/script\\u003e" in html
        initial = html.split('<script id="initial" type="application/json">')[1].split("</script>")[0]
        assert json.loads(initial)["events"][:-1] == model.events
        assert all(f'data-node="{node}"' in html for node in NODES - {""})
        assert all(f'id="{name}"' in html for name in ("test-search", "case-list", "check-list"))
    finally:
        server.stop()
    print("Loopback bind, read-only HTTP, SSE pause/resume, event schema, verdicts and offline data passed")


if __name__ == "__main__":
    self_test()
