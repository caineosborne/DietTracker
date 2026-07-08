from __future__ import annotations

import streamlit as st

from diettracker.app.dashboard_ui import render_day_view, render_history_view, render_week_view
from diettracker.app.meal_ui import render_edit_meal, render_meal_section
from diettracker.app.mood_ui import render_mood_form
from diettracker.app.wellness_ui import render_wellness_section
from diettracker.config import DEFAULT_MODEL
from diettracker.domain.metrics import get_now_local
from diettracker.stores.daily_store import ActivityStore, AlcoholStore, MeditationStore, SleepStore
from diettracker.stores.meal_store import MealStore
from diettracker.stores.mood_store import MoodStore


def render_app() -> None:
    st.set_page_config(page_title="Meal Tracker", page_icon="🍜", layout="wide")
    st.title("Meal Tracker")
    st.caption(
        f"Free-text first. Model default: `{DEFAULT_MODEL}`. "
        "Use the editor only when the parsed time or calories need correction."
    )

    meal_store = MealStore()
    activity_store = ActivityStore()
    alcohol_store = AlcoholStore()
    mood_store = MoodStore()
    meditation_store = MeditationStore()
    sleep_store = SleepStore()

    # Session defaults for the page state and edit/review flows.
    now_local = get_now_local()
    defaults = {
        "estimate": None,
        "editable_items": [],
        "last_raw_text": "",
        "timestamp_date": now_local.date(),
        "timestamp_time": now_local.time().replace(microsecond=0),
        "user_total_override": None,
        "user_notes": "",
        "selected_day": now_local.date(),
        "editing_meal_id": None,
        "existing_raw_text": "",
        "existing_items": [],
        "existing_timestamp_date": now_local.date(),
        "existing_timestamp_time": now_local.time().replace(microsecond=0),
        "existing_total_override": 0,
        "existing_notes": "",
        "wellness_entry_day": now_local.date(),
        "meal_direct_submit": True,
        "mood_review_index": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    render_meal_section(meal_store)

    with st.expander("Weekly Summary", expanded=False):
        render_week_view(meal_store, activity_store, mood_store, meditation_store, sleep_store, alcohol_store)

    with st.expander("Calorie History", expanded=False):
        render_history_view(meal_store, activity_store)

    with st.expander("Mood", expanded=False):
        st.caption("Telegram and Streamlit mood / energy check-in.")
        render_mood_form(mood_store)

    with st.expander("Wellness Logs", expanded=False):
        st.caption("Streamlit-only manual entry for meditation and sleep totals.")
        render_wellness_section(meditation_store, sleep_store)

    with st.expander("Daily Details", expanded=False):
        render_day_view(meal_store, activity_store, alcohol_store)
        render_edit_meal(meal_store)
