from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from diettracker.app.formatters import format_hours, format_minutes
from diettracker.config import SLEEP_PILL_OPTIONS
from diettracker.domain.metrics import get_now_local
from diettracker.domain.models import MeditationLog, SleepLog
from diettracker.stores.daily_store import MeditationStore, SleepStore


def render_wellness_section(
    meditation_store: MeditationStore,
    sleep_store: SleepStore,
    *,
    show_meditation: bool = True,
) -> None:
    selected_day = st.session_state["wellness_entry_day"]

    with st.container(border=True):
        st.subheader("Wellness Logs")
        nav_columns = st.columns([1, 2, 1])
        if nav_columns[0].button("Previous Day", width="stretch", key="wellness_prev_day"):
            st.session_state["wellness_entry_day"] = selected_day - timedelta(days=1)
            st.rerun()
        nav_columns[1].markdown(
            f"<div style='text-align:center; padding-top:0.5rem; font-weight:600;'>{selected_day.strftime('%A, %d %b %Y')}</div>",
            unsafe_allow_html=True,
        )
        if nav_columns[2].button("Next Day", width="stretch", key="wellness_next_day"):
            st.session_state["wellness_entry_day"] = selected_day + timedelta(days=1)
            st.rerun()

        if show_meditation:
            # Section 1: meditation log for the selected day.
            meditation_log = meditation_store.get_for_day(selected_day)
            with st.container(border=True):
                st.subheader("Meditation")
                if meditation_log is not None:
                    st.caption(
                        f"Saved for {selected_day.strftime('%Y-%m-%d')}: "
                        f"{format_minutes(meditation_log.duration_minutes)} from {meditation_log.source or 'manual entry'}."
                    )
                else:
                    st.caption("Enter the total meditation time for this day.")

                with st.form(f"meditation_form_{selected_day.isoformat()}", enter_to_submit=True, border=False):
                    form_columns = st.columns([1, 1, 2])
                    duration_minutes = form_columns[0].number_input(
                        "Meditation minutes",
                        min_value=0,
                        step=5,
                        value=meditation_log.duration_minutes if meditation_log is not None else 0,
                        key=f"meditation_minutes_{selected_day.isoformat()}",
                    )
                    source = form_columns[1].text_input(
                        "Source",
                        value=meditation_log.source if meditation_log is not None else "",
                        key=f"meditation_source_{selected_day.isoformat()}",
                        placeholder="Headspace, Calm, breathwork, etc.",
                    )
                    notes = form_columns[2].text_input(
                        "Notes",
                        value=meditation_log.notes if meditation_log is not None else "",
                        key=f"meditation_notes_{selected_day.isoformat()}",
                        placeholder="optional note",
                    )
                    save_meditation = st.form_submit_button("Save Meditation", width="stretch")

                if save_meditation:
                    now_local = get_now_local()
                    created_at = meditation_log.created_at if meditation_log is not None else now_local
                    meditation_store.upsert(
                        MeditationLog(
                            day=selected_day,
                            duration_minutes=int(duration_minutes),
                            source=source.strip(),
                            notes=notes.strip(),
                            created_at=created_at,
                            updated_at=now_local,
                        )
                    )
                    st.rerun()

        # Section 2: sleep log for the selected day.
        sleep_log = sleep_store.get_for_day(selected_day)
        with st.container(border=True):
            st.subheader("Sleep")
            if sleep_log is not None:
                st.caption(
                    f"Saved for {selected_day.strftime('%Y-%m-%d')}: "
                    f"{format_hours(sleep_log.sleep_duration_hours)} with score {sleep_log.sleep_score}."
                )
            else:
                st.caption("Enter the total sleep time and score for this day.")

            with st.form(f"sleep_form_{selected_day.isoformat()}", enter_to_submit=True, border=False):
                form_columns = st.columns([1, 1, 1, 1])
                sleep_score = form_columns[0].number_input(
                    "Sleep score",
                    min_value=0,
                    max_value=100,
                    step=1,
                    value=sleep_log.sleep_score if sleep_log is not None else 0,
                    key=f"sleep_score_{selected_day.isoformat()}",
                )
                sleep_duration_hours = form_columns[1].number_input(
                    "Sleep duration (hours)",
                    min_value=0.0,
                    step=0.25,
                    format="%.2f",
                    value=sleep_log.sleep_duration_hours if sleep_log is not None else 0.0,
                    key=f"sleep_duration_{selected_day.isoformat()}",
                )
                sleep_pills = form_columns[2].selectbox(
                    "Pills",
                    options=SLEEP_PILL_OPTIONS,
                    index=SLEEP_PILL_OPTIONS.index(sleep_log.sleep_pills)
                    if sleep_log is not None and sleep_log.sleep_pills in SLEEP_PILL_OPTIONS
                    else SLEEP_PILL_OPTIONS.index("None"),
                    key=f"sleep_pills_{selected_day.isoformat()}",
                )
                notes = form_columns[3].text_input(
                    "Notes",
                    value=sleep_log.notes if sleep_log is not None else "",
                    key=f"sleep_notes_{selected_day.isoformat()}",
                    placeholder="optional note",
                )
                save_sleep = st.form_submit_button("Save Sleep", width="stretch")

            if save_sleep:
                now_local = get_now_local()
                created_at = sleep_log.created_at if sleep_log is not None else now_local
                sleep_store.upsert(
                    SleepLog(
                        day=selected_day,
                        sleep_score=int(sleep_score),
                        sleep_duration_hours=float(sleep_duration_hours),
                        sleep_pills=sleep_pills,
                        notes=notes.strip(),
                        created_at=created_at,
                        updated_at=now_local,
                    )
                )
                st.rerun()
