from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from filelock import FileLock


from schemas import MealLog

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "meals.json"


class MealStore:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self.lock_file = Path(f"{data_file}.lock")
        self._ensure_store()

    def _ensure_store(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]\n", encoding="utf-8")

    def load_all(self) -> list[MealLog]:
        self._ensure_store()
        raw = self.data_file.read_text(encoding="utf-8").strip()
        if not raw:
            return []

        records = json.loads(raw)
        return [MealLog.model_validate(record) for record in records]

    def save_all(self, meals: list[MealLog]) -> None:
        self._ensure_store()
        payload = [meal.model_dump(mode="json") for meal in meals]

        # Write through a temp file to avoid leaving partial JSON behind if the process stops mid-save.
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.data_file.parent,
            delete=False,
        ) as temp_file:
            json.dump(payload, temp_file, indent=2)
            temp_file.write("\n")
            temp_path = Path(temp_file.name)

        temp_path.replace(self.data_file)

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

            # Replace by id rather than position so day edits remain stable after re-sorting by timestamp.
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
        return [
            meal
            for meal in self.load_all()
            if day_start <= meal.timestamp < day_end
        ]

    def meals_for_week(self, reference: datetime) -> list[MealLog]:
        week_start = (reference - timedelta(days=reference.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        week_end = week_start + timedelta(days=7)
        return [
            meal
            for meal in self.load_all()
            if week_start <= meal.timestamp < week_end
        ]
