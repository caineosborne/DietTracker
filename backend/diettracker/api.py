from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from diettracker.auth import SESSION_LENGTH, create_session_token, verify_password, verify_session_token
from diettracker.config import (
    DAILY_GOAL_CALORIES,
    DEFAULT_MODEL,
    SMALL_SNACK_ALLOWANCE_START_DAY,
    SUPPORTED_TIMEZONES,
    WEIGHT_BASELINE_DAY,
    WEIGHT_BASELINE_KG,
    app_timezone,
    configure_timezone,
)
from diettracker.domain.meal_builder import build_meal_log
from diettracker.domain.metrics import (
    build_day_metrics,
    build_history_metrics,
    build_week_metrics,
    daily_status,
    get_now_local,
    summarize_history_metrics,
)
from diettracker.domain.models import DailyActivityLog, EstimatedMealItem, MealLog, WeightLog
from diettracker.services.meal_estimator import MealEstimator
from diettracker.stores.daily_store import ActivityStore, WeightStore
from diettracker.stores.meal_store import MealStore
from diettracker.stores.settings_store import SettingsStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_COOKIE = "diettracker_session"
load_dotenv(PROJECT_ROOT / ".env")
# Keeps existing local checkouts working after the frontend/backend split.
load_dotenv(PROJECT_ROOT.parent / ".env")


def _frontend_origins() -> list[str]:
    default_origins = {
        "http://localhost:5173",
        "https://diettrackerreact.vercel.app",
        "https://diettrackerreact-fath3m2n4-caineosbornes-projects.vercel.app",
    }
    configured = os.getenv("FRONTEND_URLS") or os.getenv("FRONTEND_URL") or ""
    configured_origins = {
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    }
    return sorted(default_origins | configured_origins)


app = FastAPI(
    title="DietTracker API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class EstimateRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=2000)


class MealWriteRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    raw_text: str = Field(min_length=1, max_length=2000)
    items: list[EstimatedMealItem]
    consumed_at: datetime
    summary_notes: str = ""
    user_total_override: int | None = Field(default=None, ge=0)
    user_notes: str = Field(default="", max_length=2000)


class ActivityRequest(BaseModel):
    active_calories: int = Field(ge=0, le=10000)


class WeightRequest(BaseModel):
    weight_kg: float = Field(gt=30, le=300)


class TimezoneRequest(BaseModel):
    timezone: str


def _auth_settings() -> tuple[str, str, str]:
    values = (os.getenv("APP_USERNAME"), os.getenv("APP_PASSWORD_HASH"), os.getenv("APP_SESSION_SECRET"))
    if not all(values):
        raise HTTPException(status_code=503, detail="Password sign-in is not configured on the API.")
    return values  # type: ignore[return-value]


def require_user(
    diettracker_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    username, _, secret = _auth_settings()
    bearer_token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else None
    token = bearer_token or diettracker_session
    if not token or not verify_session_token(token, username, secret):
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return username


def _load_timezone() -> str:
    timezone_name = SettingsStore().get_timezone()
    configure_timezone(timezone_name)
    return timezone_name


def _cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}


@app.get("/health")
def health() -> dict[str, str]:
    """Cold-start probe: intentionally avoids database and OpenAI connections."""
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    username, password_hash, secret = _auth_settings()
    if not hmac.compare_digest(payload.username, username) or not verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = create_session_token(username, secret)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LENGTH.total_seconds()),
        httponly=True,
        secure=_cookie_secure(),
        samesite="none" if _cookie_secure() else "lax",
        path="/",
    )
    return {"username": username, "token": token}


@app.get("/api/auth/session")
def session(username: Annotated[str, Depends(require_user)]) -> dict[str, str]:
    return {"username": username}


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="none" if _cookie_secure() else "lax",
        path="/",
    )


