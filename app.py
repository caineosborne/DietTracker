from __future__ import annotations

from datetime import date, datetime, time, timedelta
from statistics import mean

import pandas as pd
import streamlit as st

from meal_estimator import DEFAULT_MODEL, MealEstimator
from meal_store import MealStore
from schemas import EstimatedMealItem, MealLog, PendingMealLog

st.set_page_config(page_title="Meal Tracker", page_icon="🍜", layout="wide")


def get_now_local() -> datetime:
    return datetime.now().astimezone()


def daily_status(total_calories: int) -> str:
    if total_calories < 1800:
        return "Low"
    if total_calories <= 2200:
        return "Good deficit"
    if total_calories <= 2600:
        return "Maintenance-ish"
    return "High day"


def guess_protein_quality(items: list[EstimatedMealItem]) -> str:
    if not items:
        return "low"

    levels = [item.protein_level for item in items]
    good_count = sum(level == "good" for level in levels)
    medium_or_better = sum(level in {"medium", "good"} for level in levels)

    if good_count >= 1 and medium_or_better >= max(1, len(levels) // 2):
        return "good"
    if medium_or_better >= max(1, len(levels) // 2):
        return "medium"
    return "low"


def count_matching_items(items: list[EstimatedMealItem], keywords: set[str]) -> int:
    count = 0
    for item in items:
        haystack = " ".join([item.name, item.notes, " ".join(item.tags)]).lower()
        if any(keyword in haystack for keyword in keywords):
            count += 1
    return count


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


def build_pending_log(raw_text: str, edited_timestamp: datetime) -> PendingMealLog:
    estimate = st.session_state["estimate"]
    items_data = st.session_state["editable_items"]
    user_total_override = st.session_state.get("user_total_override")
    user_notes = st.session_state.get("user_notes", "").strip()

    # The editor stores rows in a UI-friendly shape; convert them back to the schema before save.
    items = [editor_row_to_item(item) for item in items_data]
    inferred_mid_total = sum(item.calories_mid for item in items)
    override_value = (
        int(user_total_override)
        if user_total_override not in (None, "")
        else inferred_mid_total
    )
    user_override = override_value if override_value != inferred_mid_total else None

    total_mid = override_value
    total_low = sum(item.calories_low for item in items)
    total_high = sum(item.calories_high for item in items)

    notes_parts = [estimate.summary_notes.strip(), user_notes]
    notes = " | ".join(part for part in notes_parts if part)

    return PendingMealLog(
        timestamp=edited_timestamp,
        raw_text=raw_text.strip(),
        items=items,
        total_calories_low=total_low,
        total_calories_mid=total_mid,
        total_calories_high=total_high,
        user_override=user_override,
        notes=notes,
    )


def clear_review_state() -> None:
    # Drop review widget state so Streamlit recreates those controls cleanly on the next run.
    st.session_state["estimate"] = None
    st.session_state["editable_items"] = []
    st.session_state["last_raw_text"] = ""

    for key in ("timestamp_date", "timestamp_time", "user_total_override", "user_notes", "item_editor"):
        st.session_state.pop(key, None)


def start_of_day(day_value: date, tzinfo: object) -> datetime:
    return datetime.combine(day_value, time.min, tzinfo=tzinfo)


def load_existing_meal_into_editor(meal: MealLog) -> None:
    # Copy a saved meal into a separate editor state so editing does not mutate the live list view.
    st.session_state["editing_meal_id"] = meal.id
    st.session_state["existing_raw_text"] = meal.raw_text
    st.session_state["existing_items"] = [item_to_editor_row(item) for item in meal.items]
    st.session_state["existing_timestamp_date"] = meal.timestamp.date()
    st.session_state["existing_timestamp_time"] = meal.timestamp.timetz().replace(tzinfo=None)
    st.session_state["existing_total_override"] = (
        meal.user_override if meal.user_override is not None else meal.total_calories_mid
    )
    st.session_state["existing_notes"] = meal.notes


def clear_existing_editor_state() -> None:
    st.session_state["editing_meal_id"] = None


def build_updated_meal(original_meal: MealLog, edited_timestamp: datetime) -> MealLog:
    # Preserve immutable fields like id and created_at while rebuilding the editable parts.
    items = [editor_row_to_item(item) for item in st.session_state["existing_items"]]
    total_low = sum(item.calories_low for item in items)
    total_high = sum(item.calories_high for item in items)
    inferred_mid_total = sum(item.calories_mid for item in items)
    override_value = st.session_state.get("existing_total_override")
    total_mid = int(override_value) if override_value not in (None, "") else inferred_mid_total
    user_override = total_mid if total_mid != inferred_mid_total else None

    return MealLog(
        id=original_meal.id,
        timestamp=edited_timestamp,
        raw_text=st.session_state.get("existing_raw_text", "").strip(),
        items=items,
        total_calories_low=total_low,
        total_calories_mid=total_mid,
        total_calories_high=total_high,
        user_override=user_override,
        notes=st.session_state.get("existing_notes", "").strip(),
        created_at=original_meal.created_at,
    )


def render_day_view(store: MealStore) -> None:
    now_local = get_now_local()
    tzinfo = now_local.tzinfo
    selected_day = st.session_state["selected_day"]
    # The day browser is independent of "today", so all daily queries anchor off the selected date.
    day_start = start_of_day(selected_day, tzinfo)
    meals = store.meals_for_day(day_start)
    total = sum(meal.total_calories_mid for meal in meals)

    st.subheader("Day View")
    nav_columns = st.columns([1, 2, 1])
    if nav_columns[0].button("Previous Day", width="stretch"):
        st.session_state["selected_day"] = selected_day - timedelta(days=1)
        clear_existing_editor_state()
        st.rerun()
    nav_columns[1].markdown(
        f"<div style='text-align:center; padding-top:0.5rem; font-weight:600;'>{selected_day.strftime('%A, %d %b %Y')}</div>",
        unsafe_allow_html=True,
    )
    if nav_columns[2].button("Next Day", width="stretch"):
        st.session_state["selected_day"] = selected_day + timedelta(days=1)
        clear_existing_editor_state()
        st.rerun()

    metric_columns = st.columns(3)
    metric_columns[0].metric("Meals logged", len(meals))
    metric_columns[1].metric("Daily total", f"{total:,} cal")
    metric_columns[2].metric("Status", daily_status(total))
    st.caption("Target bands: < 1,800 Low | 1,800-2,200 Good deficit | 2,200-2,600 Maintenance-ish | > 2,600 High day")

    if not meals:
        st.info("No meals logged for this day yet.")

    for meal in meals:
        timestamp_label = meal.timestamp.astimezone().strftime("%a %d %b %H:%M")
        with st.container(border=True):
            header_columns = st.columns([3, 1, 1])
            header_columns[0].write(f"**{timestamp_label}**")
            if header_columns[1].button("Edit", key=f"edit_{meal.id}", width="stretch"):
                load_existing_meal_into_editor(meal)
                st.rerun()
            if header_columns[2].button("Delete", key=f"delete_{meal.id}", width="stretch"):
                store.delete(meal.id)
                if st.session_state.get("editing_meal_id") == meal.id:
                    clear_existing_editor_state()
                st.rerun()

            st.write(meal.raw_text)
            st.write(f"Total: {meal.total_calories_mid:,} cal")
            if meal.notes:
                st.caption(meal.notes)

    editing_meal_id = st.session_state.get("editing_meal_id")
    if editing_meal_id is None:
        return

    # Resolve the editor target from storage again so edits always apply to the latest saved record.
    meals_by_id = {meal.id: meal for meal in store.load_all()}
    editing_meal = meals_by_id.get(editing_meal_id)
    if editing_meal is None:
        clear_existing_editor_state()
        st.rerun()

    with st.container(border=True):
        st.subheader("Edit Saved Meal")
        st.text_area(
            "Original meal text",
            key="existing_raw_text",
            height=100,
        )
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
                "protein_level": st.column_config.SelectboxColumn(
                    "Protein",
                    options=["low", "medium", "good"],
                ),
                "confidence": st.column_config.SelectboxColumn(
                    "Confidence",
                    options=["low", "medium", "high"],
                ),
                "notes": st.column_config.TextColumn("Notes"),
                "tags_text": st.column_config.TextColumn("Tags"),
            },
        )
        st.session_state["existing_items"] = existing_items.to_dict("records")

        edit_columns = st.columns(3)
        edited_date = edit_columns[0].date_input("Consumed date", key="existing_timestamp_date")
        edited_time = edit_columns[1].time_input(
            "Consumed time",
            key="existing_timestamp_time",
            step=900,
        )
        edit_columns[2].number_input(
            "Override total calories",
            min_value=0,
            step=10,
            key="existing_total_override",
        )
        st.text_area("Notes", key="existing_notes", height=80)

        edited_timestamp = datetime.combine(
            edited_date,
            edited_time if isinstance(edited_time, time) else edited_time.time(),
            tzinfo=tzinfo,
        )

        action_columns = st.columns(2)
        if action_columns[0].button("Save Changes", width="stretch"):
            updated_meal = build_updated_meal(editing_meal, edited_timestamp)
            store.update(updated_meal)
            st.session_state["selected_day"] = updated_meal.timestamp.date()
            clear_existing_editor_state()
            st.rerun()
        if action_columns[1].button("Cancel Edit", width="stretch"):
            clear_existing_editor_state()
            st.rerun()


