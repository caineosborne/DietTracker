import pytest
from fastapi.testclient import TestClient

from diettracker import database
from diettracker.api import app
from diettracker.auth import hash_password
from diettracker.stores import daily_store, meal_store, settings_store


@pytest.fixture
def api_database(monkeypatch):
    schema = "diettracker_api_test"
    monkeypatch.setattr(database, "SCHEMA", schema)
    monkeypatch.setattr(meal_store, "SCHEMA", schema)
    monkeypatch.setattr(daily_store, "SCHEMA", schema)
    monkeypatch.setattr(settings_store, "SCHEMA", schema)
    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield
    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def test_health_is_lightweight_and_public() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_private_endpoint_requires_a_session(monkeypatch) -> None:
    monkeypatch.setenv("APP_USERNAME", "test")
    monkeypatch.setenv("APP_PASSWORD_HASH", "configured")
    monkeypatch.setenv("APP_SESSION_SECRET", "secret")
    response = TestClient(app).get("/api/auth/session")
    assert response.status_code == 401


def test_password_login_issues_a_working_signed_session(monkeypatch) -> None:
    monkeypatch.setenv("APP_USERNAME", "test-user")
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("correct-password"))
    monkeypatch.setenv("APP_SESSION_SECRET", "a-long-test-session-secret")
    client = TestClient(app)

    login = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "correct-password"},
    )

    assert login.status_code == 200
    assert login.json()["token"]
    session = client.get(
        "/api/auth/session",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    assert session.status_code == 200
    assert session.json() == {"username": "test-user"}


def test_authenticated_api_round_trip_is_idempotent(monkeypatch, api_database) -> None:
    del api_database
    monkeypatch.setenv("APP_USERNAME", "test-user")
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("correct-password"))
    monkeypatch.setenv("APP_SESSION_SECRET", "a-long-test-session-secret")
    client = TestClient(app)
    token = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "correct-password"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    meal = {
        "request_id": "api-integration-meal-001",
        "raw_text": "Chicken rice bowl",
        "items": [{
            "name": "Chicken rice bowl",
            "calories_low": 540,
            "calories_mid": 620,
            "calories_high": 710,
            "protein_level": "good",
            "confidence": "medium",
            "notes": "",
            "tags": ["lunch"],
        }],
        "consumed_at": "2026-08-20T12:30:00+07:00",
        "summary_notes": "",
        "user_total_override": 620,
        "user_notes": "",
    }

    first = client.post("/api/meals", json=meal, headers=headers)
    retry = client.post("/api/meals", json=meal, headers=headers)
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"] == meal["request_id"]

    assert client.put("/api/activity/2026-08-20", json={"active_calories": 450}, headers=headers).status_code == 200
    assert client.put("/api/weight/2026-08-20", json={"weight_kg": 82.4}, headers=headers).status_code == 200
    dashboard = client.get("/api/dashboard?day=2026-08-20", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert [item["id"] for item in body["meals"]].count(meal["request_id"]) == 1
    assert body["activity"]["active_calories"] == 450
    assert body["weight"]["weight_kg"] == 82.4

    assert client.delete(f"/api/meals/{meal['request_id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/meals/{meal['request_id']}", headers=headers).status_code == 204
