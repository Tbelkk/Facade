"""RESTore Inspector: a local dev viewer for Screen Models (not the real overlay).

Usage (from core/):
    python -m ingest.inspect            # opens http://127.0.0.1:8770 in your browser
    python -m ingest.inspect --port 9000 --no-open

Shows every screen.json it finds in core/cache/screens/*/ and shared/fixtures/screen/,
rendered in Original / Faithful / Enhanced / Reimagined (preview), plus the ARIA tree,
Nemotron's labels and the original vs modern theme.
"""
import argparse
import json
import mimetypes
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .paths import CACHE_DIR, FIXTURES_DIR, INGEST_DIR, REPO_ROOT

PAGE = INGEST_DIR / "inspector" / "index.html"


def find_screens():
    found = []
    for p in sorted((CACHE_DIR / "screens").glob("*/screen.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        found.append(p)
    fx = FIXTURES_DIR / "screen" / "screen.json"
    if fx.is_file():
        found.append(fx)
    out = []
    for p in found:
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            title = m.get("screen", {}).get("window", {}).get("title") or p.parent.name
            sid = m.get("screen", {}).get("id", "?")
        except Exception:
            title, sid = p.parent.name, "?"
        rel = p.resolve().relative_to(REPO_ROOT).as_posix()
        tag = "fixture" if "fixtures" in rel else p.parent.name
        out.append({"label": f"{sid} - {title} ({tag})", "url": "/files/" + rel})
    return out


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/screens":
            return self._send(200, json.dumps(find_screens()).encode(), "application/json")
        if path.startswith("/files/"):
            target = (REPO_ROOT / path[len("/files/"):]).resolve()
            if REPO_ROOT not in target.parents or not target.is_file():  # stay inside the repo
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return self._send(200, target.read_bytes(), ctype)
        return self._send(404, b"not found", "text/plain")


def main(argv=None):
    ap = argparse.ArgumentParser(description="RESTore Inspector")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"RESTore Inspector running at {url}  (Ctrl+C to stop)")
    print(f"screens found: {len(find_screens())}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
