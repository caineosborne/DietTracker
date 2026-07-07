# add_meal.py

from __future__ import annotations

import sys
from datetime import datetime

from meal_estimator import MealEstimator
from meal_log_builder import meal_estimate_to_log
from meal_store import MealStore


def main() -> None:
    raw_text = " ".join(sys.argv[1:]).strip()

    if not raw_text:
        raise SystemExit('Usage: uv run python add_meal.py "chicken banh mi"')

    now = datetime.now().astimezone()

    estimate = MealEstimator().estimate(raw_text, now)

    meal = meal_estimate_to_log(
        raw_text=raw_text,
        estimate=estimate,
        timestamp=now,
    )

    MealStore().append(meal)

    print("Meal added.")
    print(meal.model_dump_json(indent=2))


if __name__ == "__main__":
    main()