"""Dev server for the Cairn web prototype. Serves web/ with the wheel at /dist/.

Mirrors the security headers from vercel.json (the "/(.*)" block) so the local
e2e suite exercises the same CSP the Vercel deploy will enforce — a CSP that
breaks Pyodide fails loudly here instead of only in production.
"""
import functools, http.server, json, os, pathlib, socketserver

ROOT = pathlib.Path(__file__).parent

def _security_headers():
    # Every "/(.*)" rule, not just the first: vercel.json has one for
    # Cache-Control and one for the CSP, and stopping at the first silently
    # served the dev site (and the enforced-CSP e2e test) with no CSP at all.
    # Cache-Control is skipped; end_headers sends its own no-store.
    try:
        cfg = json.loads((ROOT / "vercel.json").read_text())
        return [(h["key"], h["value"])
                for rule in cfg.get("headers", []) if rule.get("source") == "/(.*)"
                for h in rule["headers"] if h["key"].lower() != "cache-control"]
    except (OSError, ValueError, KeyError):
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
    port = int(os.environ.get("PORT", "8765"))  # PORT=8779 when 8765 is taken
    with socketserver.TCPServer(("127.0.0.1", port),
            functools.partial(H, directory=str(ROOT))) as httpd:
        print(f"serving http://127.0.0.1:{port} with", len(_HEADERS), "security headers")
        httpd.serve_forever()
