from __future__ import annotations

import os
from datetime import date
from zoneinfo import ZoneInfo

DEFAULT_MODEL = "gpt-5.4-mini"
# The estimate uses the expected (projected) weight rather than a fixed calorie
# target.  21.25 kcal/kg gives a 1,700-calorie BMR at 80 kg, matching the
# original planning estimate for this tracker.
BMR_CALORIES_PER_KG = 21.25
BACKGROUND_MOVEMENT_CALORIES = 300
DEFAULT_DAILY_CALORIE_DEFICIT = 500
CALORIES_PER_KG = 7000
WEIGHT_BASELINE_DAY = date(2026, 6, 28)
WEIGHT_BASELINE_KG = 85.3
SMALL_SNACK_ALLOWANCE_START_DAY = date(2026, 7, 14)
SMALL_SNACK_ALLOWANCE_CALORIES = 200

DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
SUPPORTED_TIMEZONES = ("Asia/Ho_Chi_Minh", "Australia/Brisbane", "UTC")
_configured_timezone: str | None = None


def configure_timezone(timezone_name: str) -> None:
    if timezone_name not in SUPPORTED_TIMEZONES:
        raise ValueError(f"Unsupported timezone: {timezone_name}")
    ZoneInfo(timezone_name)
    global _configured_timezone
    _configured_timezone = timezone_name


def app_timezone_name() -> str:
    return _configured_timezone or os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)


def app_timezone() -> ZoneInfo:
    timezone_name = app_timezone_name()
    if timezone_name not in SUPPORTED_TIMEZONES:
        raise ValueError(
            f"APP_TIMEZONE must be one of {', '.join(SUPPORTED_TIMEZONES)}; got {timezone_name!r}"
        )
    return ZoneInfo(timezone_name)


def estimated_bmr_calories(weight_kg: float) -> int:
    return round(weight_kg * BMR_CALORIES_PER_KG)


def estimated_base_daily_burn(weight_kg: float) -> int:
    """BMR plus normal day-to-day movement, excluding deliberate activity."""
    return estimated_bmr_calories(weight_kg) + BACKGROUND_MOVEMENT_CALORIES