def render_week_view(store: MealStore) -> None:
    now_local = get_now_local()
    meals = store.meals_for_week(now_local)
    total = sum(meal.total_calories_mid for meal in meals)

    st.subheader("This Week")
    if not meals:
        st.info("No meals logged this week yet.")
        return

    heavy_meals = sum(meal.total_calories_mid >= 800 for meal in meals)
    fried_extras = sum(
        count_matching_items(meal.items, {"spring roll", "spring rolls", "fried", "extra roll"})
        for meal in meals
    )
    sweets = sum(
        count_matching_items(meal.items, {"ice cream", "dessert", "sweet", "soda"})
        for meal in meals
    )
    protein_quality = guess_protein_quality(
        [item for meal in meals for item in meal.items]
    )

    daily_totals: dict[str, int] = {}
    for meal in meals:
        day_key = meal.timestamp.astimezone().date().isoformat()
        daily_totals.setdefault(day_key, 0)
        daily_totals[day_key] += meal.total_calories_mid

    metric_columns = st.columns(5)
    metric_columns[0].metric("Week total", f"{total:,} cal")
    metric_columns[1].metric("Avg per day", f"{int(mean(daily_totals.values())):,} cal")
    metric_columns[2].metric("Heavy meals", heavy_meals)
    metric_columns[3].metric("Fried extras", fried_extras)
    metric_columns[4].metric("Sweets / ice creams", sweets)
    st.caption(f"Protein quality: **{protein_quality}**")


