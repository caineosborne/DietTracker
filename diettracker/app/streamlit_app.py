from __future__ import annotations

import streamlit as st

from diettracker.auth import require_login
from diettracker.app.dashboard_ui import render_day_view, render_history_view, render_week_view
from diettracker.app.meal_ui import render_edit_meal, render_meal_section
from diettracker.config import DEFAULT_MODEL, SMALL_SNACK_ALLOWANCE_START_DAY
from diettracker.domain.metrics import get_now_local
from diettracker.stores.daily_store import ActivityStore, WeightStore
from diettracker.stores.meal_store import MealStore


def render_app() -> None:
    st.set_page_config(page_title="Meal Tracker", page_icon="🍜", layout="wide")
    require_login()
    st.title("Meal Tracker")
    st.caption(
        f"Free-text first. Model default: `{DEFAULT_MODEL}`. "
        "Use the editor only when the parsed time or calories need correction."
    )

    meal_store = MealStore()
    activity_store = ActivityStore()
    weight_store = WeightStore()

    # Session defaults for the page state and edit/review flows.
    now_local = get_now_local()
    meal_store.ensure_small_snack_allowances(
        start_day=SMALL_SNACK_ALLOWANCE_START_DAY,
        through_day=now_local.date(),
        tzinfo=now_local.tzinfo,
    )
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
        "meal_direct_submit": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    render_meal_section(meal_store)

    with st.expander("Daily Details", expanded=False):
        render_day_view(meal_store, activity_store, weight_store)
        render_edit_meal(meal_store)

    with st.expander("Calorie History", expanded=False):
        render_history_view(meal_store, activity_store, weight_store)

    with st.expander("Weekly Summary", expanded=False):
        render_week_view(meal_store, activity_store)
