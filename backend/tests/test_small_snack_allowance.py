from datetime import date
from zoneinfo import ZoneInfo

import pytest

from diettracker import database as database_module
from diettracker.stores import meal_store as meal_store_module
from diettracker.stores.meal_store import MealStore


@pytest.fixture
def temporary_schema(monkeypatch):
    schema = "diettracker_test"
    monkeypatch.setattr(database_module, "SCHEMA", schema)
    monkeypatch.setattr(meal_store_module, "SCHEMA", schema)
    with database_module.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield
    with database_module.connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def test_small_snack_allowances_are_created_once_and_stay_removed(temporary_schema):
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