def render_app() -> None:
    st.title("Meal Tracker")
    st.caption(
        f"Free-text first. Model default: `{DEFAULT_MODEL}`. "
        "Use the editor only when the parsed time or calories need correction."
    )

    store = MealStore()

    if "estimate" not in st.session_state:
        st.session_state["estimate"] = None
    if "editable_items" not in st.session_state:
        st.session_state["editable_items"] = []
    if "last_raw_text" not in st.session_state:
        st.session_state["last_raw_text"] = ""
    if "timestamp_date" not in st.session_state:
        now_local = get_now_local()
        st.session_state["timestamp_date"] = now_local.date()
        st.session_state["timestamp_time"] = now_local.time().replace(microsecond=0)
    if "user_total_override" not in st.session_state:
        st.session_state["user_total_override"] = None
    if "user_notes" not in st.session_state:
        st.session_state["user_notes"] = ""
    if "selected_day" not in st.session_state:
        st.session_state["selected_day"] = get_now_local().date()
    if "editing_meal_id" not in st.session_state:
        st.session_state["editing_meal_id"] = None
    if "existing_raw_text" not in st.session_state:
        st.session_state["existing_raw_text"] = ""
    if "existing_items" not in st.session_state:
        st.session_state["existing_items"] = []
    if "existing_timestamp_date" not in st.session_state:
        st.session_state["existing_timestamp_date"] = get_now_local().date()
    if "existing_timestamp_time" not in st.session_state:
        st.session_state["existing_timestamp_time"] = get_now_local().time().replace(microsecond=0)
    if "existing_total_override" not in st.session_state:
        st.session_state["existing_total_override"] = 0
    if "existing_notes" not in st.session_state:
        st.session_state["existing_notes"] = ""

    with st.container(border=True):
        st.subheader("Add Meal Log")
        with st.form("estimate_meal_form", enter_to_submit=True, border=False):
            raw_text = st.text_area(
                "What did you eat?",
                value=st.session_state["last_raw_text"],
                height=140,
                placeholder="Examples:\nSmall pho bo tai\nYesterday lunch I had bun thit nuong\nIce cream, 300 calories",
            )
            st.caption("Press Cmd+Enter on Mac or Ctrl+Enter on Windows/Linux to estimate from the text box.")
            estimate_submitted = st.form_submit_button("Estimate", type="primary", width="stretch")

        if estimate_submitted:
            try:
                estimator = MealEstimator()
                estimate = estimator.estimate(raw_text, get_now_local())
            except Exception as exc:  # noqa: BLE001
                st.error(f"Estimate failed: {exc}")
            else:
                st.session_state["estimate"] = estimate
                st.session_state["editable_items"] = [
                    item_to_editor_row(item) for item in estimate.items
                ]
                st.session_state["last_raw_text"] = raw_text.strip()
                st.session_state["timestamp_date"] = estimate.consumed_at.date()
                st.session_state["timestamp_time"] = estimate.consumed_at.timetz().replace(tzinfo=None)
                st.session_state["user_total_override"] = estimate.total_calories_mid
                st.session_state["user_notes"] = ""

    estimate = st.session_state["estimate"]
    if estimate is not None:
        with st.container(border=True):
            st.subheader("Review Before Save")
            info_columns = st.columns(4)
            info_columns[0].metric("Mid estimate", f"{estimate.total_calories_mid:,} cal")
            info_columns[1].metric("Range", f"{estimate.total_calories_low:,} - {estimate.total_calories_high:,}")
            info_columns[2].metric("Time source", estimate.time_source.replace("_", " "))
            info_columns[3].metric("Parsed timestamp", estimate.consumed_at.strftime("%Y-%m-%d %H:%M"))
            if estimate.summary_notes:
                st.caption(estimate.summary_notes)

            st.markdown("Manual adjustments are optional and mainly for fixing retrospective entries.")
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
                    "protein_level": st.column_config.SelectboxColumn(
                        "Protein",
                        options=["low", "medium", "good"],
                    ),
                    "confidence": st.column_config.SelectboxColumn(
                        "Confidence",
                        options=["low", "medium", "high"],
                    ),
                    "notes": st.column_config.TextColumn("Notes"),
                    "tags_text": st.column_config.TextColumn("Tags"),
                },
            )
            st.session_state["editable_items"] = edited_items.to_dict("records")

            edit_columns = st.columns(3)
            edited_date = edit_columns[0].date_input(
                "Consumed date",
                key="timestamp_date",
            )
            edited_time = edit_columns[1].time_input(
                "Consumed time",
                key="timestamp_time",
                step=900,
            )
            edit_columns[2].number_input(
                "Override total calories",
                min_value=0,
                step=10,
                key="user_total_override",
            )

            st.text_area(
                "Extra notes",
                key="user_notes",
                height=80,
                placeholder="Optional correction or context.",
            )

            edited_timestamp = datetime.combine(
                edited_date,
                edited_time if isinstance(edited_time, time) else edited_time.time(),
                tzinfo=get_now_local().tzinfo,
            )

            if st.button("Save Meal", width="stretch"):
                try:
                    pending_log = build_pending_log(
                        st.session_state["last_raw_text"],
                        edited_timestamp,
                    )
                    store.append(pending_log.finalize(created_at=get_now_local()))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Save failed: {exc}")
                else:
                    st.success("Meal saved.")
                    clear_review_state()
                    st.rerun()

    left, right = st.columns(2)
    with left:
        render_day_view(store)
    with right:
        render_week_view(store)


render_app()
