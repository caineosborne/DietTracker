from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diettracker.domain.models import DailyActivityLog, MealLog, WeightLog
from diettracker.database import SCHEMA, connection
from diettracker.stores.daily_store import ActivityStore, WeightStore
from diettracker.stores.meal_store import MealStore


def load_records(path: Path, model_type: type[MealLog] | type[DailyActivityLog] | type[WeightLog]) -> list:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    return [model_type.model_validate(record) for record in records]


def remove_duplicate_small_snack_allowances() -> int:
    """Keep the oldest automatic allowance for each day.

    The hosted app can create allowances before an initial JSON import runs. In
    that case, the imported historical allowance and the hosted allowance have
    different IDs but represent the same daily 200-calorie entry.
    """
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"SELECT id, payload FROM {SCHEMA}.meals "
            "WHERE is_small_snack_allowance ORDER BY consumed_at, id"
        )
        allowances = [
            (row["id"], MealLog.model_validate(row["payload"]))
            for row in cursor.fetchall()
        ]

        keepers: dict[object, tuple[str, MealLog]] = {}
        duplicate_ids: list[str] = []
        for meal_id, meal in allowances:
            day = meal.timestamp.date()
            existing = keepers.get(day)
            if existing is None:
                keepers[day] = (meal_id, meal)
            elif meal.created_at < existing[1].created_at:
                duplicate_ids.append(existing[0])
                keepers[day] = (meal_id, meal)
            else:
                duplicate_ids.append(meal_id)

        for meal_id in duplicate_ids:
            cursor.execute(f"DELETE FROM {SCHEMA}.meals WHERE id = %s", (meal_id,))
    return len(duplicate_ids)


def main() -> None:
    if "--clean-allowances" in sys.argv:
        duplicates_removed = remove_duplicate_small_snack_allowances()
        print(f"Removed {duplicates_removed} duplicate small-snack allowances.")
        return

    data_dir = PROJECT_ROOT / "data"
    meal_store = MealStore()
    activity_store = ActivityStore()
    weight_store = WeightStore()

    meals = load_records(data_dir / "meals.json", MealLog)
    activities = load_records(data_dir / "daily_activity.json", DailyActivityLog)
    weights = load_records(data_dir / "weight.json", WeightLog)

    for meal in meals:
        meal_store.append(meal)
    for activity in activities:
        activity_store.upsert(activity)
    for weight in weights:
        weight_store.upsert(weight)

    removals_path = data_dir / "small_snack_allowance_removals.json"
    removed_days = json.loads(removals_path.read_text(encoding="utf-8")) if removals_path.exists() else []
    if removed_days:
        with connection() as conn, conn.cursor() as cursor:
            for day in removed_days:
                cursor.execute(
                    f"INSERT INTO {SCHEMA}.small_snack_allowance_removals (day) VALUES (%s) ON CONFLICT DO NOTHING",
                    (day,),
                )

    duplicates_removed = remove_duplicate_small_snack_allowances()
    print(
        f"Imported {len(meals)} meals, {len(activities)} activity entries, and "
        f"{len(weights)} weight entries. Removed {duplicates_removed} duplicate "
        "small-snack allowances."
    )


if __name__ == "__main__":
    main()
