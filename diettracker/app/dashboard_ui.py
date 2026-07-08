from __future__ import annotations

from datetime import timedelta

import streamlit as st

from diettracker.app.formatters import format_minutes
from diettracker.domain.metrics import (
    build_day_metrics,
    build_week_metrics,
    daily_status,
    get_now_local,
    start_of_day,
)
from diettracker.domain.models import AlcoholLog, DailyActivityLog
from diettracker.stores.daily_store import ActivityStore, AlcoholStore, MeditationStore, SleepStore
from diettracker.stores.meal_store import MealStore
from diettracker.stores.mood_store import MoodStore


def render_day_view(store: MealStore, activity_store: ActivityStore, alcohol_store: AlcoholStore) -> None:
    now_local = get_now_local()
    tzinfo = now_local.tzinfo
    selected_day = st.session_state["selected_day"]
    meals = store.meals_for_day(start_of_day(selected_day, tzinfo))
    activity_log = activity_store.get_for_day(selected_day)
    day_metrics = build_day_metrics(meals, activity_log)

    st.subheader("Day View")
    nav_columns = st.columns([1, 2, 1])
    if nav_columns[0].button("Previous Day", width="stretch", key=f"day_prev_{selected_day.isoformat()}"):
        st.session_state["selected_day"] = selected_day - timedelta(days=1)
        st.session_state["editing_meal_id"] = None
        st.rerun()
    nav_columns[1].markdown(
        f"<div style='text-align:center; padding-top:0.5rem; font-weight:600;'>{selected_day.strftime('%A, %d %b %Y')}</div>",
        unsafe_allow_html=True,
    )
    if nav_columns[2].button("Next Day", width="stretch", key=f"day_next_{selected_day.isoformat()}"):
        st.session_state["selected_day"] = selected_day + timedelta(days=1)
        st.session_state["editing_meal_id"] = None
        st.rerun()

    metric_columns = st.columns(4)
    metric_columns[0].metric("Meals logged", len(meals))
    metric_columns[1].metric("Daily total", f"{day_metrics.total_calories:,} cal")
    metric_columns[2].metric(
        "Vs 1,900 goal",
        f"{day_metrics.remaining_calories:+,} cal",
        "remaining" if day_metrics.remaining_calories >= 0 else "over",
        delta_color="inverse",
    )
    metric_columns[3].metric("Status", daily_status(day_metrics.total_calories))
    guidance_columns = st.columns(3)
    guidance_columns[0].metric("Active calories", f"{day_metrics.active_calories:,} cal")
    guidance_columns[1].metric("Total burn", f"{day_metrics.total_burn:,} cal")
    guidance_columns[2].metric(
        day_metrics.weight_direction_label,
        f"{day_metrics.expected_weight_delta_kg:.2f} kg",
        f"{day_metrics.calorie_balance:+,} cal net",
        delta_color="normal",
    )
    st.caption("Target bands: < 1,800 Low | 1,800-2,200 Good deficit | 2,200-2,600 Maintenance-ish | > 2,600 High day")
    st.caption("Weight guide uses `(2,100 resting + active calories - consumed calories) / 7,000`. A positive net means estimated loss.")

    with st.form(f"active_calories_form_{selected_day.isoformat()}", enter_to_submit=True, border=False):
        activity_columns = st.columns([2, 1])
        activity_columns[0].number_input(
            "Active calories for this day",
            min_value=0,
            step=50,
            value=day_metrics.active_calories,
            key=f"active_calories_input_{selected_day.isoformat()}",
            help="Enter calories burned above the 2,100 resting baseline.",
        )
        save_activity = activity_columns[1].form_submit_button("Save Active Calories", width="stretch")

    if save_activity:
        now_local = get_now_local()
        created_at = activity_log.created_at if activity_log is not None else now_local
        activity_store.upsert(
            DailyActivityLog(
                day=selected_day,
                active_calories=int(st.session_state[f"active_calories_input_{selected_day.isoformat()}"]),
                created_at=created_at,
                updated_at=now_local,
            )
        )
        st.rerun()

    existing_alcohol = alcohol_store.get_for_day(selected_day)
    st.subheader("Alcohol")
    if existing_alcohol is not None:
        st.caption(
            f"Saved for {selected_day.strftime('%Y-%m-%d')}: {existing_alcohol.standard_drinks} standard drink(s)."
        )
    else:
        st.caption("Enter standard drinks for this day.")

    with st.form(f"alcohol_daily_form_{selected_day.isoformat()}", enter_to_submit=True, border=False):
        alcohol_columns = st.columns([1, 2])
        alcohol_columns[0].number_input(
            "Standard drinks",
            min_value=0,
            step=1,
            value=existing_alcohol.standard_drinks if existing_alcohol is not None else 0,
            key=f"alcohol_daily_drinks_{selected_day.isoformat()}",
        )
        alcohol_columns[1].text_input(
            "Notes",
            value=existing_alcohol.notes if existing_alcohol is not None else "",
            key=f"alcohol_daily_notes_{selected_day.isoformat()}",
            placeholder="beer, wine, cocktails, etc.",
        )
        save_alcohol = st.form_submit_button("Save Alcohol", width="stretch")

    if save_alcohol:
        now_local = get_now_local()
        created_at = existing_alcohol.created_at if existing_alcohol is not None else now_local
        alcohol_store.upsert(
            AlcoholLog(
                day=selected_day,
                timestamp=now_local,
                standard_drinks=int(st.session_state[f"alcohol_daily_drinks_{selected_day.isoformat()}"]),
                notes=st.session_state[f"alcohol_daily_notes_{selected_day.isoformat()}"].strip(),
                created_at=created_at,
                updated_at=now_local,
            )
        )
        st.rerun()

    if not meals:
        st.info("No meals logged for this day yet.")

    for meal in meals:
        timestamp_label = meal.timestamp.astimezone().strftime("%a %d %b %H:%M")
        with st.container(border=True):
            header_columns = st.columns([3, 1, 1])
            header_columns[0].write(f"**{timestamp_label}**")
            if header_columns[1].button("Edit", key=f"edit_{meal.id}", width="stretch"):
                st.session_state["editing_meal_id"] = meal.id
                st.session_state["existing_raw_text"] = meal.raw_text
                st.session_state["existing_items"] = [
                    {
                        "name": item.name,
                        "calories_low": item.calories_low,
                        "calories_mid": item.calories_mid,
                        "calories_high": item.calories_high,
                        "protein_level": item.protein_level,
                        "confidence": item.confidence,
                        "notes": item.notes,
                        "tags_text": ", ".join(item.tags),
                    }
                    for item in meal.items
                ]
                st.session_state["existing_timestamp_date"] = meal.timestamp.date()
                st.session_state["existing_timestamp_time"] = meal.timestamp.timetz().replace(tzinfo=None)
                st.session_state["existing_total_override"] = (
                    meal.user_override if meal.user_override is not None else meal.total_calories_mid
                )
                st.session_state["existing_notes"] = meal.notes
                st.rerun()
            if header_columns[2].button("Delete", key=f"delete_{meal.id}", width="stretch"):
                store.delete(meal.id)
                if st.session_state.get("editing_meal_id") == meal.id:
                    st.session_state["editing_meal_id"] = None
                st.rerun()

            st.write(meal.raw_text)
            st.write(f"Total: {meal.total_calories_mid:,} cal")
            if meal.notes:
                st.caption(meal.notes)


