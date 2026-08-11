from __future__ import annotations

import json
from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel

from diettracker.config import WEIGHT_BASELINE_DAY, WEIGHT_BASELINE_KG
from diettracker.database import SCHEMA, connection, initialize_database
from diettracker.domain.models import DailyActivityLog, WeightLog

ModelT = TypeVar("ModelT", bound=BaseModel)


class PostgresDayStore(Generic[ModelT]):
    def __init__(self, *, table: str, model_type: type[ModelT]) -> None:
        initialize_database()
        self.table = table
        self.model_type = model_type

    def load_all(self) -> list[ModelT]:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(f"SELECT payload FROM {SCHEMA}.{self.table} ORDER BY day")
            return [self.model_type.model_validate(row["payload"]) for row in cursor.fetchall()]

    def get_for_day(self, day_value: date) -> ModelT | None:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"SELECT payload FROM {SCHEMA}.{self.table} WHERE day = %s", (day_value,)
            )
            row = cursor.fetchone()
            return self.model_type.model_validate(row["payload"]) if row else None

    def upsert(self, record: ModelT) -> None:
        payload = json.loads(record.model_dump_json())
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.{self.table} (day, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (day) DO UPDATE SET payload = EXCLUDED.payload
                """,
                (getattr(record, "day"), json.dumps(payload)),
            )


class ActivityStore(PostgresDayStore[DailyActivityLog]):
    def __init__(self) -> None:
        super().__init__(table="daily_activity", model_type=DailyActivityLog)


class WeightStore(PostgresDayStore[WeightLog]):
    def __init__(self) -> None:
        super().__init__(table="weights", model_type=WeightLog)
        self._ensure_baseline_entry()

    def _ensure_baseline_entry(self) -> None:
        if self.get_for_day(WEIGHT_BASELINE_DAY) is not None:
            return

        from diettracker.domain.metrics import get_now_local

        now_local = get_now_local()
        self.upsert(
            WeightLog(
                day=WEIGHT_BASELINE_DAY,
                weight_kg=WEIGHT_BASELINE_KG,
                created_at=now_local,
                updated_at=now_local,
            )
        )
