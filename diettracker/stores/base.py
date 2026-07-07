from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generic, TypeVar

from filelock import FileLock
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonListStore(Generic[ModelT]):
    def __init__(self, *, data_file: Path, model_type: type[ModelT]) -> None:
        self.data_file = data_file
        self.lock_file = Path(f"{data_file}.lock")
        self.model_type = model_type
        self._ensure_store()

    def _ensure_store(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]\n", encoding="utf-8")

    def load_all(self) -> list[ModelT]:
        self._ensure_store()
        raw = self.data_file.read_text(encoding="utf-8").strip()
        if not raw:
            return []

        records = json.loads(raw)
        return [self.model_type.model_validate(record) for record in records]

    def save_all(self, records: list[ModelT]) -> None:
        self._ensure_store()
        payload = [record.model_dump(mode="json") for record in records]

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


class AppendOnlyStore(JsonListStore[ModelT], Generic[ModelT]):
    def append(self, record: ModelT) -> None:
        with FileLock(self.lock_file):
            records = self.load_all()
            records.append(record)
            records.sort(key=self.sort_key)
            self.save_all(records)

    def delete(self, record_id: str) -> None:
        with FileLock(self.lock_file):
            records = self.load_all()
            filtered_records = [record for record in records if getattr(record, "id") != record_id]
            if len(filtered_records) == len(records):
                raise ValueError(f"Record with id {record_id} was not found.")
            self.save_all(filtered_records)

    def sort_key(self, record: ModelT) -> object:
        return getattr(record, "timestamp")


class DayLogStore(JsonListStore[ModelT], Generic[ModelT]):
    def get_for_day(self, day_value: date) -> ModelT | None:
        for record in self.load_all():
            if getattr(record, "day") == day_value:
                return record
        return None

    def upsert(self, record: ModelT) -> None:
        with FileLock(self.lock_file):
            records = self.load_all()
            updated = False

            for index, existing_record in enumerate(records):
                if getattr(existing_record, "day") == getattr(record, "day"):
                    records[index] = record
                    updated = True
                    break

            if not updated:
                records.append(record)

            records.sort(key=self.sort_key)
            self.save_all(records)

    def sort_key(self, record: ModelT) -> object:
        return getattr(record, "day")

