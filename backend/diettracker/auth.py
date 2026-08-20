from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta


SESSION_LENGTH = timedelta(days=30)
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 32


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Create a portable scrypt password hash for APP_PASSWORD_HASH."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = salt or secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_KEY_LENGTH
    )
    return "$".join(("scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P), _encode(salt), _encode(derived_key)))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n, r, p, encoded_salt, encoded_key = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected_key = _decode(encoded_key)
        actual_key = hashlib.scrypt(
            password.encode(), salt=_decode(encoded_salt), n=int(n), r=int(r), p=int(p), dklen=len(expected_key)
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual_key, expected_key)


def create_session_token(username: str, secret: str, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {"sub": username, "exp": int((issued_at + SESSION_LENGTH).timestamp())}
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def verify_session_token(token: str, username: str, secret: str, *, now: datetime | None = None) -> bool:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode(supplied_signature), expected_signature):
            return False
        payload = json.loads(_decode(encoded))
        current_time = now or datetime.now(UTC)
        return hmac.compare_digest(str(payload["sub"]), username) and int(payload["exp"]) > int(current_time.timestamp())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
