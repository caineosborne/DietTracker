from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from diettracker.config import SMALL_SNACK_ALLOWANCE_CALORIES
from diettracker.config import app_timezone
from diettracker.database import SCHEMA, connection, initialize_database
from diettracker.domain.models import EstimatedMealItem, MealLog


class MealStore:
    def __init__(self) -> None:
        initialize_database()

    def load_all(self) -> list[MealLog]:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(f"SELECT payload FROM {SCHEMA}.meals ORDER BY consumed_at")
            return [MealLog.model_validate(row["payload"]) for row in cursor.fetchall()]

    def append(self, meal: MealLog) -> None:
        self._save(meal)

    def update(self, updated_meal: MealLog) -> None:
        payload = json.dumps(json.loads(updated_meal.model_dump_json()))
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.meals
                SET consumed_at = %s, is_small_snack_allowance = %s, payload = %s::jsonb
                WHERE id = %s
                """,
                (
                    updated_meal.timestamp,
                    updated_meal.is_small_snack_allowance,
                    payload,
                    updated_meal.id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Meal with id {updated_meal.id} was not found.")

    def _save(self, meal: MealLog) -> None:
        payload = json.dumps(json.loads(meal.model_dump_json()))
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.meals (id, consumed_at, is_small_snack_allowance, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (meal.id, meal.timestamp, meal.is_small_snack_allowance, payload),
            )

    def delete(self, meal_id: str) -> None:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"SELECT consumed_at, is_small_snack_allowance FROM {SCHEMA}.meals WHERE id = %s",
                (meal_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Meal with id {meal_id} was not found.")
            cursor.execute(f"DELETE FROM {SCHEMA}.meals WHERE id = %s", (meal_id,))
            if row["is_small_snack_allowance"]:
                cursor.execute(
                    f"INSERT INTO {SCHEMA}.small_snack_allowance_removals (day) VALUES (%s) ON CONFLICT DO NOTHING",
                    (row["consumed_at"].astimezone(app_timezone()).date(),),
                )

    def ensure_small_snack_allowances(self, start_day: date, through_day: date, tzinfo: object) -> int:
        if through_day < start_day:
            return 0
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"SELECT (consumed_at AT TIME ZONE %s)::date AS day FROM {SCHEMA}.meals WHERE is_small_snack_allowance",
                (getattr(tzinfo, "key", str(tzinfo)),),
            )
            existing_days = {row["day"] for row in cursor.fetchall()}
            cursor.execute(f"SELECT day FROM {SCHEMA}.small_snack_allowance_removals")
            removed_days = {row["day"] for row in cursor.fetchall()}
        now = datetime.now(tz=tzinfo)
        additions: list[MealLog] = []
        current_day = start_day
        while current_day <= through_day:
            if current_day not in existing_days and current_day not in removed_days:
                timestamp = datetime.combine(current_day, time(hour=20), tzinfo=tzinfo)
                additions.append(
                    MealLog(
                        timestamp=timestamp,
                        raw_text="Small snacks allowance",
                        items=[
                            EstimatedMealItem(
                                name="Small snacks allowance",
                                calories_low=SMALL_SNACK_ALLOWANCE_CALORIES,
                                calories_mid=SMALL_SNACK_ALLOWANCE_CALORIES,
                                calories_high=SMALL_SNACK_ALLOWANCE_CALORIES,
                                protein_level="low",
                                confidence="medium",
                                notes="Automatic daily allowance for small unlogged snacks.",
                                tags=["small-snacks", "allowance"],
                            )
                        ],
                        total_calories_low=SMALL_SNACK_ALLOWANCE_CALORIES,
                        total_calories_mid=SMALL_SNACK_ALLOWANCE_CALORIES,
                        total_calories_high=SMALL_SNACK_ALLOWANCE_CALORIES,
                        notes="Automatic 200-calorie allowance. Delete this entry when it was not needed.",
                        created_at=now,
                        is_small_snack_allowance=True,
                    )
                )
            current_day += timedelta(days=1)
        for meal in additions:
            self.append(meal)
        return len(additions)

    def meals_for_day(self, day_start: datetime) -> list[MealLog]:
        day_end = day_start + timedelta(days=1)
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"SELECT payload FROM {SCHEMA}.meals WHERE consumed_at >= %s AND consumed_at < %s ORDER BY consumed_at",
                (day_start, day_end),
            )
            return [MealLog.model_validate(row["payload"]) for row in cursor.fetchall()]

    def meals_for_week(self, reference: datetime) -> list[MealLog]:
        week_start = (reference - timedelta(days=reference.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        week_end = week_start + timedelta(days=7)
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"SELECT payload FROM {SCHEMA}.meals WHERE consumed_at >= %s AND consumed_at < %s ORDER BY consumed_at",
                (week_start, week_end),
            )
            return [MealLog.model_validate(row["payload"]) for row in cursor.fetchall()]