def render_week_view(
    store: MealStore,
    activity_store: ActivityStore,
    mood_store: MoodStore,
    meditation_store: MeditationStore,
    sleep_store: SleepStore,
    alcohol_store: AlcoholStore,
) -> None:
    week_metrics = build_week_metrics(
        meals=store.load_all(),
        activity_logs=activity_store.load_all(),
        mood_logs=mood_store.load_all(),
        meditation_logs=meditation_store.load_all(),
        sleep_logs=sleep_store.load_all(),
        alcohol_logs=alcohol_store.load_all(),
        today=get_now_local().date(),
    )

    metric_columns = st.columns(2)
    with metric_columns[0]:
        st.metric("Average calories", f"{week_metrics.average_calories:,} cal")
        st.metric("Average active calories", f"{week_metrics.average_active_calories:,} cal")
        st.metric("Average sleep score", f"{week_metrics.average_sleep_score:.0f}")
        st.metric("Total meditation", format_minutes(week_metrics.total_meditation))
        st.metric("Average mood", f"{week_metrics.average_mood:.1f}")
        st.metric("Average energy", f"{week_metrics.average_energy:.1f}")
        st.metric("Total drinks", f"{week_metrics.total_drinks}")
    with metric_columns[1]:
        st.metric("Tracked intake", f"{week_metrics.tracked_consumed_total:,} cal")
        st.metric("Total burn", f"{week_metrics.total_burn:,} cal")
        st.metric("Net", f"{week_metrics.calorie_balance:+,} cal")
        st.metric("Est. weight change", f"{week_metrics.expected_weight_delta_kg:.2f} kg", week_metrics.weight_direction_label)
        st.caption(f"Tracked days: **{week_metrics.tracked_days_count}**")
    st.caption(
        f"Window: {week_metrics.window_start.strftime('%d %b')} to {(week_metrics.window_end - timedelta(days=1)).strftime('%d %b')} "
        f"(last 7 completed days, excluding today {week_metrics.today.strftime('%d %b')})."
    )
    st.caption(
        f"Meals logged: **{week_metrics.meals_count}** | Activity days: **{week_metrics.activity_days_count}** | "
        f"Sleep days: **{week_metrics.sleep_days_count}** | Meditation days: **{week_metrics.meditation_days_count}** | "
        f"Mood entries: **{week_metrics.mood_entries_count}** | Alcohol days: **{week_metrics.alcohol_days_count}**"
    )
