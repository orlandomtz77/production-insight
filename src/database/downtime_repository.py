"""Downtime events. The caller owns the transaction (ADR-004)."""

import sqlite3

import pandas as pd

from src.database import shift_replacement

TABLE = "downtime_events"


def replace_shifts(conn: sqlite3.Connection, rows: pd.DataFrame) -> tuple[int, int]:
    """Replace the events of every shift in `rows`, for all products. Return (replaced, new)."""
    return shift_replacement.replace_shifts(conn, TABLE, rows)
