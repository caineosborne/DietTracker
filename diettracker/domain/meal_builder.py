from __future__ import annotations

from datetime import datetime

from diettracker.domain.models import EstimatedMealItem, MealLog


def build_meal_log(
    *,
    raw_text: str,
    items: list[EstimatedMealItem],
    timestamp: datetime,
    created_at: datetime,
    summary_notes: str = "",
    user_total_override: int | None = None,
    user_notes: str = "",
    meal_id: str | None = None,
) -> MealLog:
    inferred_mid_total = sum(item.calories_mid for item in items)
    override_value = user_total_override if user_total_override is not None else inferred_mid_total
    user_override = override_value if override_value != inferred_mid_total else None
    notes_parts = [summary_notes.strip(), user_notes.strip()]

    meal_data = {
        "timestamp": timestamp,
        "raw_text": raw_text.strip(),
        "items": items,
        "total_calories_low": sum(item.calories_low for item in items),
        "total_calories_mid": override_value,
        "total_calories_high": sum(item.calories_high for item in items),
        "user_override": user_override,
        "notes": " | ".join(part for part in notes_parts if part),
        "created_at": created_at,
    }
    if meal_id is not None:
        meal_data["id"] = meal_id

    return MealLog(**meal_data)
