"""Production records. The caller owns the transaction (ADR-004)."""

import sqlite3

import pandas as pd

from src.database import shift_replacement

TABLE = "production_records"


def replace_shifts(conn: sqlite3.Connection, rows: pd.DataFrame) -> tuple[int, int]:
    """Replace every production shift present in `rows`. Return (replaced, new)."""
    return shift_replacement.replace_shifts(conn, TABLE, rows)


def existing_keys(conn: sqlite3.Connection) -> set[tuple[str, str, int, str]]:
    """All stored date + line + shift + product keys (used to detect orphan downtime)."""
    return set(conn.execute(f"SELECT date, line, shift, product FROM {TABLE}").fetchall())
