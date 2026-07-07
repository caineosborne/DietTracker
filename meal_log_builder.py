from __future__ import annotations

from datetime import datetime

from schemas import MealEstimate, MealLog


def meal_estimate_to_log(
    *,
    raw_text: str,
    estimate: MealEstimate,
    timestamp: datetime,
    created_at: datetime | None = None,
) -> MealLog:
    items = estimate.items

    return MealLog(
        timestamp=timestamp,
        raw_text=raw_text.strip(),
        items=items,
        total_calories_low=sum(item.calories_low for item in items),
        total_calories_mid=sum(item.calories_mid for item in items),
        total_calories_high=sum(item.calories_high for item in items),
        user_override=None,
        notes=estimate.summary_notes.strip(),
        created_at=created_at or timestamp,
    )