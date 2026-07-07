from __future__ import annotations

from diettracker.domain.models import AlcoholLog, DailyActivityLog, MeditationLog, SleepLog
from diettracker.paths import ACTIVITY_FILE, ALCOHOL_FILE, MEDITATION_FILE, SLEEP_FILE
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

