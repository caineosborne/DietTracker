from __future__ import annotations

import sys

from diettracker.domain.meal_builder import build_meal_log
from diettracker.domain.metrics import get_now_local
from diettracker.services.meal_estimator import MealEstimator
from diettracker.stores.meal_store import MealStore


def main() -> None:
    raw_text = " ".join(sys.argv[1:]).strip()

    if not raw_text:
        raise SystemExit('Usage: uv run python add_meal.py "chicken banh mi"')

    now = get_now_local()
    estimate = MealEstimator().estimate(raw_text, now)
    meal = build_meal_log(
        raw_text=raw_text,
        items=estimate.items,
        timestamp=now,
        created_at=now,
        summary_notes=estimate.summary_notes,
    )
    MealStore().append(meal)

    print("Meal added.")
    print(meal.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
