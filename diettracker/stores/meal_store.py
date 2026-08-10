from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from filelock import FileLock

from diettracker.config import SMALL_SNACK_ALLOWANCE_CALORIES
from diettracker.domain.models import EstimatedMealItem, MealLog
from diettracker.paths import MEALS_FILE, SMALL_SNACK_ALLOWANCE_REMOVALS_FILE
from diettracker.stores.base import JsonListStore


class MealStore(JsonListStore[MealLog]):
    def __init__(self) -> None:
        super().__init__(data_file=MEALS_FILE, model_type=MealLog)
        self.small_snack_allowance_removals_file = SMALL_SNACK_ALLOWANCE_REMOVALS_FILE
        self.small_snack_allowance_removals_lock_file = Path(
            f"{self.small_snack_allowance_removals_file}.lock"
        )

    def append(self, meal: MealLog) -> None:
        with FileLock(self.lock_file):
            meals = self.load_all()
            meals.append(meal)
            meals.sort(key=lambda record: record.timestamp)
            self.save_all(meals)

    def update(self, updated_meal: MealLog) -> None:
        with FileLock(self.lock_file):
            meals = self.load_all()
            updated = False

            for index, meal in enumerate(meals):
                if meal.id == updated_meal.id:
                    meals[index] = updated_meal
                    updated = True
                    break

            if not updated:
                raise ValueError(f"Meal with id {updated_meal.id} was not found.")

            meals.sort(key=lambda record: record.timestamp)
            self.save_all(meals)

    def delete(self, meal_id: str) -> None:
        with FileLock(self.lock_file):
            meals = self.load_all()
            meal_to_delete = next((meal for meal in meals if meal.id == meal_id), None)
            if meal_to_delete is None:
                raise ValueError(f"Meal with id {meal_id} was not found.")

            if meal_to_delete.is_small_snack_allowance:
                self._remember_small_snack_allowance_removal(meal_to_delete.timestamp.date())

            filtered_meals = [meal for meal in meals if meal.id != meal_id]
            self.save_all(filtered_meals)

    def ensure_small_snack_allowances(self, start_day: date, through_day: date, tzinfo: object) -> int:
        """Create one removable 200-calorie allowance for every applicable day.

        Deleted allowances are recorded separately so they do not reappear on a
        later app load.
        """
        if through_day < start_day:
            return 0

        with FileLock(self.lock_file):
            meals = self.load_all()
            existing_days = {
                meal.timestamp.date() for meal in meals if meal.is_small_snack_allowance
            }
            removed_days = self._load_small_snack_allowance_removals()
            now = datetime.now(tz=tzinfo)
            additions: list[MealLog] = []
            current_day = start_day

            while current_day <= through_day:
                if current_day not in existing_days and current_day not in removed_days:
                    timestamp = datetime.combine(current_day, time(hour=20), tzinfo=tzinfo)
                    additions.append(
                        MealLog(
                            timestamp=timestamp,
                            raw_text="Small snacks allowance",
                            items=[
                                EstimatedMealItem(
                                    name="Small snacks allowance",
                                    calories_low=SMALL_SNACK_ALLOWANCE_CALORIES,
                                    calories_mid=SMALL_SNACK_ALLOWANCE_CALORIES,
                                    calories_high=SMALL_SNACK_ALLOWANCE_CALORIES,
                                    protein_level="low",
                                    confidence="medium",
                                    notes="Automatic daily allowance for small unlogged snacks.",
                                    tags=["small-snacks", "allowance"],
                                )
                            ],
                            total_calories_low=SMALL_SNACK_ALLOWANCE_CALORIES,
                            total_calories_mid=SMALL_SNACK_ALLOWANCE_CALORIES,
                            total_calories_high=SMALL_SNACK_ALLOWANCE_CALORIES,
                            notes="Automatic 200-calorie allowance. Delete this entry when it was not needed.",
                            created_at=now,
                            is_small_snack_allowance=True,
                        )
                    )
                current_day += timedelta(days=1)

            if additions:
                meals.extend(additions)
                meals.sort(key=lambda record: record.timestamp)
                self.save_all(meals)

            return len(additions)

    def _load_small_snack_allowance_removals(self) -> set[date]:
        if not self.small_snack_allowance_removals_file.exists():
            return set()
        raw = self.small_snack_allowance_removals_file.read_text(encoding="utf-8").strip()
        return {date.fromisoformat(value) for value in json.loads(raw)} if raw else set()

    def _remember_small_snack_allowance_removal(self, day: date) -> None:
        with FileLock(self.small_snack_allowance_removals_lock_file):
            removed_days = self._load_small_snack_allowance_removals()
            if day in removed_days:
                return
            removed_days.add(day)
            self.small_snack_allowance_removals_file.parent.mkdir(parents=True, exist_ok=True)
            self.small_snack_allowance_removals_file.write_text(
                json.dumps(sorted(value.isoformat() for value in removed_days), indent=2) + "\n",
                encoding="utf-8",
            )

    def meals_for_day(self, day_start: datetime) -> list[MealLog]:
        day_end = day_start + timedelta(days=1)
        return [meal for meal in self.load_all() if day_start <= meal.timestamp < day_end]

    def meals_for_week(self, reference: datetime) -> list[MealLog]:
        week_start = (reference - timedelta(days=reference.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        week_end = week_start + timedelta(days=7)
        return [meal for meal in self.load_all() if week_start <= meal.timestamp < week_end]
