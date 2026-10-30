import os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from license_utils import (
    LICENSE_SESSION_COOKIE,
    LICENSE_SESSION_MAX_AGE,
    create_license_session,
    verify_license_key,
)


HOST = os.environ.get("LICENSE_SESSION_HOST", "127.0.0.1")
PORT = int(os.environ.get("LICENSE_SESSION_PORT", "8765"))
SESSION_SECRET = os.environ.get("LICENSE_SESSION_SECRET", "")


class LicenseSessionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/license/logout":
            self._clear_session()
            return
        self._send_text(404, "Not found.")

    def do_POST(self):
        if urlsplit(self.path).path != "/license/activate":
            self._send_text(404, "Not found.")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > 4096:
            self._send_text(400, "Form aktivasi tidak valid.")
            return

        try:
            request_body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError:
            self._send_text(400, "Form aktivasi tidak valid.")
            return
        form_data = parse_qs(request_body, keep_blank_values=True)
        owner = form_data.get("name", [""])[0].strip()
        license_key = form_data.get("key", [""])[0].strip()
        if not verify_license_key(license_key, owner):
            self._send_text(403, "Nama atau kode lisensi tidak cocok.")
            return
        if len(SESSION_SECRET) < 32:
            self._send_text(503, "Sesi persisten belum dikonfigurasi.")
            return

        token = create_license_session(owner, SESSION_SECRET)
        cookie = SimpleCookie()
        cookie[LICENSE_SESSION_COOKIE] = token
        cookie[LICENSE_SESSION_COOKIE]["path"] = "/"
        cookie[LICENSE_SESSION_COOKIE]["max-age"] = str(LICENSE_SESSION_MAX_AGE)
        cookie[LICENSE_SESSION_COOKIE]["httponly"] = True
        cookie[LICENSE_SESSION_COOKIE]["secure"] = True
        cookie[LICENSE_SESSION_COOKIE]["samesite"] = "Lax"

        self.send_response(204)
        self.send_header("Set-Cookie", cookie[LICENSE_SESSION_COOKIE].OutputString())
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _clear_session(self):
        cookie = SimpleCookie()
        cookie[LICENSE_SESSION_COOKIE] = ""
        cookie[LICENSE_SESSION_COOKIE]["path"] = "/"
        cookie[LICENSE_SESSION_COOKIE]["max-age"] = "0"
        cookie[LICENSE_SESSION_COOKIE]["httponly"] = True
        cookie[LICENSE_SESSION_COOKIE]["secure"] = True
        cookie[LICENSE_SESSION_COOKIE]["samesite"] = "Lax"
        self.send_response(303)
        self.send_header("Set-Cookie", cookie[LICENSE_SESSION_COOKIE].OutputString())
        self.send_header("Location", "/")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send_text(self, status, message):
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        return


def main():
    if len(SESSION_SECRET) < 32:
        raise RuntimeError(
            "Set LICENSE_SESSION_SECRET to a random secret of at least 32 characters."
        )
    server = ThreadingHTTPServer((HOST, PORT), LicenseSessionHandler)
    print(f"License session service listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
