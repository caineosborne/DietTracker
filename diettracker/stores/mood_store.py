from __future__ import annotations

from diettracker.domain.models import MoodEnergyLog
from diettracker.paths import MOOD_FILE
from diettracker.stores.base import AppendOnlyStore


class MoodStore(AppendOnlyStore[MoodEnergyLog]):
    def __init__(self) -> None:
        super().__init__(data_file=MOOD_FILE, model_type=MoodEnergyLog)

