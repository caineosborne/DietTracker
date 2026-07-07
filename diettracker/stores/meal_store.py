from __future__ import annotations

from datetime import datetime, timedelta

from filelock import FileLock

from diettracker.domain.models import MealLog
from diettracker.paths import MEALS_FILE
from diettracker.stores.base import JsonListStore


class MealStore(JsonListStore[MealLog]):
    def __init__(self) -> None:
        super().__init__(data_file=MEALS_FILE, model_type=MealLog)

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
            filtered_meals = [meal for meal in meals if meal.id != meal_id]
            if len(filtered_meals) == len(meals):
                raise ValueError(f"Meal with id {meal_id} was not found.")
            self.save_all(filtered_meals)

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

