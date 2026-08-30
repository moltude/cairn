"""Dev server for the Cairn web prototype. Serves web/ with the wheel at /dist/."""
import functools, http.server, socketserver, pathlib
ROOT = pathlib.Path(__file__).parent
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a): pass
if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 8765),
            functools.partial(H, directory=str(ROOT))) as httpd:
        print("serving http://127.0.0.1:8765")
        httpd.serve_forever()
