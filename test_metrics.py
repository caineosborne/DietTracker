from datetime import UTC, date, datetime, timedelta
import unittest

from diettracker.config import RESTING_CALORIES, WEIGHT_BASELINE_DAY
from diettracker.domain.metrics import build_history_metrics, build_week_metrics
from diettracker.domain.models import DailyActivityLog, MealLog


def meal(day: date, calories: int, identifier: str) -> MealLog:
    timestamp = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    return MealLog(
        id=identifier,
        timestamp=timestamp,
        raw_text="meal",
        items=[],
        total_calories_low=calories,
        total_calories_mid=calories,
        total_calories_high=calories,
        created_at=timestamp,
    )


def activity(day: date, calories: int) -> DailyActivityLog:
    timestamp = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return DailyActivityLog(day=day, active_calories=calories, created_at=timestamp, updated_at=timestamp)


class IncompleteMealDayMetricsTests(unittest.TestCase):
    def test_week_uses_neutral_defaults_for_days_with_fewer_than_two_entries(self) -> None:
        today = date(2026, 7, 8)
        incomplete_day = date(2026, 7, 2)
        complete_day = date(2026, 7, 3)

        metrics = build_week_metrics(
            meals=[meal(incomplete_day, 600, "one"), meal(complete_day, 800, "two"), meal(complete_day, 900, "three")],
            activity_logs=[activity(incomplete_day, 500), activity(complete_day, 300)],
            mood_logs=[], meditation_logs=[], sleep_logs=[], alcohol_logs=[], today=today,
        )

        self.assertEqual(metrics.tracked_days_count, 1)
        self.assertEqual(metrics.tracked_consumed_total, (6 * RESTING_CALORIES) + 1700)
        self.assertEqual(metrics.total_burn, (6 * RESTING_CALORIES) + RESTING_CALORIES + 300)
        self.assertEqual(metrics.calorie_balance, 700)

    def test_history_uses_neutral_defaults_and_does_not_project_weight_change(self) -> None:
        incomplete_day = WEIGHT_BASELINE_DAY + timedelta(days=1)
        complete_day = WEIGHT_BASELINE_DAY + timedelta(days=2)
        history = build_history_metrics(
            meals=[meal(incomplete_day, 600, "one"), meal(complete_day, 900, "two"), meal(complete_day, 1000, "three")],
            activity_logs=[activity(incomplete_day, 500), activity(complete_day, 200)],
            weight_logs=[],
            today=complete_day,
        )

        self.assertEqual(history[1].total_intake, RESTING_CALORIES)
        self.assertEqual(history[1].total_burn, RESTING_CALORIES)
        self.assertEqual(history[1].calorie_balance, 0)
        self.assertEqual(history[2].total_intake, 1900)
        self.assertEqual(history[2].total_burn, RESTING_CALORIES + 200)


if __name__ == "__main__":
    unittest.main()
