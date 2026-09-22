from datetime import UTC, date, datetime, timedelta
import unittest

from diettracker.config import (
    DAILY_EXPECTATION_START_DAY,
    LEGACY_BASE_DAILY_BURN_CALORIES,
    LEGACY_EXPECTATION_VERSION,
    WEIGHT_BASELINE_DAY,
    estimated_base_daily_burn,
    estimated_bmr_calories,
)
from diettracker.domain.metrics import build_history_metrics, build_week_metrics
from diettracker.domain.models import DailyActivityLog, DailyExpectation, MealLog, WeightLog


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


def weight(day: date, weight_kg: float) -> WeightLog:
    timestamp = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return WeightLog(day=day, weight_kg=weight_kg, created_at=timestamp, updated_at=timestamp)


class IncompleteMealDayMetricsTests(unittest.TestCase):
    def test_base_burn_is_weight_based_and_excludes_active_calories(self) -> None:
        self.assertEqual(estimated_bmr_calories(80), 1700)
        self.assertEqual(estimated_base_daily_burn(80), 2000)
        self.assertEqual(estimated_base_daily_burn(78.2), 1962)

    def test_week_uses_neutral_defaults_for_days_with_fewer_than_two_entries(self) -> None:
        today = date(2026, 7, 8)
        incomplete_day = date(2026, 7, 2)
        complete_day = date(2026, 7, 3)

        metrics = build_week_metrics(
            meals=[meal(incomplete_day, 600, "one"), meal(complete_day, 800, "two"), meal(complete_day, 900, "three")],
            activity_logs=[activity(incomplete_day, 500), activity(complete_day, 300)],
            today=today,
        )

        self.assertEqual(metrics.tracked_days_count, 1)
        base_burn = LEGACY_BASE_DAILY_BURN_CALORIES
        self.assertEqual(metrics.tracked_consumed_total, (6 * base_burn) + 1700)
        self.assertEqual(metrics.total_burn, (6 * base_burn) + base_burn + 300)
        self.assertEqual(metrics.calorie_balance, base_burn - 1700 + 300)

    def test_history_uses_neutral_defaults_and_does_not_project_weight_change(self) -> None:
        incomplete_day = WEIGHT_BASELINE_DAY + timedelta(days=1)
        complete_day = WEIGHT_BASELINE_DAY + timedelta(days=2)
        history = build_history_metrics(
            meals=[meal(incomplete_day, 600, "one"), meal(complete_day, 900, "two"), meal(complete_day, 1000, "three")],
            activity_logs=[activity(incomplete_day, 500), activity(complete_day, 200)],
            weight_logs=[],
            today=complete_day,
        )

        self.assertEqual(history[1].total_intake, LEGACY_BASE_DAILY_BURN_CALORIES)
        self.assertEqual(history[1].total_burn, LEGACY_BASE_DAILY_BURN_CALORIES)
        self.assertEqual(history[1].calorie_balance, 0)
        self.assertEqual(history[2].total_intake, 1900)
        self.assertEqual(history[2].total_burn, LEGACY_BASE_DAILY_BURN_CALORIES + 200)
        self.assertEqual(history[2].expectation_version, LEGACY_EXPECTATION_VERSION)

    def test_new_expectations_are_snapshotted_and_reused(self) -> None:
        generated: list[DailyExpectation] = []
        history = build_history_metrics(
            meals=[],
            activity_logs=[],
            weight_logs=[],
            today=DAILY_EXPECTATION_START_DAY,
            snapshot_through=DAILY_EXPECTATION_START_DAY,
            generated_expectations=generated,
        )

        self.assertEqual(len(generated), 1)
        snapshot = generated[0]
        self.assertEqual(snapshot.day, DAILY_EXPECTATION_START_DAY)
        self.assertEqual(snapshot.base_burn_calories, estimated_base_daily_burn(history[-1].expected_weight_kg))
        self.assertEqual(set(snapshot.model_dump()), {
            "day", "base_burn_calories", "calculation_version",
        })

        rebuilt = build_history_metrics(
            meals=[],
            activity_logs=[],
            weight_logs=[],
            today=DAILY_EXPECTATION_START_DAY,
            daily_expectations=[snapshot],
        )
        self.assertEqual(rebuilt[-1].base_burn_calories, snapshot.base_burn_calories)

    def test_new_snapshot_uses_an_actual_weight_logged_that_day(self) -> None:
        generated: list[DailyExpectation] = []
        history = build_history_metrics(
            meals=[],
            activity_logs=[],
            weight_logs=[weight(DAILY_EXPECTATION_START_DAY, 70)],
            today=DAILY_EXPECTATION_START_DAY,
            snapshot_through=DAILY_EXPECTATION_START_DAY,
            generated_expectations=generated,
        )

        self.assertEqual(generated[0].base_burn_calories, estimated_base_daily_burn(70))
        self.assertEqual(history[-1].base_burn_calories, estimated_base_daily_burn(70))

    def test_legacy_history_ignores_non_legacy_snapshots(self) -> None:
        legacy_day = DAILY_EXPECTATION_START_DAY - timedelta(days=1)
        history = build_history_metrics(
            meals=[],
            activity_logs=[],
            weight_logs=[],
            today=legacy_day,
            daily_expectations=[DailyExpectation(
                day=legacy_day,
                base_burn_calories=9999,
                calculation_version="invalid-for-legacy",
            )],
        )

        self.assertEqual(history[-1].base_burn_calories, LEGACY_BASE_DAILY_BURN_CALORIES)
        self.assertEqual(history[-1].expectation_version, LEGACY_EXPECTATION_VERSION)


if __name__ == "__main__":
    unittest.main()
