from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from diettracker.config import (
    CALORIES_PER_KG,
    DAILY_GOAL_CALORIES,
    RESTING_CALORIES,
    WEIGHT_BASELINE_DAY,
    WEIGHT_BASELINE_KG,
)
from diettracker.domain.models import (
    AlcoholLog,
    DailyActivityLog,
    EstimatedMealItem,
    MealLog,
    MeditationLog,
    MoodEnergyLog,
    SleepLog,
    WeightLog,
)

TREAT_KEYWORDS = {
    "ice cream",
    "icecream",
    "dessert",
    "chocolate",
    "cake",
    "cookie",
    "candy",
    "brownie",
    "donut",
    "pastry",
    "pudding",
    "sundae",
    "gelato",
    "muffin",
    "tart",
    "pie",
}


@dataclass(frozen=True)
class DayMetrics:
    total_calories: int
    active_calories: int
    remaining_calories: int
    total_burn: int
    calorie_balance: int
    expected_weight_delta_kg: float
    weight_direction_label: str
    anchor_weight_kg: float
    anchor_day: date
    actual_weight_kg: float | None
    actual_weight_delta_kg: float | None
    expected_weight_kg: float
    weight_difference_kg: float | None


@dataclass(frozen=True)
class WeekMetrics:
    today: date
    window_start: date
    window_end: date
    average_calories: int
    average_active_calories: int
    average_sleep_score: int
    total_meditation: int
    average_mood: float
    average_energy: float
    total_drinks: int
    tracked_consumed_total: int
    total_burn: int
    calorie_balance: int
    expected_weight_delta_kg: float
    weight_direction_label: str
    tracked_days_count: int
    meals_count: int
    activity_days_count: int
    sleep_days_count: int
    meditation_days_count: int
    mood_entries_count: int
    alcohol_days_count: int


@dataclass(frozen=True)
class HistoryDayMetrics:
    day: date
    total_burn: int
    total_intake: int
    calorie_balance: int
    expected_weight_delta_kg: float
    weight_direction_label: str
    anchor_weight_kg: float
    anchor_day: date
    expected_weight_kg: float
    actual_weight_kg: float | None
    actual_weight_delta_kg: float | None
    weight_difference_kg: float | None


@dataclass(frozen=True)
class HistorySummaryMetrics:
    label: str
    days_count: int
    total_burn: int
    total_intake: int
    calorie_balance: int
    expected_weight_delta_kg: float
    weight_direction_label: str
    anchor_weight_kg: float
    anchor_day: date
    expected_weight_kg: float
    latest_actual_weight_kg: float | None
    actual_weight_delta_kg: float | None
    weight_difference_kg: float | None


def get_now_local() -> datetime:
    return datetime.now().astimezone()


def start_of_day(day_value: date, tzinfo: object) -> datetime:
    return datetime.combine(day_value, datetime.min.time(), tzinfo=tzinfo)


def daily_status(total_calories: int) -> str:
    if total_calories < 1800:
        return "Low"
    if total_calories <= 2200:
        return "Good deficit"
    if total_calories <= 2600:
        return "Maintenance-ish"
    return "High day"


