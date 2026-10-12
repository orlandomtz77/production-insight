"""Database maintenance (REQ-017)."""

import sqlite3

TABLES = ("downtime_events", "production_records", "load_history")


def clear_all_data(conn: sqlite3.Connection) -> None:
    """Delete production, downtime and load history in one transaction. Master lists are files, untouched."""
    with conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
