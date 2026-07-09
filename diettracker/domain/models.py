from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

ProteinLevel = Literal["low", "medium", "good"]
ConfidenceLevel = Literal["low", "medium", "high"]
TimeSource = Literal["explicit", "inferred", "default_now"]


class EstimatedMealItem(BaseModel):
    name: str
    calories_low: int = Field(ge=0)
    calories_mid: int = Field(ge=0)
    calories_high: int = Field(ge=0)
    protein_level: ProteinLevel
    confidence: ConfidenceLevel
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class MealEstimate(BaseModel):
    items: list[EstimatedMealItem]
    total_calories_low: int = Field(ge=0)
    total_calories_mid: int = Field(ge=0)
    total_calories_high: int = Field(ge=0)
    consumed_at: datetime
    time_source: TimeSource
    summary_notes: str = ""


class MealLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    raw_text: str
    items: list[EstimatedMealItem]
    total_calories_low: int = Field(ge=0)
    total_calories_mid: int = Field(ge=0)
    total_calories_high: int = Field(ge=0)
    user_override: int | None = Field(default=None, ge=0)
    notes: str = ""
    created_at: datetime


class DailyActivityLog(BaseModel):
    day: date
    active_calories: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class MeditationLog(BaseModel):
    day: date
    duration_minutes: int = Field(ge=0)
    source: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class SleepLog(BaseModel):
    day: date
    sleep_score: int = Field(ge=0, le=100)
    sleep_duration_hours: float = Field(ge=0)
    sleep_pills: str = "None"
    notes: str = ""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if "sleep_duration_hours" not in normalized and "sleep_duration_minutes" in normalized:
            normalized["sleep_duration_hours"] = float(normalized["sleep_duration_minutes"]) / 60.0
        normalized.setdefault("sleep_pills", "None")
        return normalized


class MoodEnergyLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    mood_score: int = Field(ge=0, le=10)
    energy_score: int = Field(ge=0, le=10)
    notes: str = ""
    created_at: datetime


class AlcoholLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    day: date
    timestamp: datetime
    standard_drinks: int = Field(ge=0)
    notes: str = ""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        timestamp_value = normalized.get("timestamp")
        if isinstance(timestamp_value, str):
            normalized["timestamp"] = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
            timestamp_value = normalized["timestamp"]

        if "day" not in normalized and isinstance(timestamp_value, datetime):
            normalized["day"] = timestamp_value.date()
        if "updated_at" not in normalized and "created_at" in normalized:
            normalized["updated_at"] = normalized["created_at"]
        return normalized


class WeightLog(BaseModel):
    day: date
    weight_kg: float = Field(gt=0)
    created_at: datetime
    updated_at: datetime