def guess_protein_quality(items: list[EstimatedMealItem]) -> str:
    if not items:
        return "low"

    levels = [item.protein_level for item in items]
    good_count = sum(level == "good" for level in levels)
    medium_or_better = sum(level in {"medium", "good"} for level in levels)

    if good_count >= 1 and medium_or_better >= max(1, len(levels) // 2):
        return "good"
    if medium_or_better >= max(1, len(levels) // 2):
        return "medium"
    return "low"


def count_matching_items(items: list[EstimatedMealItem], keywords: set[str]) -> int:
    count = 0
    for item in items:
        text = " ".join([item.name, item.notes]).lower()
        tags = {tag.lower() for tag in item.tags}
        if any(
            keyword in tags or re.search(rf"\b{re.escape(keyword)}\b", text) is not None
            for keyword in keywords
        ):
            count += 1
    return count


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_day_metrics(
    meals: list[MealLog],
    activity_log: DailyActivityLog | None,
    actual_weight_log: WeightLog | None,
    anchor_weight_kg: float,
    anchor_day: date,
    expected_weight_kg: float,
) -> DayMetrics:
    total = sum(meal.total_calories_mid for meal in meals)
    active_calories = activity_log.active_calories if activity_log is not None else 0
    remaining_calories = DAILY_GOAL_CALORIES - total
    total_burn = RESTING_CALORIES + active_calories
    calorie_balance = total_burn - total
    return DayMetrics(
        total_calories=total,
        active_calories=active_calories,
        remaining_calories=remaining_calories,
        total_burn=total_burn,
        calorie_balance=calorie_balance,
        expected_weight_delta_kg=abs(calorie_balance) / CALORIES_PER_KG,
        weight_direction_label="Est. loss" if calorie_balance >= 0 else "Est. surplus",
        anchor_weight_kg=anchor_weight_kg,
        anchor_day=anchor_day,
        actual_weight_kg=actual_weight_log.weight_kg if actual_weight_log is not None else None,
        actual_weight_delta_kg=(
            anchor_weight_kg - actual_weight_log.weight_kg if actual_weight_log is not None else None
        ),
        expected_weight_kg=expected_weight_kg,
        weight_difference_kg=(
            actual_weight_log.weight_kg - expected_weight_kg if actual_weight_log is not None else None
        ),
    )


def build_week_metrics(
    *,
    meals: list[MealLog],
    activity_logs: list[DailyActivityLog],
    mood_logs: list[MoodEnergyLog],
    meditation_logs: list[MeditationLog],
    sleep_logs: list[SleepLog],
    alcohol_logs: list[AlcoholLog],
    today: date,
) -> WeekMetrics:
    window_end = today
    window_start = today - timedelta(days=7)
    days_in_window = (window_end - window_start).days

    window_meals = [
        meal for meal in meals if window_start <= meal.timestamp.astimezone().date() < window_end
    ]
    activity_logs_by_day = {
        activity.day: activity for activity in activity_logs if window_start <= activity.day < window_end
    }
    window_mood_logs = [
        log for log in mood_logs if window_start <= log.timestamp.astimezone().date() < window_end
    ]
    meditation_logs_by_day = {
        log.day: log for log in meditation_logs if window_start <= log.day < window_end
    }
    sleep_logs_by_day = {log.day: log for log in sleep_logs if window_start <= log.day < window_end}
    alcohol_logs_by_day = {log.day: log for log in alcohol_logs if window_start <= log.day < window_end}
    tracked_days = sorted(activity_logs_by_day)
    tracked_meals = [
        meal for meal in window_meals if meal.timestamp.astimezone().date() in activity_logs_by_day
    ]
    tracked_consumed_total = sum(meal.total_calories_mid for meal in tracked_meals)
    total_burn = sum(RESTING_CALORIES + activity_logs_by_day[day].active_calories for day in tracked_days)
    calorie_balance = total_burn - tracked_consumed_total

    return WeekMetrics(
        today=today,
        window_start=window_start,
        window_end=window_end,
        average_calories=int(sum(meal.total_calories_mid for meal in window_meals) / days_in_window) if days_in_window else 0,
        average_active_calories=int(sum(log.active_calories for log in activity_logs_by_day.values()) / days_in_window) if days_in_window else 0,
        average_sleep_score=int(average([float(log.sleep_score) for log in sleep_logs_by_day.values()])),
        total_meditation=sum(log.duration_minutes for log in meditation_logs_by_day.values()),
        average_mood=average([float(log.mood_score) for log in window_mood_logs]),
        average_energy=average([float(log.energy_score) for log in window_mood_logs]),
        total_drinks=sum(log.standard_drinks for log in alcohol_logs_by_day.values()),
        tracked_consumed_total=tracked_consumed_total,
        total_burn=total_burn,
        calorie_balance=calorie_balance,
        expected_weight_delta_kg=abs(calorie_balance) / CALORIES_PER_KG if tracked_days else 0.0,
        weight_direction_label="loss" if calorie_balance >= 0 else "surplus",
        tracked_days_count=len(tracked_days),
        meals_count=len(window_meals),
        activity_days_count=len(activity_logs_by_day),
        sleep_days_count=len(sleep_logs_by_day),
        meditation_days_count=len(meditation_logs_by_day),
        mood_entries_count=len(window_mood_logs),
        alcohol_days_count=len(alcohol_logs_by_day),
    )


def build_history_day_metrics(
    day: date,
    intake: int,
    active_calories: int,
    anchor_weight_kg: float,
    anchor_day: date,
    expected_weight_kg: float,
    actual_weight_log: WeightLog | None,
) -> HistoryDayMetrics:
    total_burn = RESTING_CALORIES + active_calories
    calorie_balance = total_burn - intake
    return HistoryDayMetrics(
        day=day,
        total_burn=total_burn,
        total_intake=intake,
        calorie_balance=calorie_balance,
        expected_weight_delta_kg=abs(calorie_balance) / CALORIES_PER_KG,
        weight_direction_label="Est. loss" if calorie_balance >= 0 else "Est. gain",
        anchor_weight_kg=anchor_weight_kg,
        anchor_day=anchor_day,
        expected_weight_kg=expected_weight_kg,
        actual_weight_kg=actual_weight_log.weight_kg if actual_weight_log is not None else None,
        actual_weight_delta_kg=(
            anchor_weight_kg - actual_weight_log.weight_kg if actual_weight_log is not None else None
        ),
        weight_difference_kg=(
            actual_weight_log.weight_kg - expected_weight_kg if actual_weight_log is not None else None
        ),
    )


def build_history_metrics(
    *,
    meals: list[MealLog],
    activity_logs: list[DailyActivityLog],
    weight_logs: list[WeightLog],
    today: date,
) -> list[HistoryDayMetrics]:
    meals_by_day: dict[date, int] = {}
    for meal in meals:
        meal_day = meal.timestamp.astimezone().date()
        meals_by_day[meal_day] = meals_by_day.get(meal_day, 0) + meal.total_calories_mid

    activity_by_day = {log.day: log.active_calories for log in activity_logs}
    weights_by_day = {log.day: log for log in weight_logs}
    tracked_days = sorted(set(meals_by_day) | set(activity_by_day) | set(weights_by_day) | {WEIGHT_BASELINE_DAY})
    if not tracked_days:
        return []

    start_day = min(tracked_days[0], WEIGHT_BASELINE_DAY)
    total_days = (today - start_day).days + 1
    history: list[HistoryDayMetrics] = []
    anchor_weight_kg = WEIGHT_BASELINE_KG
    anchor_day = WEIGHT_BASELINE_DAY
    expected_weight_kg = WEIGHT_BASELINE_KG
    for offset in range(total_days):
        current_day = start_day + timedelta(days=offset)
        current_weight_log = weights_by_day.get(current_day)
        intake = meals_by_day.get(current_day, 0)
        active_calories = activity_by_day.get(current_day, 0)
        calorie_balance = RESTING_CALORIES + active_calories - intake
        history.append(
            build_history_day_metrics(
                day=current_day,
                intake=intake,
                active_calories=active_calories,
                anchor_weight_kg=anchor_weight_kg,
                anchor_day=anchor_day,
                expected_weight_kg=expected_weight_kg,
                actual_weight_log=current_weight_log,
            )
        )

        if current_weight_log is not None:
            anchor_weight_kg = current_weight_log.weight_kg
            anchor_day = current_day
            expected_weight_kg = anchor_weight_kg

        expected_weight_kg -= calorie_balance / CALORIES_PER_KG
    return history


def summarize_history_metrics(
    *,
    label: str,
    history: list[HistoryDayMetrics],
    days: int | None = None,
) -> HistorySummaryMetrics:
    window = history if days is None else history[-days:]
    total_burn = sum(day.total_burn for day in window)
    total_intake = sum(day.total_intake for day in window)
    calorie_balance = total_burn - total_intake
    latest_actual_entry = next((day for day in reversed(window) if day.actual_weight_kg is not None), None)
    return HistorySummaryMetrics(
        label=label,
        days_count=len(window),
        total_burn=total_burn,
        total_intake=total_intake,
        calorie_balance=calorie_balance,
        expected_weight_delta_kg=abs(calorie_balance) / CALORIES_PER_KG if window else 0.0,
        weight_direction_label="Est. loss" if calorie_balance >= 0 else "Est. gain",
        anchor_weight_kg=window[-1].anchor_weight_kg if window else WEIGHT_BASELINE_KG,
        anchor_day=window[-1].anchor_day if window else WEIGHT_BASELINE_DAY,
        expected_weight_kg=window[-1].expected_weight_kg if window else WEIGHT_BASELINE_KG,
        latest_actual_weight_kg=latest_actual_entry.actual_weight_kg if latest_actual_entry is not None else None,
        actual_weight_delta_kg=latest_actual_entry.actual_weight_delta_kg if latest_actual_entry is not None else None,
        weight_difference_kg=latest_actual_entry.weight_difference_kg if latest_actual_entry is not None else None,
    )
