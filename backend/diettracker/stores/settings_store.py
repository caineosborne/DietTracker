from __future__ import annotations

import os

from diettracker.config import DEFAULT_DAILY_CALORIE_DEFICIT, DEFAULT_TIMEZONE
from diettracker.database import SCHEMA, connection, initialize_database


class SettingsStore:
    def __init__(self) -> None:
        initialize_database()

    def get_timezone(self) -> str:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(f"SELECT value FROM {SCHEMA}.app_settings WHERE key = %s", ("timezone",))
            row = cursor.fetchone()
        return row["value"] if row else os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)

    def set_timezone(self, timezone_name: str) -> None:
        self._set("timezone", timezone_name)

    def get_daily_calorie_deficit(self) -> int:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(f"SELECT value FROM {SCHEMA}.app_settings WHERE key = %s", ("daily_calorie_deficit",))
            row = cursor.fetchone()
        try:
            return int(row["value"]) if row else DEFAULT_DAILY_CALORIE_DEFICIT
        except (TypeError, ValueError):
            return DEFAULT_DAILY_CALORIE_DEFICIT

    def set_daily_calorie_deficit(self, calories: int) -> None:
        self._set("daily_calorie_deficit", str(calories))

    def _set(self, key: str, value: str) -> None:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.app_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value),
            )
