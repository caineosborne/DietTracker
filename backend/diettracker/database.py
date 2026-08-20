from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from psycopg import Connection, connect
from psycopg.rows import dict_row

LOCAL_DATABASE_URL = "postgresql://diettracker:diettracker_local@localhost:5432/diettracker"
SCHEMA = "diettracker"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / ".env")


def database_url() -> str:
    return os.getenv("DATABASE_URL", LOCAL_DATABASE_URL)


@contextmanager
def connection() -> Iterator[Connection]:
    """Open a short-lived connection for one unit of work, then release it."""
    with connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def initialize_database() -> None:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.meals (
                id TEXT PRIMARY KEY,
                consumed_at TIMESTAMPTZ NOT NULL,
                is_small_snack_allowance BOOLEAN NOT NULL DEFAULT FALSE,
                payload JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS meals_consumed_at_idx ON {SCHEMA}.meals (consumed_at)"
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.daily_activity (
                day DATE PRIMARY KEY,
                payload JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.weights (
                day DATE PRIMARY KEY,
                payload JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.small_snack_allowance_removals (
                day DATE PRIMARY KEY
            )
            """
        )
