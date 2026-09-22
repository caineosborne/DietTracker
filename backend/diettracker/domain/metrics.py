from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from diettracker.config import (
    CALORIES_PER_KG,
    DAILY_EXPECTATION_START_DAY,
    LEGACY_BASE_DAILY_BURN_CALORIES,
    LEGACY_EXPECTATION_VERSION,
    WEIGHT_BASELINE_DAY,
    WEIGHT_BASELINE_KG,
    WEIGHT_BASED_EXPECTATION_VERSION,
    app_timezone,
    estimated_base_daily_burn,
)
from diettracker.domain.models import (
    DailyActivityLog,
    DailyExpectation,
    MealLog,
    WeightLog,
)

# A single meal log can be an incomplete record of a day.  Until at least two
# meals have been logged, use a neutral day for aggregate calorie and weight
# calculations rather than projecting a deficit from missing meals.
MINIMUM_MEAL_ENTRIES_PER_DAY = 2


@dataclass(frozen=True)
class DayMetrics:
    total_calories: int
    active_calories: int
    remaining_calories: int
    total_burn: int
    base_burn_calories: int
    expectation_version: str
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
    tracked_consumed_total: int
    total_burn: int
    calorie_balance: int
    expected_weight_delta_kg: float
    weight_direction_label: str
    tracked_days_count: int
    meals_count: int
    activity_days_count: int


@dataclass(frozen=True)
class HistoryDayMetrics:
    day: date
    total_burn: int
    base_burn_calories: int
    expectation_version: str
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
    return datetime.now(tz=app_timezone())


def start_of_day(day_value: date, tzinfo: object) -> datetime:
    return datetime.combine(day_value, datetime.min.time(), tzinfo=tzinfo)


def daily_status(total_calories: int, daily_goal: int) -> str:
    if total_calories < daily_goal - 250:
        return "Low"
    if total_calories <= daily_goal:
        return "Within guide"
    if total_calories <= daily_goal + 400:
        return "Over guide"
    return "High day"


def build_day_metrics(
    meals: list[MealLog],
    activity_log: DailyActivityLog | None,
    actual_weight_log: WeightLog | None,
    anchor_weight_kg: float,
    anchor_day: date,
    expected_weight_kg: float,
    base_burn_calories: int,
    expectation_version: str,
) -> DayMetrics:
    total = sum(meal.total_calories_mid for meal in meals)
    active_calories = activity_log.active_calories if activity_log is not None else 0
    remaining_calories = base_burn_calories - total
    total_burn = base_burn_calories + active_calories
    calorie_balance = total_burn - total
    return DayMetrics(
        total_calories=total,
        active_calories=active_calories,
        remaining_calories=remaining_calories,
        total_burn=total_burn,
        base_burn_calories=base_burn_calories,
        expectation_version=expectation_version,
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
    today: date,
    history: list[HistoryDayMetrics] | None = None,
) -> WeekMetrics:
    window_end = today
    window_start = today - timedelta(days=7)
    days_in_window = (window_end - window_start).days

    window_meals = [
        meal for meal in meals if window_start <= meal.timestamp.astimezone(app_timezone()).date() < window_end
    ]
    activity_logs_by_day = {
        activity.day: activity for activity in activity_logs if window_start <= activity.day < window_end
    }
    meals_by_day: dict[date, list[MealLog]] = {}
    for meal in window_meals:
        meals_by_day.setdefault(meal.timestamp.astimezone(app_timezone()).date(), []).append(meal)

    complete_meal_days = {
        day for day, daily_meals in meals_by_day.items() if len(daily_meals) >= MINIMUM_MEAL_ENTRIES_PER_DAY
    }
    days_in_window_range = [window_start + timedelta(days=offset) for offset in range(days_in_window)]
    history_by_day = {entry.day: entry for entry in history or []}

    def reporting_base_burn(day: date) -> int:
        entry = history_by_day.get(day)
        if entry is not None:
            return entry.base_burn_calories
        if day < DAILY_EXPECTATION_START_DAY:
            return LEGACY_BASE_DAILY_BURN_CALORIES
        return estimated_base_daily_burn(WEIGHT_BASELINE_KG)

    daily_intake = {
        day: sum(meal.total_calories_mid for meal in meals_by_day[day])
        if day in complete_meal_days
        else reporting_base_burn(day)
        for day in days_in_window_range
    }
    daily_burn = {
        day: reporting_base_burn(day) + activity_logs_by_day[day].active_calories
        if day in complete_meal_days and day in activity_logs_by_day
        else reporting_base_burn(day)
        for day in days_in_window_range
    }
    tracked_consumed_total = sum(daily_intake.values())
    total_burn = sum(daily_burn.values())
    calorie_balance = total_burn - tracked_consumed_total

    return WeekMetrics(
        today=today,
        window_start=window_start,
        window_end=window_end,
        average_calories=int(tracked_consumed_total / days_in_window) if days_in_window else 0,
        average_active_calories=int(sum(log.active_calories for log in activity_logs_by_day.values()) / days_in_window) if days_in_window else 0,
        tracked_consumed_total=tracked_consumed_total,
        total_burn=total_burn,
        calorie_balance=calorie_balance,
        expected_weight_delta_kg=abs(calorie_balance) / CALORIES_PER_KG if days_in_window else 0.0,
        weight_direction_label="loss" if calorie_balance >= 0 else "surplus",
        tracked_days_count=len(complete_meal_days),
        meals_count=len(window_meals),
        activity_days_count=len(activity_logs_by_day),
    )


