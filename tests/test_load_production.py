"""Integration tests for REQ-001: upload production CSV.

Expected values: data/sample/expected_results.md
"""

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.database.connection import connect
from src.database import production_repository
from src.ingestion.load_production import load_production_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
TODAY = date(2026, 10, 7)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()


def load(conn, file_name, master_dir=MASTER_DIR):
    return load_production_file(SAMPLE_DIR / file_name, file_name, conn, master_dir, TODAY)


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_main_file_loads_without_rejections(conn):
    result = load(conn, "production.csv")

    assert result.summary.status == "completed"
    assert result.summary.rows_read == 263
    assert result.summary.rows_stored == 263
    assert result.summary.rows_rejected == 0
    assert result.summary.shifts_new == 234  # 232 Mon–Sat + 2 Sunday overtime
    assert result.summary.shifts_replaced == 0
    assert count(conn, "production_records") == 263


def test_invalid_file_stores_valid_shifts_and_reports_errors(conn):
    result = load(conn, "production_invalid.csv")

    assert result.summary.status == "completed"
    assert result.summary.rows_stored == 2
    assert result.summary.rows_rejected == 10
    assert result.summary.shifts_new == 2
    assert result.summary.shifts_rejected == 4  # L1/2, L1/3, L2/2, L3/1 on 2026-09-02
    stored = conn.execute("SELECT date, line, shift FROM production_records ORDER BY line").fetchall()
    assert stored == [("2026-09-02", "L1", 1), ("2026-09-02", "L3", 2)]
    rejected_rows = {error.row for error in result.errors}
    assert rejected_rows == set(range(3, 13))  # Excel rows 3..12; rows 2 and 13 are valid


def test_missing_column_rejects_whole_file(conn):
    result = load(conn, "production_missing_column.csv")

    assert result.summary.status == "rejected"
    assert any("scrap_quantity" in message for message in result.file_errors)
    assert count(conn, "production_records") == 0


def test_missing_master_list_rejects_whole_file(conn, tmp_path):
    result = load(conn, "production.csv", master_dir=tmp_path / "missing")

    assert result.summary.status == "rejected"
    assert result.file_errors
    assert count(conn, "production_records") == 0


def test_empty_file_rejects_whole_file(conn, tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("date,line,shift,product,production_quantity,scrap_quantity\n", encoding="utf-8")

    result = load_production_file(empty, "empty.csv", conn, MASTER_DIR, TODAY)

    assert result.summary.status == "rejected"
    assert result.file_errors


def test_extra_columns_are_ignored_with_warning(conn, tmp_path):
    df = pd.read_csv(SAMPLE_DIR / "production.csv", dtype=str).head(3)
    df["comments"] = "x"
    path = tmp_path / "extra.csv"
    df.to_csv(path, index=False)

    result = load_production_file(path, "extra.csv", conn, MASTER_DIR, TODAY)

    assert result.summary.rows_stored == 3
    assert result.summary.warnings == 1
    assert any("comments" in warning for warning in result.warnings)


def test_reload_replaces_whole_shift(conn):
    load(conn, "production.csv")

    result = load(conn, "production_reload.csv")

    assert result.summary.shifts_replaced == 1
    assert result.summary.shifts_new == 0
    shift_rows = conn.execute(
        "SELECT product FROM production_records WHERE date='2026-09-29' AND line='L3' AND shift=1"
    ).fetchall()
    assert shift_rows == [("Producto D",)]
    assert count(conn, "production_records") == 262


def test_loading_same_file_twice_gives_same_result(conn):
    load(conn, "production.csv")
    result = load(conn, "production.csv")

    assert result.summary.shifts_replaced == 234
    assert count(conn, "production_records") == 263


def test_every_upload_is_recorded_in_load_history(conn):
    load(conn, "production.csv")
    load(conn, "production_missing_column.csv")

    history = conn.execute(
        "SELECT file_name, file_type, status FROM load_history ORDER BY id"
    ).fetchall()
    assert history == [
        ("production.csv", "production", "completed"),
        ("production_missing_column.csv", "production", "rejected"),
    ]


def test_failed_write_leaves_database_unchanged(conn):
    """If the database rejects a row (safety net), no shift is partially stored."""
    rows = pd.DataFrame(
        [
            ("2026-09-01", "L1", 1, "Producto A", 1000, 30),
            ("2026-09-01", "L1", 2, "Producto A", 100, 150),  # violates CHECK
        ],
        columns=["date", "line", "shift", "product", "production_quantity", "scrap_quantity"],
    )

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            production_repository.replace_shifts(conn, rows)

    assert count(conn, "production_records") == 0
