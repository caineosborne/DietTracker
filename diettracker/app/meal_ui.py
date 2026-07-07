from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import streamlit as st

from diettracker.domain.meal_builder import build_meal_log
from diettracker.domain.metrics import get_now_local
from diettracker.domain.models import EstimatedMealItem
from diettracker.services.meal_estimator import MealEstimator
from diettracker.stores.meal_store import MealStore


def render_meal_section(store: MealStore) -> None:
    def item_to_editor_row(item: EstimatedMealItem) -> dict[str, str | int]:
        return {
            "name": item.name,
            "calories_low": item.calories_low,
            "calories_mid": item.calories_mid,
            "calories_high": item.calories_high,
            "protein_level": item.protein_level,
            "confidence": item.confidence,
            "notes": item.notes,
            "tags_text": ", ".join(item.tags),
        }

    def editor_row_to_item(row: dict[str, object]) -> EstimatedMealItem:
        tags_text = str(row.get("tags_text", "") or "")
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        return EstimatedMealItem.model_validate(
            {
                "name": row.get("name", ""),
                "calories_low": row.get("calories_low", 0),
                "calories_mid": row.get("calories_mid", 0),
                "calories_high": row.get("calories_high", 0),
                "protein_level": row.get("protein_level", "low"),
                "confidence": row.get("confidence", "medium"),
                "notes": row.get("notes", ""),
                "tags": tags,
            }
        )

    def clear_review_state() -> None:
        st.session_state["estimate"] = None
        st.session_state["editable_items"] = []
        st.session_state["last_raw_text"] = ""
        for key in ("timestamp_date", "timestamp_time", "user_total_override", "user_notes", "item_editor"):
            st.session_state.pop(key, None)

    def build_meal(raw_text: str, edited_timestamp: datetime, created_at: datetime, meal_id: str | None = None):
        estimate = st.session_state["estimate"]
        items = [editor_row_to_item(item) for item in st.session_state["editable_items"]]
        user_total_override = st.session_state.get("user_total_override")
        override_value = int(user_total_override) if user_total_override not in (None, "") else None
        return build_meal_log(
            raw_text=raw_text,
            items=items,
            timestamp=edited_timestamp,
            created_at=created_at,
            summary_notes=estimate.summary_notes,
            user_total_override=override_value,
            user_notes=st.session_state.get("user_notes", ""),
            meal_id=meal_id,
        )

    # Section 1: quick meal entry and model estimate.
    with st.container(border=True):
        st.subheader("Add Meal Log")
        st.checkbox("Save directly without review", key="meal_direct_submit")
        with st.form("estimate_meal_form", enter_to_submit=True, border=False):
            raw_text = st.text_input(
                "What did you eat?",
                value=st.session_state["last_raw_text"],
                placeholder="Example: Small pho bo tai, 300 calories",
            )
            st.caption("Press Enter to submit.")
            submit_label = "Add Meal" if st.session_state["meal_direct_submit"] else "Estimate"
            estimate_submitted = st.form_submit_button(submit_label, type="primary", width="stretch")

        if estimate_submitted:
            try:
                estimate = MealEstimator().estimate(raw_text, get_now_local())
            except Exception as exc:  # noqa: BLE001
                st.error(f"Estimate failed: {exc}")
            else:
                st.session_state["estimate"] = estimate
                st.session_state["editable_items"] = [item_to_editor_row(item) for item in estimate.items]
                st.session_state["last_raw_text"] = raw_text.strip()
                st.session_state["timestamp_date"] = estimate.consumed_at.date()
                st.session_state["timestamp_time"] = estimate.consumed_at.timetz().replace(tzinfo=None)
                st.session_state["user_total_override"] = estimate.total_calories_mid
                st.session_state["user_notes"] = ""

                if st.session_state["meal_direct_submit"]:
                    try:
                        store.append(
                            build_meal(raw_text, estimate.consumed_at, created_at=get_now_local())
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Save failed: {exc}")
                    else:
                        st.success("Meal saved.")
                        clear_review_state()
                        st.rerun()
                else:
                    st.rerun()

    # Section 2: optional review flow after estimating.
    estimate = st.session_state["estimate"]
    if estimate is None:
        return

    with st.container(border=True):
        with st.form("save_meal_form", enter_to_submit=True, border=False):
            st.subheader("Review Before Save")
            info_columns = st.columns(4)
            info_columns[0].metric("Mid estimate", f"{estimate.total_calories_mid:,} cal")
            info_columns[1].metric("Range", f"{estimate.total_calories_low:,} - {estimate.total_calories_high:,}")
            info_columns[2].metric("Time source", estimate.time_source.replace("_", " "))
            info_columns[3].metric("Parsed timestamp", estimate.consumed_at.strftime("%Y-%m-%d %H:%M"))
            if estimate.summary_notes:
                st.caption(estimate.summary_notes)

            st.markdown("Manual adjustments are optional and mainly for fixing retrospective entries.")
            st.caption("Press Enter to save once you are done reviewing. In multiline fields, use Cmd+Enter or Ctrl+Enter.")
            edited_items = st.data_editor(
                pd.DataFrame(st.session_state["editable_items"]),
                num_rows="dynamic",
                width="stretch",
                key="item_editor",
                column_config={
                    "name": st.column_config.TextColumn("Meal"),
                    "calories_low": st.column_config.NumberColumn("Low", min_value=0, step=1),
                    "calories_mid": st.column_config.NumberColumn("Mid", min_value=0, step=1),
                    "calories_high": st.column_config.NumberColumn("High", min_value=0, step=1),
                    "protein_level": st.column_config.SelectboxColumn("Protein", options=["low", "medium", "good"]),
                    "confidence": st.column_config.SelectboxColumn("Confidence", options=["low", "medium", "high"]),
                    "notes": st.column_config.TextColumn("Notes"),
                    "tags_text": st.column_config.TextColumn("Tags"),
                },
            )
            st.session_state["editable_items"] = edited_items.to_dict("records")

            edit_columns = st.columns(3)
            edited_date = edit_columns[0].date_input("Consumed date", key="timestamp_date")
            edited_time = edit_columns[1].time_input("Consumed time", key="timestamp_time", step=900)
            edit_columns[2].number_input("Override total calories", min_value=0, step=10, key="user_total_override")

            st.text_area("Extra notes", key="user_notes", height=80, placeholder="Optional correction or context.")

            save_submitted = st.form_submit_button("Save Meal", width="stretch")

        edited_timestamp = datetime.combine(
            edited_date,
            edited_time if isinstance(edited_time, time) else edited_time.time(),
            tzinfo=get_now_local().tzinfo,
        )

        if save_submitted:
            try:
                store.append(
                    build_meal(
                        st.session_state["last_raw_text"],
                        edited_timestamp,
                        created_at=get_now_local(),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Save failed: {exc}")
            else:
                st.success("Meal saved.")
                clear_review_state()
                st.rerun()


def render_edit_meal(store: MealStore) -> None:
    def editor_row_to_item(row: dict[str, object]) -> EstimatedMealItem:
        tags_text = str(row.get("tags_text", "") or "")
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        return EstimatedMealItem.model_validate(
            {
                "name": row.get("name", ""),
                "calories_low": row.get("calories_low", 0),
                "calories_mid": row.get("calories_mid", 0),
                "calories_high": row.get("calories_high", 0),
                "protein_level": row.get("protein_level", "low"),
                "confidence": row.get("confidence", "medium"),
                "notes": row.get("notes", ""),
                "tags": tags,
            }
        )

    def clear_existing_editor_state() -> None:
        st.session_state["editing_meal_id"] = None

    editing_meal_id = st.session_state.get("editing_meal_id")
    if editing_meal_id is None:
        return

    meals_by_id = {meal.id: meal for meal in store.load_all()}
    editing_meal = meals_by_id.get(editing_meal_id)
    if editing_meal is None:
        clear_existing_editor_state()
        st.rerun()

    tzinfo = get_now_local().tzinfo
    with st.container(border=True):
        st.subheader("Edit Saved Meal")
        st.text_area("Original meal text", key="existing_raw_text", height=100)
        existing_items = st.data_editor(
            pd.DataFrame(st.session_state["existing_items"]),
            num_rows="dynamic",
            width="stretch",
            key="existing_item_editor",
            column_config={
                "name": st.column_config.TextColumn("Meal"),
                "calories_low": st.column_config.NumberColumn("Low", min_value=0, step=1),
                "calories_mid": st.column_config.NumberColumn("Mid", min_value=0, step=1),
                "calories_high": st.column_config.NumberColumn("High", min_value=0, step=1),
                "protein_level": st.column_config.SelectboxColumn("Protein", options=["low", "medium", "good"]),
                "confidence": st.column_config.SelectboxColumn("Confidence", options=["low", "medium", "high"]),
                "notes": st.column_config.TextColumn("Notes"),
                "tags_text": st.column_config.TextColumn("Tags"),
            },
        )
        st.session_state["existing_items"] = existing_items.to_dict("records")

        edit_columns = st.columns(3)
        edited_date = edit_columns[0].date_input("Consumed date", key="existing_timestamp_date")
        edited_time = edit_columns[1].time_input("Consumed time", key="existing_timestamp_time", step=900)
        edit_columns[2].number_input("Override total calories", min_value=0, step=10, key="existing_total_override")
        st.text_area("Notes", key="existing_notes", height=80)

        edited_timestamp = datetime.combine(
            edited_date,
            edited_time if isinstance(edited_time, time) else edited_time.time(),
            tzinfo=tzinfo,
        )

        action_columns = st.columns(2)
        if action_columns[0].button("Save Changes", width="stretch"):
            updated_meal = build_meal_log(
                raw_text=st.session_state.get("existing_raw_text", ""),
                items=[editor_row_to_item(item) for item in st.session_state["existing_items"]],
                timestamp=edited_timestamp,
                created_at=editing_meal.created_at,
                user_total_override=int(st.session_state["existing_total_override"])
                if st.session_state.get("existing_total_override") not in (None, "")
                else None,
                user_notes=st.session_state.get("existing_notes", ""),
                meal_id=editing_meal.id,
            )
            store.update(updated_meal)
            st.session_state["selected_day"] = updated_meal.timestamp.date()
            clear_existing_editor_state()
            st.rerun()
        if action_columns[1].button("Cancel Edit", width="stretch"):
            clear_existing_editor_state()
            st.rerun()
