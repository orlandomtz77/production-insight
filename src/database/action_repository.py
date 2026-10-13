"""Action plan storage (REQ-019). Each write is its own transaction."""

import sqlite3

import pandas as pd

from src.action_plan.model import DONE, ActionItem

COLUMNS = [
    "id", "problem", "line", "action", "owner", "due_date", "priority", "stage",
    "source_alert", "created_at", "updated_at", "closed_at",
]


def create_action(conn: sqlite3.Connection, item: ActionItem, now: str) -> int:
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO action_items
                (problem, line, action, owner, due_date, priority, stage, source_alert,
                 created_at, updated_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.problem.strip(), item.line, item.action.strip(), item.owner.strip(),
                item.due_date.isoformat(), item.priority, item.stage, item.source_alert,
                now, now, now if item.stage == DONE else None,
            ),
        )
    return cursor.lastrowid


def update_action(conn: sqlite3.Connection, item: ActionItem, now: str) -> None:
    """Update an action. Reaching 'done' records the closing date (kept while it stays done);
    leaving 'done' clears it."""
    with conn:
        conn.execute(
            """
            UPDATE action_items
               SET problem = ?, line = ?, action = ?, owner = ?, due_date = ?, priority = ?,
                   stage = ?, updated_at = ?,
                   closed_at = CASE WHEN ? = ? THEN COALESCE(closed_at, ?) ELSE NULL END
             WHERE id = ?
            """,
            (
                item.problem.strip(), item.line, item.action.strip(), item.owner.strip(),
                item.due_date.isoformat(), item.priority, item.stage, now,
                item.stage, DONE, now,
                item.id,
            ),
        )


def list_actions(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(f"SELECT {', '.join(COLUMNS)} FROM action_items ORDER BY due_date, id", conn)
    return df.astype(object).where(df.notna(), None)


def action_for_alert(conn: sqlite3.Connection, key: str) -> tuple[int, str] | None:
    """(id, stage) of the action created from this alert, if any."""
    return conn.execute("SELECT id, stage FROM action_items WHERE source_alert = ?", (key,)).fetchone()
