from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


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


class PendingMealLog(BaseModel):
    timestamp: datetime
    raw_text: str
    items: list[EstimatedMealItem]
    total_calories_low: int = Field(ge=0)
    total_calories_mid: int = Field(ge=0)
    total_calories_high: int = Field(ge=0)
    user_override: int | None = Field(default=None, ge=0)
    notes: str = ""

    def finalize(self, created_at: datetime) -> MealLog:
        return MealLog(
            timestamp=self.timestamp,
            raw_text=self.raw_text,
            items=self.items,
            total_calories_low=self.total_calories_low,
            total_calories_mid=self.total_calories_mid,
            total_calories_high=self.total_calories_high,
            user_override=self.user_override,
            notes=self.notes,
            created_at=created_at,
        )
