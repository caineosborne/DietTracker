from __future__ import annotations

import streamlit as st

from diettracker.domain.metrics import get_now_local
from diettracker.domain.models import MoodEnergyLog
from diettracker.stores.mood_store import MoodStore


def render_mood_form(mood_store: MoodStore) -> None:
    mood_logs = mood_store.load_all()
    current_index = st.session_state.get("mood_history_index", len(mood_logs) - 1 if mood_logs else 0)
    if mood_logs:
        current_index = max(0, min(current_index, len(mood_logs) - 1))
        st.session_state["mood_history_index"] = current_index
        current_log = mood_logs[current_index]
    else:
        current_log = None

    with st.container(border=True):
        st.subheader("Mood")
        nav_columns = st.columns([1, 2, 1])
        if nav_columns[0].button(
            "Previous Mood",
            width="stretch",
            key="mood_prev",
            disabled=not mood_logs or current_index <= 0,
        ):
            st.session_state["mood_history_index"] = current_index - 1
            st.rerun()
        if nav_columns[2].button(
            "Next Mood",
            width="stretch",
            key="mood_next",
            disabled=not mood_logs or current_index >= len(mood_logs) - 1,
        ):
            st.session_state["mood_history_index"] = current_index + 1
            st.rerun()
        nav_columns[1].markdown(
            f"<div style='text-align:center; padding-top:0.5rem; font-weight:600;'>"
            f"{current_log.timestamp.astimezone().strftime('%a %d %b %H:%M') if current_log else 'No mood entries yet'}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if current_log is not None:
            st.caption(f"Mood {current_log.mood_score}/10, energy {current_log.energy_score}/10.")
        else:
            st.caption("Enter a quick mood/energy check-in.")

        with st.form("mood_form", enter_to_submit=True, border=False):
            form_columns = st.columns([1, 1, 2])
            mood_score = form_columns[0].number_input(
                "Mood",
                min_value=0,
                max_value=10,
                step=1,
                value=current_log.mood_score if current_log is not None else 6,
                key="mood_score_input",
            )
            energy_score = form_columns[1].number_input(
                "Energy",
                min_value=0,
                max_value=10,
                step=1,
                value=current_log.energy_score if current_log is not None else 6,
                key="mood_energy_input",
            )
            notes = form_columns[2].text_input(
                "Notes",
                value=current_log.notes if current_log is not None else "",
                key="mood_notes_input",
                placeholder="tired but mentally okay",
            )
            save_columns = st.columns([1, 1])
            save_submitted = save_columns[0].form_submit_button("Save Mood", width="stretch")
            delete_submitted = save_columns[1].form_submit_button(
                "Delete Mood",
                width="stretch",
                disabled=current_log is None,
            )

        if save_submitted:
            now_local = get_now_local()
            mood_store.append(
                MoodEnergyLog(
                    timestamp=now_local,
                    mood_score=int(mood_score),
                    energy_score=int(energy_score),
                    notes=notes.strip(),
                    created_at=now_local,
                )
            )
            st.session_state["mood_history_index"] = len(mood_logs)
            st.rerun()

        if delete_submitted and current_log is not None:
            mood_store.delete(current_log.id)
            st.session_state["mood_history_index"] = max(0, current_index - 1)
            st.rerun()

