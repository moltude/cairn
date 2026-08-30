"""Dev server for the Cairn web prototype. Serves web/ with the wheel at /dist/.

Mirrors the security headers from vercel.json (the "/(.*)" block) so the local
e2e suite exercises the same CSP the Vercel deploy will enforce — a CSP that
breaks Pyodide fails loudly here instead of only in production.
"""
import functools, http.server, json, pathlib, socketserver

ROOT = pathlib.Path(__file__).parent

def _security_headers():
    try:
        cfg = json.loads((ROOT / "vercel.json").read_text())
        for rule in cfg.get("headers", []):
            if rule.get("source") == "/(.*)":
                return [(h["key"], h["value"]) for h in rule["headers"]]
    except (OSError, ValueError, KeyError):
        pass
    return []

_HEADERS = _security_headers()

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        for key, value in _HEADERS:
            self.send_header(key, value)
        super().end_headers()
    def log_message(self, *a): pass

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 8765),
            functools.partial(H, directory=str(ROOT))) as httpd:
        print("serving http://127.0.0.1:8765 with", len(_HEADERS), "security headers")
        httpd.serve_forever()
