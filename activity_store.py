from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from schemas import DailyActivityLog

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "daily_activity.json"


class ActivityStore:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self._ensure_store()

    def _ensure_store(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]\n", encoding="utf-8")

    def load_all(self) -> list[DailyActivityLog]:
        self._ensure_store()
        raw = self.data_file.read_text(encoding="utf-8").strip()
        if not raw:
            return []

        records = json.loads(raw)
        return [DailyActivityLog.model_validate(record) for record in records]

    def save_all(self, activities: list[DailyActivityLog]) -> None:
        self._ensure_store()
        payload = [activity.model_dump(mode="json") for activity in activities]

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

    def get_for_day(self, day_value: date) -> DailyActivityLog | None:
        for activity in self.load_all():
            if activity.day == day_value:
                return activity
        return None

    def upsert(self, activity_log: DailyActivityLog) -> None:
        activities = self.load_all()
        updated = False

        for index, activity in enumerate(activities):
            if activity.day == activity_log.day:
                activities[index] = activity_log
                updated = True
                break

        if not updated:
            activities.append(activity_log)

        activities.sort(key=lambda record: record.day)
        self.save_all(activities)
