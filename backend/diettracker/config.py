from __future__ import annotations

import os
from datetime import date
from zoneinfo import ZoneInfo

DEFAULT_MODEL = "gpt-5.4-mini"
DAILY_GOAL_CALORIES = 1900
RESTING_CALORIES = 2100
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
