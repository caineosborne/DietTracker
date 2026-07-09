from __future__ import annotations

from diettracker.config import WEIGHT_BASELINE_DAY, WEIGHT_BASELINE_KG
from diettracker.domain.models import AlcoholLog, DailyActivityLog, MeditationLog, SleepLog, WeightLog
from diettracker.paths import ACTIVITY_FILE, ALCOHOL_FILE, MEDITATION_FILE, SLEEP_FILE, WEIGHT_FILE
from diettracker.stores.base import DayLogStore


class ActivityStore(DayLogStore[DailyActivityLog]):
    def __init__(self) -> None:
        super().__init__(data_file=ACTIVITY_FILE, model_type=DailyActivityLog)


class MeditationStore(DayLogStore[MeditationLog]):
    def __init__(self) -> None:
        super().__init__(data_file=MEDITATION_FILE, model_type=MeditationLog)


class SleepStore(DayLogStore[SleepLog]):
    def __init__(self) -> None:
        super().__init__(data_file=SLEEP_FILE, model_type=SleepLog)


class AlcoholStore(DayLogStore[AlcoholLog]):
    def __init__(self) -> None:
        super().__init__(data_file=ALCOHOL_FILE, model_type=AlcoholLog)


class WeightStore(DayLogStore[WeightLog]):
    def __init__(self) -> None:
        super().__init__(data_file=WEIGHT_FILE, model_type=WeightLog)
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
