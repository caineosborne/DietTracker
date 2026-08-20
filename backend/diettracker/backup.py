from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from diettracker.database import SCHEMA, connection, initialize_database
from diettracker.domain.models import DailyActivityLog, MealLog, WeightLog


BACKUP_FORMAT_VERSION = 1


def export_backup() -> dict[str, Any]:
    """Return a complete, portable snapshot of DietTracker's database."""
    initialize_database()
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"SELECT payload FROM {SCHEMA}.meals ORDER BY consumed_at, id")
        meals = [MealLog.model_validate(row["payload"]).model_dump(mode="json") for row in cursor.fetchall()]

        cursor.execute(f"SELECT payload FROM {SCHEMA}.daily_activity ORDER BY day")
        activities = [
            DailyActivityLog.model_validate(row["payload"]).model_dump(mode="json")
            for row in cursor.fetchall()
        ]

        cursor.execute(f"SELECT payload FROM {SCHEMA}.weights ORDER BY day")
        weights = [WeightLog.model_validate(row["payload"]).model_dump(mode="json") for row in cursor.fetchall()]

        cursor.execute(f"SELECT day FROM {SCHEMA}.small_snack_allowance_removals ORDER BY day")
        removed_allowance_days = [row["day"].isoformat() for row in cursor.fetchall()]

    return {
        "format_version": BACKUP_FORMAT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "meals": meals,
        "daily_activity": activities,
        "weights": weights,
        "small_snack_allowance_removals": removed_allowance_days,
    }


def write_backup(path: Path) -> dict[str, int]:
    backup = export_backup()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")
    return backup_counts(backup)


def load_backup(path: Path) -> dict[str, Any]:
    backup = json.loads(path.read_text(encoding="utf-8"))
    if backup.get("format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("This is not a supported DietTracker backup file.")

    required_lists = ("meals", "daily_activity", "weights", "small_snack_allowance_removals")
    if any(not isinstance(backup.get(name), list) for name in required_lists):
        raise ValueError("This backup file is missing DietTracker data.")
    return backup


def restore_backup(path: Path, *, replace: bool) -> dict[str, int]:
    """Restore a backup, optionally replacing all existing DietTracker records."""
    backup = load_backup(path)
    meals = [MealLog.model_validate(item) for item in backup["meals"]]
    activities = [DailyActivityLog.model_validate(item) for item in backup["daily_activity"]]
    weights = [WeightLog.model_validate(item) for item in backup["weights"]]
    removed_days = backup["small_snack_allowance_removals"]

    initialize_database()
    with connection() as conn, conn.cursor() as cursor:
        if replace:
            cursor.execute(f"DELETE FROM {SCHEMA}.small_snack_allowance_removals")
            cursor.execute(f"DELETE FROM {SCHEMA}.weights")
            cursor.execute(f"DELETE FROM {SCHEMA}.daily_activity")
            cursor.execute(f"DELETE FROM {SCHEMA}.meals")

        for meal in meals:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.meals (id, consumed_at, is_small_snack_allowance, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                SET consumed_at = EXCLUDED.consumed_at,
                    is_small_snack_allowance = EXCLUDED.is_small_snack_allowance,
                    payload = EXCLUDED.payload
                """,
                (
                    meal.id,
                    meal.timestamp,
                    meal.is_small_snack_allowance,
                    json.dumps(meal.model_dump(mode="json")),
                ),
            )

        day_records = [(record, "daily_activity") for record in activities]
        day_records.extend((record, "weights") for record in weights)
        for record, table in day_records:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.{table} (day, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (day) DO UPDATE SET payload = EXCLUDED.payload
                """,
                (record.day, json.dumps(record.model_dump(mode="json"))),
            )

        for day in removed_days:
            cursor.execute(
                f"INSERT INTO {SCHEMA}.small_snack_allowance_removals (day) VALUES (%s) ON CONFLICT DO NOTHING",
                (day,),
            )

    return backup_counts(backup)


def backup_counts(backup: dict[str, Any]) -> dict[str, int]:
    return {
        "meals": len(backup["meals"]),
        "activity entries": len(backup["daily_activity"]),
        "weight entries": len(backup["weights"]),
        "removed snack allowances": len(backup["small_snack_allowance_removals"]),
    }
