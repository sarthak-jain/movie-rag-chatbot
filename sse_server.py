"""Minimal SSE server for the System Design Panel.

Local dev only: Hugging Face Spaces exposes a single port, so this second
HTTP server is unreachable once deployed — the panel degrades to a
"Reconnecting..." badge in production, and that's expected. Locally, the
browser's EventSource connects directly to this port (no proxying through
Streamlit), which is why plain stdlib http.server is enough — no ASGI
framework needed for one read-only streaming endpoint.
"""

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import workflow_events

PORT = 8502

_started = threading.Event()
_lock = threading.Lock()


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # clients (esp. EventSource reconnects) disconnect constantly — not our bug


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # keep stdout clean — this runs on every heartbeat

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path != "/events":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors_headers()
        self.end_headers()

        q = workflow_events.subscribe()
        try:
            while True:
                try:
                    event_name, data = q.get(timeout=15)
                    payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
                except queue.Empty:
                    payload = ": keepalive\n\n"
                self.wfile.write(payload.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass
        finally:
            workflow_events.unsubscribe(q)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")


def start_server_once(port: int = PORT) -> int:
    """Start the background SSE server exactly once per process. Returns the port."""
    with _lock:
        if _started.is_set():
            return port
        try:
            server = _Server(("127.0.0.1", port), _Handler)
        except OSError:
            # Port already bound — most likely another Streamlit session in this
            # same process already started it moments ago. Treat as started.
            _started.set()
            return port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _started.set()
        return port
