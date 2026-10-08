"""Load history (REQ-005). The caller owns the transaction."""

import sqlite3
from dataclasses import astuple, dataclass

import pandas as pd


@dataclass
class LoadSummary:
    loaded_at: str
    file_type: str
    file_name: str
    rows_read: int
    rows_stored: int
    rows_rejected: int
    shifts_replaced: int
    shifts_new: int
    shifts_rejected: int
    warnings: int
    status: str


def insert_load_history(conn: sqlite3.Connection, summary: LoadSummary) -> None:
    conn.execute(
        """
        INSERT INTO load_history
            (loaded_at, file_type, file_name, rows_read, rows_stored, rows_rejected,
             shifts_replaced, shifts_new, shifts_rejected, warnings, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        astuple(summary),
    )


def load_history(conn: sqlite3.Connection) -> pd.DataFrame:
    """All uploads, newest first."""
    return pd.read_sql_query("SELECT * FROM load_history ORDER BY id DESC", conn)
