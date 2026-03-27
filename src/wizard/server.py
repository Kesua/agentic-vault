"""Wizard HTTP server -- stdlib only, localhost-only, static + API routing."""

from __future__ import annotations

import json
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

WIZARD_DIR = Path(__file__).resolve().parent
WEB_DIR = WIZARD_DIR / "web"
REPO_ROOT = WIZARD_DIR.parent.parent

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

API_ROUTES: dict[str, callable] = {}

_SERVER_REF: ThreadingHTTPServer | None = None


class WizardHandler(BaseHTTPRequestHandler):
    """Routes GET/POST to static files or API handlers."""

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._handle_api("GET")
        else:
            self._serve_static()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._handle_api("POST")
        else:
            self._send_json(405, {"error": "Method not allowed"})

    # -- API dispatch --

    def _handle_api(self, method: str) -> None:
        clean_path = urlparse(self.path).path.rstrip("/")
        route_key = f"{method} {clean_path}"
        handler_fn = API_ROUTES.get(route_key)
        if not handler_fn:
            self._send_json(404, {"error": f"Unknown route: {route_key}"})
            return
        try:
            body = self._read_body() if method == "POST" else None
            result = handler_fn(body, self.headers)
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    # -- Static file serving --

    def _serve_static(self) -> None:
        parsed = urlparse(self.path)
        rel = parsed.path.lstrip("/") or "index.html"
        file_path = (WEB_DIR / rel).resolve()

        if not file_path.is_relative_to(WEB_DIR.resolve()):
            self._send_error_page(403, "Forbidden")
            return

        if not file_path.is_file():
            self._send_error_page(404, "Not found")
            return

        suffix = file_path.suffix.lower()
        content_type = MIME_TYPES.get(suffix, "application/octet-stream")

        try:
            data = file_path.read_bytes()
        except OSError:
            self._send_error_page(500, "Read error")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- Helpers --

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw else {}

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_page(self, status: int, message: str) -> None:
        body = f"<h1>{status} {message}</h1>".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ARG002
        pass


def get_server_ref() -> ThreadingHTTPServer | None:
    return _SERVER_REF


def _find_port(start: int = 8470, end: int = 8479):
    for port in range(start, end + 1):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), WizardHandler)
            return port, server
        except OSError:
            continue
    raise RuntimeError(f"No available port in range {start}-{end}")


def main() -> None:
    global _SERVER_REF  # noqa: PLW0603

    from . import handlers  # noqa: F811 -- deferred to avoid circular imports

    handlers.register_routes(API_ROUTES)

    port, server = _find_port()
    _SERVER_REF = server
    url = f"http://localhost:{port}"
    print(f"       Setup wizard running at {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Wizard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.path.insert(0, str(WIZARD_DIR.parent.parent))
    main()
