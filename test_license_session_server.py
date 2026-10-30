import http.client
import threading
import unittest
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import license_session_server
from license_utils import generate_license, verify_license_session


class LicenseSessionServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        license_session_server.SESSION_SECRET = "test-session-secret-" * 3
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            license_session_server.LicenseSessionHandler,
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def test_valid_activation_sets_signed_secure_http_only_cookie(self):
        owner = "PWA Test"
        key, _ = generate_license(owner)
        status, headers, _ = self.request(
            "POST",
            "/license/activate",
            urlencode({"name": owner, "key": key}),
        )
        response_headers = dict(headers)
        cookie = SimpleCookie()
        cookie.load(response_headers["Set-Cookie"])
        session_cookie = cookie["valuasi_session"]

        self.assertEqual(status, 204)
        self.assertTrue(session_cookie["httponly"])
        self.assertTrue(session_cookie["secure"])
        self.assertEqual(session_cookie["samesite"], "Lax")
        self.assertEqual(
            verify_license_session(
                session_cookie.value,
                license_session_server.SESSION_SECRET,
            ),
            owner,
        )
        self.assertNotIn(key, session_cookie.value)

    def test_invalid_activation_does_not_issue_cookie(self):
        status, headers, _ = self.request(
            "POST",
            "/license/activate",
            urlencode({"name": "PWA Test", "key": "invalid"}),
        )

        self.assertEqual(status, 403)
        self.assertNotIn("Set-Cookie", dict(headers))

    def test_logout_clears_session_cookie(self):
        status, headers, _ = self.request("GET", "/license/logout")
        cookie = SimpleCookie()
        cookie.load(dict(headers)["Set-Cookie"])

        self.assertEqual(status, 303)
        self.assertEqual(cookie["valuasi_session"]["max-age"], "0")


if __name__ == "__main__":
    unittest.main()
