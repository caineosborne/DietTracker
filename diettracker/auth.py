from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_manager import EncryptedCookieManager


# The cookie component cannot remove names when its `prefix` option is used.
# Keep the names unique ourselves instead, so logout reliably removes them.
COOKIE_PREFIX = ""
COOKIE_KEY_PARAMS = "diettracker_cookie_key_params"
LOGIN_USERNAME_COOKIE = "diettracker_login_username"
LOGIN_EXPIRY_COOKIE = "diettracker_login_expires_at"
SESSION_LENGTH = timedelta(days=30)
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 32
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_ENV_FILE = PROJECT_ROOT / ".env"


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Create a portable scrypt password hash for APP_PASSWORD_HASH."""
    if not password:
        raise ValueError("Password cannot be empty.")

    salt = salt or secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            _encode(salt),
            _encode(derived_key),
        )
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an scrypt hash without exposing parse errors."""
    try:
        algorithm, n, r, p, encoded_salt, encoded_key = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected_key = _decode(encoded_key)
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(encoded_salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_key),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual_key, expected_key)


def require_login() -> None:
    """Stop rendering unless the visitor has a valid, persistent login."""
    # Streamlit may be launched from outside the repository, so do not rely on
    # its working directory when loading local sign-in settings.
    load_dotenv(dotenv_path=LOCAL_ENV_FILE)
    username = os.getenv("APP_USERNAME")
    password_hash = os.getenv("APP_PASSWORD_HASH")
    session_secret = os.getenv("APP_SESSION_SECRET")

    missing_settings = tuple(
        name
        for name, value in (
            ("APP_USERNAME", username),
            ("APP_PASSWORD_HASH", password_hash),
            ("APP_SESSION_SECRET", session_secret),
        )
        if not value
    )
    if missing_settings:
        st.error(
            "Configuration error: sign-in requires "
            + ", ".join(missing_settings)
            + "."
        )
        st.stop()

    cookies = EncryptedCookieManager(
        prefix=COOKIE_PREFIX,
        key_params_cookie=COOKIE_KEY_PARAMS,
        password=session_secret,
    )
    if not cookies.ready():
        st.stop()

    if _has_valid_session(cookies, username):
        _render_logout(cookies)
        return

    _clear_login(cookies)
    _render_login_form(cookies, username, password_hash)
    st.stop()


def _render_login_form(cookies: EncryptedCookieManager, username: str, password_hash: str) -> None:
    st.title("DietTracker")
    st.caption("Sign in to access your tracker.")
    with st.form("login_form"):
        entered_username = st.text_input("Username", autocomplete="username")
        entered_password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        if hmac.compare_digest(entered_username, username) and verify_password(entered_password, password_hash):
            cookies[LOGIN_USERNAME_COOKIE] = username
            cookies[LOGIN_EXPIRY_COOKIE] = (datetime.now(UTC) + SESSION_LENGTH).isoformat()
            cookies.save()
            st.rerun()
        else:
            st.error("Incorrect username or password.")


def _render_logout(cookies: EncryptedCookieManager) -> None:
    with st.sidebar:
        if st.button("Log out"):
            _clear_login(cookies)
            st.rerun()


def _has_valid_session(cookies: EncryptedCookieManager, username: str) -> bool:
    if not hmac.compare_digest(cookies.get(LOGIN_USERNAME_COOKIE, ""), username):
        return False
    try:
        expiry = datetime.fromisoformat(cookies[LOGIN_EXPIRY_COOKIE])
    except (KeyError, TypeError, ValueError):
        return False
    return expiry.tzinfo is not None and expiry > datetime.now(UTC)


def _clear_login(cookies: EncryptedCookieManager) -> None:
    for key in (LOGIN_USERNAME_COOKIE, LOGIN_EXPIRY_COOKIE):
        cookies.pop(key, None)
    cookies.save()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
