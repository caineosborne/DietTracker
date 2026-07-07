from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedMoodCommand:
    mood_score: int
    energy_score: int
    notes: str


def parse_mood_command(args: list[str]) -> ParsedMoodCommand:
    if len(args) < 2:
        raise ValueError("Use /mood <mood 0-10> <energy 0-10> <notes>")

    try:
        mood_score = int(args[0])
        energy_score = int(args[1])
    except ValueError as exc:
        raise ValueError("Mood and energy must be whole numbers from 0 to 10.") from exc

    if not (0 <= mood_score <= 10 and 0 <= energy_score <= 10):
        raise ValueError("Mood and energy must be between 0 and 10.")

    return ParsedMoodCommand(
        mood_score=mood_score,
        energy_score=energy_score,
        notes=" ".join(args[2:]).strip(),
    )

