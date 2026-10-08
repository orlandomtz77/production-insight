"""Integration tests for REQ-002: upload downtime CSV.

Expected values: data/sample/expected_results.md
"""

from datetime import date
from pathlib import Path

import pytest

from src.database.connection import connect
from src.ingestion.load_downtime import load_downtime_file
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


@pytest.fixture
def conn_with_production(conn):
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", conn, MASTER_DIR, TODAY)
    return conn


def load(conn, file_name):
    return load_downtime_file(SAMPLE_DIR / file_name, file_name, conn, MASTER_DIR, TODAY)


def events(conn, day, line, shift):
    return conn.execute(
        "SELECT product, downtime_minutes, downtime_reason FROM downtime_events "
        "WHERE date = ? AND line = ? AND shift = ? ORDER BY id",
        (day, line, shift),
    ).fetchall()


def test_downtime_before_production_is_rejected_as_orphan(conn):
    result = load(conn, "downtime.csv")

    assert result.summary.rows_stored == 0
    assert result.summary.rows_rejected == 484
    assert {error.code for error in result.errors} == {"orphan_event"}


def test_main_file_loads_without_rejections(conn_with_production):
    result = load(conn_with_production, "downtime.csv")

    assert result.summary.status == "completed"
    assert result.summary.file_type == "downtime"
    assert result.summary.rows_stored == 484
    assert result.summary.rows_rejected == 0
    assert result.summary.shifts_new == 234
    assert result.summary.warnings == 0


def test_invalid_file_rejects_each_case(conn_with_production):
    load(conn_with_production, "downtime.csv")
    before_rejected_shift = events(conn_with_production, "2026-09-04", "L1", 1)

    result = load(conn_with_production, "downtime_invalid.csv")

    codes_by_row = {error.row: error.code for error in result.errors}
    assert codes_by_row == {
        2: "orphan_event",
        3: "unknown_reason",
        4: "not_positive",
        5: "shift_total_exceeded",
        6: "shift_total_exceeded",
    }
    assert result.summary.rows_stored == 1
    assert result.summary.shifts_replaced == 1
    assert result.summary.shifts_rejected == 4
    # Accepted shift: its 4 previous events are replaced by 1.
    assert events(conn_with_production, "2026-09-04", "L2", 1) == [
        ("Producto C", 25, "Mantenimiento")
    ]
    # Rejected shift: existing events are kept.
    assert events(conn_with_production, "2026-09-04", "L1", 1) == before_rejected_shift


def test_reload_replaces_events_of_all_products_in_shift(conn_with_production):
    load(conn_with_production, "downtime.csv")
    assert len(events(conn_with_production, "2026-09-29", "L3", 1)) == 3

    load(conn_with_production, "downtime_invalid.csv")  # does not touch this shift
    assert len(events(conn_with_production, "2026-09-29", "L3", 1)) == 3

    result = load(conn_with_production, "downtime.csv")
    assert result.summary.shifts_replaced == 234
    assert conn_with_production.execute("SELECT COUNT(*) FROM downtime_events").fetchone()[0] == 484


def test_production_reload_leaves_orphan_events(conn_with_production):
    """REQ-001 open point: replacing a production shift does not delete downtime events."""
    load(conn_with_production, "downtime.csv")

    load_production_file(
        SAMPLE_DIR / "production_reload.csv", "production_reload.csv",
        conn_with_production, MASTER_DIR, TODAY,
    )

    orphans = conn_with_production.execute(
        """
        SELECT d.downtime_minutes, d.downtime_reason
          FROM downtime_events d
          LEFT JOIN production_records p
            ON p.date = d.date AND p.line = d.line AND p.shift = d.shift AND p.product = d.product
         WHERE p.id IS NULL
         ORDER BY d.id
        """
    ).fetchall()
    assert orphans == [(19, "Ajuste / Cambio de modelo"), (6, "Otro")]
