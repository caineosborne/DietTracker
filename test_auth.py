from datetime import UTC, datetime, timedelta

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
