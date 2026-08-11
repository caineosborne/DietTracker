from datetime import UTC, datetime, timedelta

import pytest

import diettracker.auth as auth
from diettracker.auth import _has_valid_session, hash_password, verify_password


def test_password_hash_verifies_the_original_password() -> None:
    password_hash = hash_password("correct horse battery staple", salt=b"0123456789abcdef")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_invalid_password_hash_is_rejected() -> None:
    assert not verify_password("anything", "not-a-password-hash")


def test_login_session_requires_the_right_user_and_a_future_expiry() -> None:
    cookies = {
        "login_username": "caine",
        "login_expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }

    assert _has_valid_session(cookies, "caine")
    assert not _has_valid_session(cookies, "someone-else")


def test_require_login_stops_before_rendering_when_settings_are_missing(monkeypatch) -> None:
    errors: list[str] = []

    monkeypatch.setattr(auth, "load_dotenv", lambda **_: True)
    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("APP_SESSION_SECRET", raising=False)
    monkeypatch.setattr(auth.st, "error", errors.append)
    monkeypatch.setattr(auth.st, "stop", lambda: (_ for _ in ()).throw(RuntimeError("stopped")))

    with pytest.raises(RuntimeError, match="stopped"):
        auth.require_login()

    assert errors == [
        "Configuration error: sign-in requires APP_USERNAME, APP_PASSWORD_HASH, APP_SESSION_SECRET."
    ]


def test_require_login_loads_local_env_before_checking_settings(monkeypatch) -> None:
    loaded_paths = []
    rendered_settings = []

    def load_local_env(*, dotenv_path):
        loaded_paths.append(dotenv_path)
        monkeypatch.setenv("APP_USERNAME", "test-user")
        monkeypatch.setenv("APP_PASSWORD_HASH", "test-hash")
        monkeypatch.setenv("APP_SESSION_SECRET", "test-secret")

    class Cookies:
        def ready(self):
            return True

    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("APP_SESSION_SECRET", raising=False)
    monkeypatch.setattr(auth, "load_dotenv", load_local_env)
    monkeypatch.setattr(auth, "EncryptedCookieManager", lambda **_: Cookies())
    monkeypatch.setattr(auth, "_has_valid_session", lambda *_: False)
    monkeypatch.setattr(auth, "_clear_login", lambda _: None)
    monkeypatch.setattr(auth, "_render_login_form", lambda *args: rendered_settings.append(args[1:]))
    monkeypatch.setattr(auth.st, "stop", lambda: (_ for _ in ()).throw(RuntimeError("stopped")))

    with pytest.raises(RuntimeError, match="stopped"):
        auth.require_login()

    assert loaded_paths == [auth.LOCAL_ENV_FILE]
    assert rendered_settings == [("test-user", "test-hash")]
