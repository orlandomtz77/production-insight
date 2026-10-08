"""SQLite connection and schema setup (ADR-004)."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "production_insight.db"


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the database and create the tables if they do not exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn
