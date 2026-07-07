from __future__ import annotations


def format_minutes(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours == 0:
        return f"{remainder} min"
    return f"{hours}h {remainder:02d}m"


def format_hours(hours: float) -> str:
    return f"{hours:.2f} h"
