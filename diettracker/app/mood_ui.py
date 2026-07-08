from __future__ import annotations

import streamlit as st

from diettracker.domain.metrics import get_now_local
from diettracker.domain.models import MoodEnergyLog
from diettracker.stores.mood_store import MoodStore


def render_mood_form(mood_store: MoodStore) -> None:
    with st.container(border=True):
        st.subheader("Add Mood")
        st.caption("Log a new mood/energy check-in.")

        with st.form("mood_form", enter_to_submit=True, border=False):
            form_columns = st.columns([1, 1, 2])
            mood_score = form_columns[0].number_input(
                "Mood",
                min_value=0,
                max_value=10,
                step=1,
                value=6,
                key="mood_score_input",
            )
            energy_score = form_columns[1].number_input(
                "Energy",
                min_value=0,
                max_value=10,
                step=1,
                value=6,
                key="mood_energy_input",
            )
            notes = form_columns[2].text_input(
                "Notes",
                value="",
                key="mood_notes_input",
                placeholder="tired but mentally okay",
            )
            save_submitted = st.form_submit_button("Save Mood", width="stretch")

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
            for key in ("mood_score_input", "mood_energy_input", "mood_notes_input"):
                st.session_state.pop(key, None)
            st.rerun()

    with st.expander("Review Mood", expanded=False):
        mood_logs = mood_store.load_all()
        current_index = st.session_state.get(
            "mood_review_index",
            st.session_state.get("mood_history_index", len(mood_logs) - 1 if mood_logs else 0),
        )

        if not mood_logs:
            st.caption("No mood entries yet.")
            return

        current_index = max(0, min(current_index, len(mood_logs) - 1))
        st.session_state["mood_review_index"] = current_index
        current_log = mood_logs[current_index]

        nav_columns = st.columns([1, 2, 1])
        if nav_columns[0].button(
            "Previous Mood",
            width="stretch",
            key="mood_review_prev",
            disabled=current_index <= 0,
        ):
            st.session_state["mood_review_index"] = current_index - 1
            st.rerun()
        if nav_columns[2].button(
            "Next Mood",
            width="stretch",
            key="mood_review_next",
            disabled=current_index >= len(mood_logs) - 1,
        ):
            st.session_state["mood_review_index"] = current_index + 1
            st.rerun()
        nav_columns[1].markdown(
            f"<div style='text-align:center; padding-top:0.5rem; font-weight:600;'>"
            f"{current_log.timestamp.astimezone().strftime('%a %d %b %H:%M')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.caption(f"Entry {current_index + 1} of {len(mood_logs)}")
        st.caption(f"Mood {current_log.mood_score}/10, energy {current_log.energy_score}/10.")
        if current_log.notes:
            st.caption(f"Notes: {current_log.notes}")

        if st.button(
            "Delete This Entry",
            width="stretch",
            key=f"mood_delete_{current_log.id}",
            help="Deletes the currently selected mood entry.",
        ):
            mood_store.delete(current_log.id)
            st.session_state["mood_review_index"] = max(0, current_index - 1)
            st.rerun()