def build_history_day_metrics(
    day: date,
    intake: int,
    active_calories: int,
    anchor_weight_kg: float,
    anchor_day: date,
    expected_weight_kg: float,
    actual_weight_log: WeightLog | None,
    base_burn_calories: int,
    expectation_version: str,
) -> HistoryDayMetrics:
    total_burn = base_burn_calories + active_calories
    calorie_balance = total_burn - intake
    return HistoryDayMetrics(
        day=day,
        total_burn=total_burn,
        base_burn_calories=base_burn_calories,
        expectation_version=expectation_version,
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
    daily_expectations: list[DailyExpectation] | None = None,
    snapshot_through: date | None = None,
    generated_expectations: list[DailyExpectation] | None = None,
) -> list[HistoryDayMetrics]:
    meals_by_day: dict[date, list[MealLog]] = {}
    for meal in meals:
        meal_day = meal.timestamp.astimezone(app_timezone()).date()
        meals_by_day.setdefault(meal_day, []).append(meal)

    activity_by_day = {log.day: log.active_calories for log in activity_logs}
    weights_by_day = {log.day: log for log in weight_logs}
    expectations_by_day = {entry.day: entry for entry in daily_expectations or []}
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
        if current_day < DAILY_EXPECTATION_START_DAY:
            # Ignore any accidental pre-cutover snapshot: legacy reporting is
            # always the original fixed 2,100-calorie model.
            base_burn_calories = LEGACY_BASE_DAILY_BURN_CALORIES
            expectation_version = LEGACY_EXPECTATION_VERSION
        else:
            expectation = expectations_by_day.get(current_day)
            if expectation is None:
                burn_weight_kg = (
                    current_weight_log.weight_kg
                    if current_weight_log is not None
                    else expected_weight_kg
                )
                expectation = DailyExpectation(
                    day=current_day,
                    base_burn_calories=estimated_base_daily_burn(burn_weight_kg),
                    calculation_version=WEIGHT_BASED_EXPECTATION_VERSION,
                )
                if (
                    generated_expectations is not None
                    and (snapshot_through is None or current_day <= snapshot_through)
                ):
                    generated_expectations.append(expectation)
            base_burn_calories = expectation.base_burn_calories
            expectation_version = expectation.calculation_version
        daily_meals = meals_by_day.get(current_day, [])
        has_complete_meal_log = len(daily_meals) >= MINIMUM_MEAL_ENTRIES_PER_DAY
        intake = (
            sum(meal.total_calories_mid for meal in daily_meals)
            if has_complete_meal_log
            else base_burn_calories
        )
        active_calories = activity_by_day.get(current_day, 0) if has_complete_meal_log else 0
        calorie_balance = base_burn_calories + active_calories - intake
        history.append(
            build_history_day_metrics(
                day=current_day,
                intake=intake,
                active_calories=active_calories,
                anchor_weight_kg=anchor_weight_kg,
                anchor_day=anchor_day,
                expected_weight_kg=expected_weight_kg,
                actual_weight_log=current_weight_log,
                base_burn_calories=base_burn_calories,
                expectation_version=expectation_version,
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
