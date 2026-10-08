"""Write production records and load history.

The caller owns the transaction (`with conn:`), so a whole upload is committed or
rolled back together (ADR-004). Functions here never commit.
"""

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


def replace_shifts(conn: sqlite3.Connection, rows: pd.DataFrame) -> tuple[int, int]:
    """Replace every shift present in `rows` (ADR-002). Return (shifts_replaced, shifts_new)."""
    replaced = new = 0
    for (day, line, shift), shift_rows in rows.groupby(["date", "line", "shift"], sort=True):
        params = (day, line, int(shift))
        deleted = conn.execute(
            "DELETE FROM production_records WHERE date = ? AND line = ? AND shift = ?", params
        ).rowcount
        if deleted:
            replaced += 1
        else:
            new += 1
        conn.executemany(
            """
            INSERT INTO production_records
                (date, line, shift, product, production_quantity, scrap_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (day, line, int(shift), row.product, int(row.production_quantity), int(row.scrap_quantity))
                for row in shift_rows.itertuples(index=False)
            ],
        )
    return replaced, new


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
