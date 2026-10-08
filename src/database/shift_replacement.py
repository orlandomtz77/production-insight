"""Replace whole shifts in a table (ADR-002). The caller owns the transaction (ADR-004)."""

import sqlite3

import pandas as pd


def replace_shifts(conn: sqlite3.Connection, table: str, rows: pd.DataFrame) -> tuple[int, int]:
    """Delete every shift present in `rows` and insert its rows.

    `table` is an internal constant (never user input); its columns are those of `rows`.
    Return (shifts_replaced, shifts_new).
    """
    columns = list(rows.columns)
    insert_sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})"
    )
    replaced = new = 0
    for (day, line, shift), shift_rows in rows.groupby(["date", "line", "shift"], sort=True):
        deleted = conn.execute(
            f"DELETE FROM {table} WHERE date = ? AND line = ? AND shift = ?",
            (day, line, int(shift)),
        ).rowcount
        if deleted:
            replaced += 1
        else:
            new += 1
        conn.executemany(
            insert_sql,
            [
                tuple(value.item() if hasattr(value, "item") else value for value in record)
                for record in shift_rows.itertuples(index=False)
            ],
        )
    return replaced, new
