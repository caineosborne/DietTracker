from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from diettracker.app.formatters import format_minutes
from diettracker.config import DAILY_GOAL_CALORIES, WEIGHT_BASELINE_DAY, WEIGHT_BASELINE_KG
from diettracker.domain.metrics import (
    build_day_metrics,
    build_history_metrics,
    build_week_metrics,
    daily_status,
    get_now_local,
    summarize_history_metrics,
    start_of_day,
)
from diettracker.domain.models import AlcoholLog, DailyActivityLog, WeightLog
from diettracker.stores.daily_store import ActivityStore, AlcoholStore, MeditationStore, SleepStore, WeightStore
from diettracker.stores.meal_store import MealStore
from diettracker.stores.mood_store import MoodStore


BRISBANE_TZ = ZoneInfo("Australia/Brisbane")


def render_day_view(
    store: MealStore,
    activity_store: ActivityStore,
    alcohol_store: AlcoholStore,
    weight_store: WeightStore,
) -> None:
    now_local = get_now_local()
    tzinfo = now_local.tzinfo
    selected_day = st.session_state["selected_day"]
    meals = store.meals_for_day(start_of_day(selected_day, tzinfo))
    activity_log = activity_store.get_for_day(selected_day)
    history = build_history_metrics(
        meals=store.load_all(),
        activity_logs=activity_store.load_all(),
        weight_logs=weight_store.load_all(),
        today=max(get_now_local().date(), selected_day),
    )
    selected_history = next((entry for entry in history if entry.day == selected_day), None)
    actual_weight_log = weight_store.get_for_day(selected_day)
    day_metrics = build_day_metrics(
        meals,
        activity_log,
        actual_weight_log,
        selected_history.anchor_weight_kg if selected_history is not None else WEIGHT_BASELINE_KG,
        selected_history.anchor_day if selected_history is not None else WEIGHT_BASELINE_DAY,
        selected_history.expected_weight_kg if selected_history is not None else WEIGHT_BASELINE_KG,
    )

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
    weight_columns = st.columns(4)
    weight_columns[0].metric("Expected weight", f"{day_metrics.expected_weight_kg:.1f} kg")
    weight_columns[1].metric(
        "Actual weight",
        f"{day_metrics.actual_weight_kg:.1f} kg" if day_metrics.actual_weight_kg is not None else "Not logged",
    )
    weight_columns[2].metric(
        "Actual change",
        f"{day_metrics.actual_weight_delta_kg:.1f} kg" if day_metrics.actual_weight_delta_kg is not None else "Not logged",
    )
    weight_columns[3].metric(
        "Actual vs expected",
        f"{day_metrics.weight_difference_kg:+.1f} kg" if day_metrics.weight_difference_kg is not None else "Not logged",
        "positive means above expected",
        delta_color="inverse",
    )
    st.caption("Target bands: < 1,800 Low | 1,800-2,200 Good deficit | 2,200-2,600 Maintenance-ish | > 2,600 High day")
    st.caption("Weight guide uses `(2,100 resting + active calories - consumed calories) / 7,000`. A positive net means estimated loss.")
    st.caption(
        f"Current weight anchor is {day_metrics.anchor_weight_kg:.1f} kg on {day_metrics.anchor_day.strftime('%Y-%m-%d')}. "
        "On weigh-in days, expected weight uses the prior day's projection; the new weigh-in becomes the anchor for future days."
    )

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

    existing_weight = actual_weight_log
    st.subheader("Weight")
    if existing_weight is not None:
        st.caption(f"Saved for {selected_day.strftime('%Y-%m-%d')}: {existing_weight.weight_kg:.1f} kg.")
    else:
        st.caption("Add a weight only on days you weigh in.")

    with st.form(f"weight_daily_form_{selected_day.isoformat()}", enter_to_submit=True, border=False):
        weight_columns = st.columns([1, 2])
        weight_columns[0].number_input(
            "Weight (kg)",
            min_value=30.0,
            max_value=300.0,
            step=0.1,
            value=float(existing_weight.weight_kg) if existing_weight is not None else float(day_metrics.expected_weight_kg),
            key=f"weight_daily_kg_{selected_day.isoformat()}",
        )
        save_weight = weight_columns[1].form_submit_button("Save Weight", width="stretch")

    if save_weight:
        now_local = get_now_local()
        created_at = existing_weight.created_at if existing_weight is not None else now_local
        weight_store.upsert(
            WeightLog(
                day=selected_day,
                weight_kg=round(float(st.session_state[f"weight_daily_kg_{selected_day.isoformat()}"]), 1),
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
        f"Sleep days: **{week_metrics.sleep_days_count}** | Alcohol days: **{week_metrics.alcohol_days_count}**"
    )


def render_history_view(store: MealStore, activity_store: ActivityStore, weight_store: WeightStore) -> None:
    history = build_history_metrics(
        meals=store.load_all(),
        activity_logs=activity_store.load_all(),
        weight_logs=weight_store.load_all(),
        today=get_now_local().date(),
    )

    if not history:
        st.info("No meal or activity history yet.")
        return

    summaries = [
        summarize_history_metrics(label="Overall", history=history),
        summarize_history_metrics(label="Last 7 days", history=history, days=7),
        summarize_history_metrics(label="Last 30 days", history=history, days=30),
    ]

    summary_columns = st.columns(3)
    for column, summary in zip(summary_columns, summaries):
        with column:
            st.markdown(f"**{summary.label}**")
            st.caption(f"{summary.days_count} day(s)")
            st.metric("Total burn", f"{summary.total_burn:,} cal")
            st.metric("Total intake", f"{summary.total_intake:,} cal")
            st.metric("Net calorie difference", f"{summary.calorie_balance:+,} cal")
            st.metric("Expected weight change", f"{summary.expected_weight_delta_kg:.2f} kg", summary.weight_direction_label)
            st.metric("Current anchor", f"{summary.anchor_weight_kg:.1f} kg")
            st.metric("Expected weight", f"{summary.expected_weight_kg:.1f} kg")
            st.metric(
                "Latest actual weight",
                f"{summary.latest_actual_weight_kg:.1f} kg" if summary.latest_actual_weight_kg is not None else "Not logged",
            )
            st.metric(
                "Actual change",
                f"{summary.actual_weight_delta_kg:.1f} kg" if summary.actual_weight_delta_kg is not None else "Not logged",
            )
            st.metric(
                "Actual vs expected",
                f"{summary.weight_difference_kg:+.1f} kg" if summary.weight_difference_kg is not None else "Not logged",
            )

    table_rows = [
        {
            "Day": day.day.strftime("%Y-%m-%d"),
            "Total calorie burn": day.total_burn,
            "Total calorie intake": day.total_intake,
            "Net calorie difference": day.calorie_balance,
            "Expected weight change": f"{day.expected_weight_delta_kg:.2f} kg {day.weight_direction_label.lower().replace('est. ', '')}",
            "Anchor day": day.anchor_day.strftime("%Y-%m-%d"),
            "Anchor weight": f"{day.anchor_weight_kg:.1f} kg",
            "Expected weight": f"{day.expected_weight_kg:.1f} kg",
            "Actual weight": f"{day.actual_weight_kg:.1f} kg" if day.actual_weight_kg is not None else "",
            "Actual change": f"{day.actual_weight_delta_kg:.1f} kg" if day.actual_weight_delta_kg is not None else "",
            "Actual vs expected": f"{day.weight_difference_kg:+.1f} kg" if day.weight_difference_kg is not None else "",
        }
        for day in reversed(history)
    ]

    st.caption(
        f"Daily history runs from {history[0].day.strftime('%Y-%m-%d')} to {history[-1].day.strftime('%Y-%m-%d')}."
    )
    st.caption(
        "Net calorie difference uses `total burn - total intake`. Expected weight change uses `(net calories) / 7,000`, "
        "with positive net shown as estimated loss and negative net shown as estimated gain."
    )
    st.caption(
        "Expected weight on a weigh-in day is compared against the prior day's projection. After that, the new weigh-in becomes the anchor. If there is no earlier weigh-in, it falls back to 85.3 kg on 2026-06-28."
    )
    chart_data = pd.DataFrame(
        [
            {
                "Day": day.day,
                "Calories in": day.total_intake,
                "Calories out": day.total_burn,
                "Daily difference": day.calorie_balance,
                "Expected weight": day.expected_weight_kg,
                "Actual weight": day.actual_weight_kg,
            }
            for day in history
        ]
    )
    chart_series = chart_data.melt("Day", var_name="Series", value_name="Calories")
    series_scale = alt.Scale(
        domain=["Calories in", "Calories out", "Daily difference"],
        range=["#d97706", "#2563eb", "#059669"],
    )
    hover = alt.selection_point(fields=["Day"], nearest=True, on="pointerover", empty=False)

    line_chart = (
        alt.Chart(chart_series)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=alt.X("Day:T", title="Day", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-35)),
            y=alt.Y("Calories:Q", title="Calories"),
            color=alt.Color("Series:N", scale=series_scale, legend=alt.Legend(title=None)),
        )
    )
    hover_points = line_chart.mark_circle(size=70).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0))
    )
    hover_rule = (
        alt.Chart(chart_data)
        .mark_rule(color="#94a3b8", strokeDash=[2, 3])
        .encode(
            x=alt.X("Day:T", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-35)),
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("Day:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Calories in:Q", title="Calories in", format=",.0f"),
                alt.Tooltip("Calories out:Q", title="Calories out", format=",.0f"),
                alt.Tooltip("Daily difference:Q", title="Daily difference", format=",.0f"),
            ],
        )
        .add_params(hover)
    )

    reference_lines = pd.DataFrame(
        [
            {"label": "1,900 intake goal", "value": DAILY_GOAL_CALORIES, "color": "#b45309"},
            {"label": "0 net difference", "value": 0, "color": "#059669"},
        ]
    )
    reference_tooltips = [
        alt.Tooltip("label:N", title="Reference"),
        alt.Tooltip("value:Q", title="Calories", format=",.0f"),
    ]
    goal_rule = alt.Chart(reference_lines.iloc[[0]]).mark_rule(
        color="#b45309", strokeDash=[6, 4], strokeWidth=2
    ).encode(y="value:Q", tooltip=reference_tooltips)
    zero_rule = alt.Chart(reference_lines.iloc[[1]]).mark_rule(
        color="#059669", strokeDash=[6, 4], strokeWidth=2
    ).encode(y="value:Q", tooltip=reference_tooltips)
    goal_label = alt.Chart(reference_lines.iloc[[0]]).mark_text(
        align="left", dx=8, dy=-6, fontSize=12, fontWeight="bold", color="#b45309"
    ).encode(x=alt.value(8), y="value:Q", text="label:N")
    zero_label = alt.Chart(reference_lines.iloc[[1]]).mark_text(
        align="left", dx=8, dy=-6, fontSize=12, fontWeight="bold", color="#059669"
    ).encode(x=alt.value(8), y="value:Q", text="label:N")
    rules = goal_rule + zero_rule
    labels = goal_label + zero_label

    period_year = get_now_local().year
    period_lines = pd.DataFrame(
        [
            {
                "Day": datetime.combine(
                    datetime(period_year, 7, 13).date(), time.min, tzinfo=BRISBANE_TZ
                ),
                "Boundary": "Period start — 13 Jul",
            },
            {
                "Day": datetime.combine(
                    datetime(period_year, 7, 26).date(), time.min, tzinfo=BRISBANE_TZ
                ),
                "Boundary": "Period end — 26 Jul",
            },
        ]
    )
    period_rules = alt.Chart(period_lines).mark_rule(
        color="#7c3aed", strokeDash=[4, 3], strokeWidth=2
    ).encode(
        x=alt.X("Day:T", title="Day", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-35)),
        tooltip=[alt.Tooltip("Boundary:N", title="Brisbane time")],
    )

    st.altair_chart(
        (line_chart + hover_points + hover_rule + rules + labels + period_rules), width="stretch"
    )
    weight_chart_data = chart_data.melt(
        "Day",
        value_vars=["Expected weight", "Actual weight"],
        var_name="Series",
        value_name="Weight",
    )
    weight_chart = (
        alt.Chart(weight_chart_data.dropna())
        .mark_line(strokeWidth=2.5, point=True)
        .encode(
            x=alt.X("Day:T", title="Day", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-35)),
            y=alt.Y("Weight:Q", title="Weight (kg)", scale=alt.Scale(domain=[75, 90])),
            color=alt.Color(
                "Series:N",
                scale=alt.Scale(domain=["Expected weight", "Actual weight"], range=["#7c3aed", "#dc2626"]),
                legend=alt.Legend(title=None),
            ),
            tooltip=[
                alt.Tooltip("Day:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Series:N", title="Series"),
                alt.Tooltip("Weight:Q", title="Weight (kg)", format=".1f"),
            ],
        )
    )
    st.altair_chart(weight_chart, width="stretch")
    st.dataframe(table_rows, hide_index=True, width="stretch")
