import unittest
from urllib.parse import parse_qs, urlsplit

from license_utils import (
    create_license_session,
    generate_license,
    verify_license_key,
    verify_license_session,
)


class LicenseUtilsTests(unittest.TestCase):
    def test_generated_key_matches_activation_validation(self):
        name = "Budi Motor"

        key, link = generate_license(name, "https://example.com/")

        self.assertTrue(verify_license_key(key, name))
        parsed_link = urlsplit(link)
        self.assertEqual(
            parse_qs(parsed_link.fragment),
            {"name": [name], "key": [key]},
        )
        self.assertEqual(parsed_link.path, "/activate")
        self.assertTrue(link.startswith("https://example.com/activate#"))

    def test_signed_license_session_round_trips_owner(self):
        token = create_license_session("Budi Motor", "x" * 40, now=1000)

        self.assertEqual(
            verify_license_session(token, "x" * 40, now=1001),
            "Budi Motor",
        )

    def test_expired_or_tampered_session_is_rejected(self):
        token = create_license_session(
            "Budi Motor",
            "x" * 40,
            max_age=10,
            now=1000,
        )

        self.assertIsNone(verify_license_session(token, "x" * 40, now=1010))
        self.assertIsNone(
            verify_license_session(token + "tampered", "x" * 40, now=1001)
        )
        self.assertIsNone(verify_license_session(token, "y" * 40, now=1001))

    def test_empty_customer_name_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_license("  ")


if __name__ == "__main__":
    unittest.main()
