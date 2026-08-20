from datetime import UTC, datetime, timedelta

from diettracker.auth import create_session_token, hash_password, verify_password, verify_session_token


def test_password_hash_verifies_the_original_password() -> None:
    password_hash = hash_password("correct horse battery staple", salt=b"0123456789abcdef")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_invalid_password_hash_is_rejected() -> None:
    assert not verify_password("anything", "not-a-password-hash")


def test_signed_session_requires_the_right_user_secret_and_future_expiry() -> None:
    now = datetime(2026, 8, 20, tzinfo=UTC)
    token = create_session_token("caine", "a-long-secret", now=now)

    assert verify_session_token(token, "caine", "a-long-secret", now=now)
    assert not verify_session_token(token, "someone-else", "a-long-secret", now=now)
    assert not verify_session_token(token, "caine", "wrong-secret", now=now)
    assert not verify_session_token(token, "caine", "a-long-secret", now=now + timedelta(days=31))


def test_modified_session_is_rejected() -> None:
    token = create_session_token("caine", "a-long-secret")
    encoded, signature = token.split(".")
    assert not verify_session_token(f"{encoded}x.{signature}", "caine", "a-long-secret")
