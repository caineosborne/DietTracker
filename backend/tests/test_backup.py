from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from diettracker import backup, database
from diettracker.domain.models import DailyActivityLog, MealLog, WeightLog


@pytest.fixture
def temporary_schema(monkeypatch):
    schema = "diettracker_backup_test"
    monkeypatch.setattr(database, "SCHEMA", schema)
    monkeypatch.setattr(backup, "SCHEMA", schema)
    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield
    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def test_export_and_restore_round_trip(temporary_schema, tmp_path):
    meal = MealLog(
        id="meal-1",
        timestamp=datetime(2026, 8, 1, 12, tzinfo=UTC),
        raw_text="Lunch",
        items=[],
        total_calories_low=500,
        total_calories_mid=600,
        total_calories_high=700,
        created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    activity = DailyActivityLog(
        day=date(2026, 8, 1),
        active_calories=400,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    weight = WeightLog(
        day=date(2026, 8, 1),
        weight_kg=80,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )

    database.initialize_database()
    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {database.SCHEMA}.meals (id, consumed_at, is_small_snack_allowance, payload) VALUES (%s, %s, %s, %s::jsonb)",
            (meal.id, meal.timestamp, meal.is_small_snack_allowance, json.dumps(meal.model_dump(mode="json"))),
        )
        cursor.execute(
            f"INSERT INTO {database.SCHEMA}.daily_activity (day, payload) VALUES (%s, %s::jsonb)",
            (activity.day, json.dumps(activity.model_dump(mode="json"))),
        )
        cursor.execute(
            f"INSERT INTO {database.SCHEMA}.weights (day, payload) VALUES (%s, %s::jsonb)",
            (weight.day, json.dumps(weight.model_dump(mode="json"))),
        )
        cursor.execute(
            f"INSERT INTO {database.SCHEMA}.small_snack_allowance_removals (day) VALUES (%s)",
            (date(2026, 8, 2),),
        )
        cursor.execute(
            f"INSERT INTO {database.SCHEMA}.app_settings (key, value) VALUES (%s, %s)",
            ("timezone", "Asia/Ho_Chi_Minh"),
        )

    backup_path = tmp_path / "diettracker-backup.json"
    assert backup.write_backup(backup_path) == {
        "meals": 1,
        "activity entries": 1,
        "weight entries": 1,
        "removed snack allowances": 1,
        "settings": 1,
    }

    with database.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DELETE FROM {database.SCHEMA}.meals")
        cursor.execute(f"DELETE FROM {database.SCHEMA}.daily_activity")
        cursor.execute(f"DELETE FROM {database.SCHEMA}.weights")
        cursor.execute(f"DELETE FROM {database.SCHEMA}.small_snack_allowance_removals")
        cursor.execute(f"DELETE FROM {database.SCHEMA}.app_settings")

    assert backup.restore_backup(backup_path, replace=True)["meals"] == 1
    restored = backup.export_backup()
    assert restored["meals"] == [meal.model_dump(mode="json")]
    assert restored["daily_activity"] == [activity.model_dump(mode="json")]
    assert restored["weights"] == [weight.model_dump(mode="json")]
    assert restored["small_snack_allowance_removals"] == ["2026-08-02"]
    assert restored["app_settings"] == {"timezone": "Asia/Ho_Chi_Minh"}


def test_version_one_backup_remains_supported(tmp_path):
    backup_path = tmp_path / "version-one.json"
    backup_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "exported_at": "2026-08-20T00:00:00+00:00",
                "meals": [],
                "daily_activity": [],
                "weights": [],
                "small_snack_allowance_removals": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = backup.load_backup(backup_path)

    assert loaded["app_settings"] == {}
