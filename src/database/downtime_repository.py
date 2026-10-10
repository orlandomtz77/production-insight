"""Downtime events. The caller owns the transaction (ADR-004)."""

import sqlite3

import pandas as pd

from src.database import shift_replacement

TABLE = "downtime_events"


def replace_shifts(conn: sqlite3.Connection, rows: pd.DataFrame) -> tuple[int, int]:
    """Replace the events of every shift in `rows`, for all products. Return (replaced, new)."""
    return shift_replacement.replace_shifts(conn, TABLE, rows)


def orphan_events(conn: sqlite3.Connection) -> pd.DataFrame:
    """Downtime events without a production record for the same date + line + shift + product."""
    return pd.read_sql_query(
        """
        SELECT d.date, d.line, d.shift, d.product, d.downtime_minutes, d.downtime_reason
          FROM downtime_events d
          LEFT JOIN production_records p
            ON p.date = d.date
           AND p.line = d.line
           AND p.shift = d.shift
           AND p.product = d.product
         WHERE p.id IS NULL
         ORDER BY d.date, d.line, d.shift, d.id
        """,
        conn,
    )


def read_linked_events(conn: sqlite3.Connection) -> pd.DataFrame:
    """Downtime events that have a production record (orphans excluded)."""
    return pd.read_sql_query(
        """
        SELECT d.date, d.line, d.shift, d.product, d.downtime_minutes, d.downtime_reason
          FROM downtime_events d
         WHERE EXISTS (
               SELECT 1
                 FROM production_records p
                WHERE p.date = d.date
                  AND p.line = d.line
                  AND p.shift = d.shift
                  AND p.product = d.product)
        """,
        conn,
    )
