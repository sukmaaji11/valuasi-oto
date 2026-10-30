import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode


SECRET_SALT = "VALUASIOTO_149K_SEKALI_BELI_2026"
DEFAULT_APP_URL = "https://valuasi-oto.duckdns.org"
LICENSE_SESSION_COOKIE = "valuasi_session"
LICENSE_SESSION_MAX_AGE = 30 * 24 * 60 * 60


def _encode_urlsafe(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_urlsafe(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_license_session(owner, secret, max_age=LICENSE_SESSION_MAX_AGE, now=None):
    if not owner or not secret:
        raise ValueError("Nama pemilik dan secret sesi wajib diisi.")

    issued_at = int(time.time() if now is None else now)
    payload = json.dumps(
        {"owner": owner.strip(), "exp": issued_at + max_age},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = _encode_urlsafe(payload)
    signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_encode_urlsafe(signature)}"


def verify_license_session(token, secret, now=None):
    if not token or not secret:
        return None

    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_signature = _decode_urlsafe(encoded_signature)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None

        payload = json.loads(_decode_urlsafe(encoded_payload))
        if not isinstance(payload, dict):
            return None
        current_time = int(time.time() if now is None else now)
        owner = payload.get("owner")
        expires_at = payload.get("exp")
        if not isinstance(owner, str) or not owner.strip():
            return None
        if (
            not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or expires_at <= current_time
        ):
            return None
        return owner
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def create_activation_link(nama_pemilik, license_key, app_url=None):
    base_url = (
        app_url or os.environ.get("PUBLIC_APP_URL") or DEFAULT_APP_URL
    ).strip().rstrip("/")
    activation_data = urlencode(
        {"name": nama_pemilik.strip(), "key": license_key.strip()}
    )
    return f"{base_url}/activate#{activation_data}"


def verify_license_key(input_key, nama_pemilik):
    if not input_key or not nama_pemilik:
        return False
    clean_name = nama_pemilik.strip().upper()
    raw_str = f"{clean_name}_{SECRET_SALT}"
    hashed_str = hashlib.sha256(raw_str.encode()).hexdigest().upper()[:8]
    expected_key = f"VALUASI-{clean_name.replace(' ', '')[:6]}-{hashed_str}"
    return input_key.strip().upper() == expected_key


def generate_license(nama_pembeli, app_url=None):
    clean_name = nama_pembeli.strip()
    if not clean_name:
        raise ValueError("Nama pembeli wajib diisi.")

    canonical_name = clean_name.upper()
    raw_str = f"{canonical_name}_{SECRET_SALT}"
    hashed_str = hashlib.sha256(raw_str.encode()).hexdigest().upper()[:8]
    license_key = (
        f"VALUASI-{canonical_name.replace(' ', '')[:6]}-{hashed_str}"
    )
    magic_link = create_activation_link(clean_name, license_key, app_url)
    return license_key, magic_link
