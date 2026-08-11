from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from diettracker.domain.models import DailyActivityLog, MealLog, WeightLog
from diettracker.stores.daily_store import ActivityStore, WeightStore
from diettracker.stores.meal_store import MealStore


def load_records(path: Path, model_type: type[MealLog] | type[DailyActivityLog] | type[WeightLog]) -> list:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    return [model_type.model_validate(record) for record in records]


def main() -> None:
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
        from diettracker.database import SCHEMA, connection

        with connection() as conn, conn.cursor() as cursor:
            for day in removed_days:
                cursor.execute(
                    f"INSERT INTO {SCHEMA}.small_snack_allowance_removals (day) VALUES (%s) ON CONFLICT DO NOTHING",
                    (day,),
                )

    print(f"Imported {len(meals)} meals, {len(activities)} activity entries, and {len(weights)} weight entries.")


if __name__ == "__main__":
    main()
