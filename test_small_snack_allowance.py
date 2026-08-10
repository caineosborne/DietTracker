from datetime import date
from zoneinfo import ZoneInfo

from diettracker.stores import meal_store as meal_store_module
from diettracker.stores.meal_store import MealStore


def test_small_snack_allowances_are_created_once_and_stay_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(meal_store_module, "MEALS_FILE", tmp_path / "meals.json")
    monkeypatch.setattr(
        meal_store_module,
        "SMALL_SNACK_ALLOWANCE_REMOVALS_FILE",
        tmp_path / "small_snack_allowance_removals.json",
    )
    store = MealStore()
    tzinfo = ZoneInfo("Asia/Ho_Chi_Minh")

    assert store.ensure_small_snack_allowances(date(2026, 7, 14), date(2026, 7, 16), tzinfo) == 3
    allowances = [meal for meal in store.load_all() if meal.is_small_snack_allowance]
    assert [meal.timestamp.date() for meal in allowances] == [
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
    ]
    assert all(meal.total_calories_mid == 200 for meal in allowances)

    store.delete(allowances[0].id)
    assert store.ensure_small_snack_allowances(date(2026, 7, 14), date(2026, 7, 16), tzinfo) == 0
    assert [meal.timestamp.date() for meal in store.load_all()] == [date(2026, 7, 15), date(2026, 7, 16)]