@app.get("/api/dashboard")
def dashboard(
    _: Annotated[str, Depends(require_user)],
    day: date | None = None,
) -> dict[str, object]:
    timezone_name = _load_timezone()
    now = get_now_local()
    selected_day = day or now.date()
    meal_store = MealStore()
    activity_store = ActivityStore()
    weight_store = WeightStore()
    meal_store.ensure_small_snack_allowances(SMALL_SNACK_ALLOWANCE_START_DAY, now.date(), now.tzinfo)

    meals = meal_store.load_all()
    activities = activity_store.load_all()
    weights = weight_store.load_all()
    history = build_history_metrics(
        meals=meals,
        activity_logs=activities,
        weight_logs=weights,
        today=max(now.date(), selected_day),
    )
    selected_history = next((entry for entry in history if entry.day == selected_day), None)
    day_meals = [meal for meal in meals if meal.timestamp.astimezone(app_timezone()).date() == selected_day]
    activity = next((entry for entry in activities if entry.day == selected_day), None)
    actual_weight = next((entry for entry in weights if entry.day == selected_day), None)
    day_metrics = build_day_metrics(
        day_meals,
        activity,
        actual_weight,
        selected_history.anchor_weight_kg if selected_history else WEIGHT_BASELINE_KG,
        selected_history.anchor_day if selected_history else WEIGHT_BASELINE_DAY,
        selected_history.expected_weight_kg if selected_history else WEIGHT_BASELINE_KG,
    )
    week = build_week_metrics(meals=meals, activity_logs=activities, today=now.date())
    summaries = [
        summarize_history_metrics(label="Overall", history=history),
        summarize_history_metrics(label="Last 7 days", history=history, days=7),
        summarize_history_metrics(label="Last 30 days", history=history, days=30),
    ]
    return jsonable_encoder(
        {
            "today": now.date(),
            "selected_day": selected_day,
            "timezone": timezone_name,
            "supported_timezones": SUPPORTED_TIMEZONES,
            "daily_goal": DAILY_GOAL_CALORIES,
            "model": DEFAULT_MODEL,
            "meals": day_meals,
            "activity": activity,
            "weight": actual_weight,
            "day_metrics": {**asdict(day_metrics), "status": daily_status(day_metrics.total_calories)},
            "week_metrics": asdict(week),
            "history": [asdict(entry) for entry in history],
            "history_summaries": [asdict(summary) for summary in summaries],
        }
    )


@app.post("/api/meals/estimate")
def estimate_meal(payload: EstimateRequest, _: Annotated[str, Depends(require_user)]) -> object:
    _load_timezone()
    return MealEstimator().estimate(payload.raw_text, get_now_local())


@app.post("/api/meals", status_code=status.HTTP_201_CREATED)
def create_meal(payload: MealWriteRequest, _: Annotated[str, Depends(require_user)]) -> MealLog:
    _load_timezone()
    store = MealStore()
    meal = build_meal_log(
        raw_text=payload.raw_text,
        items=payload.items,
        timestamp=payload.consumed_at,
        created_at=get_now_local(),
        summary_notes=payload.summary_notes,
        user_total_override=payload.user_total_override,
        user_notes=payload.user_notes,
        meal_id=payload.request_id,
    )
    store.append(meal)
    existing = store.get(payload.request_id)
    if existing is None:
        raise HTTPException(status_code=500, detail="The meal could not be saved.")
    return existing


@app.put("/api/meals/{meal_id}")
def update_meal(meal_id: str, payload: MealWriteRequest, _: Annotated[str, Depends(require_user)]) -> MealLog:
    _load_timezone()
    store = MealStore()
    existing = store.get(meal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Meal not found.")
    updated = build_meal_log(
        raw_text=payload.raw_text,
        items=payload.items,
        timestamp=payload.consumed_at,
        created_at=existing.created_at,
        summary_notes=payload.summary_notes,
        user_total_override=payload.user_total_override,
        user_notes=payload.user_notes,
        meal_id=meal_id,
    )
    store.update(updated)
    return updated


@app.delete("/api/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(meal_id: str, _: Annotated[str, Depends(require_user)]) -> None:
    _load_timezone()
    store = MealStore()
    if store.get(meal_id) is not None:
        store.delete(meal_id)


@app.put("/api/activity/{day}")
def save_activity(day: date, payload: ActivityRequest, _: Annotated[str, Depends(require_user)]) -> DailyActivityLog:
    _load_timezone()
    store = ActivityStore()
    existing = store.get_for_day(day)
    now = get_now_local()
    record = DailyActivityLog(
        day=day,
        active_calories=payload.active_calories,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    store.upsert(record)
    return record


@app.put("/api/weight/{day}")
def save_weight(day: date, payload: WeightRequest, _: Annotated[str, Depends(require_user)]) -> WeightLog:
    _load_timezone()
    store = WeightStore()
    existing = store.get_for_day(day)
    now = get_now_local()
    record = WeightLog(
        day=day,
        weight_kg=round(payload.weight_kg, 1),
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    store.upsert(record)
    return record


@app.put("/api/settings/timezone")
def save_timezone(payload: TimezoneRequest, _: Annotated[str, Depends(require_user)]) -> dict[str, str]:
    if payload.timezone not in SUPPORTED_TIMEZONES:
        raise HTTPException(status_code=422, detail="Unsupported timezone.")
    SettingsStore().set_timezone(payload.timezone)
    configure_timezone(payload.timezone)
    return {"timezone": payload.timezone}
