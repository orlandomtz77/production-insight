"""Integration tests for REQ-005: data quality report.

Expected values: data/sample/expected_results.md, section 2.
"""

from datetime import date
from pathlib import Path

import pytest

from src.analytics.data_quality import build_data_quality_report
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
def loaded(conn):
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", conn, MASTER_DIR, TODAY)
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", conn, MASTER_DIR, TODAY)
    return conn


def test_empty_database_reports_no_data(conn):
    report = build_data_quality_report(conn, MASTER_DIR)

    assert report.has_data is False
    assert report.coverage is None
    assert report.orphan_events.empty
    assert report.load_history.empty
    assert report.planned_stops_invalid == []


def test_coverage_of_sample_dataset(loaded):
    coverage = build_data_quality_report(loaded, MASTER_DIR).coverage

    assert coverage.period_start == date(2026, 9, 1)
    assert coverage.period_end == date(2026, 9, 30)
    assert coverage.expected_shifts == 233  # 234 − 1 planned stop (P1)
    assert coverage.covered_shifts == 232
    assert round(coverage.coverage_percent, 1) == 99.6
    assert coverage.planned_stop_shifts == 1
    assert coverage.missing_shifts == [("2026-09-15", "L3", 3)]
    assert coverage.overtime_shifts == [("2026-09-27", "L1", 1), ("2026-09-27", "L1", 2)]


def test_sample_dataset_has_no_orphans(loaded):
    assert build_data_quality_report(loaded, MASTER_DIR).orphan_events.empty


def test_orphans_after_production_reload(loaded):
    load_production_file(
        SAMPLE_DIR / "production_reload.csv", "production_reload.csv", loaded, MASTER_DIR, TODAY
    )

    orphans = build_data_quality_report(loaded, MASTER_DIR).orphan_events

    assert list(orphans.columns) == [
        "date", "line", "shift", "product", "downtime_minutes", "downtime_reason"
    ]
    assert orphans["downtime_minutes"].tolist() == [19, 6]
    assert set(orphans["product"]) == {"Producto E"}


def test_load_history_newest_first(loaded):
    load_production_file(
        SAMPLE_DIR / "production_missing_column.csv", "production_missing_column.csv",
        loaded, MASTER_DIR, TODAY,
    )

    history = build_data_quality_report(loaded, MASTER_DIR).load_history

    assert history["file_name"].tolist() == [
        "production_missing_column.csv", "downtime.csv", "production.csv"
    ]
    assert history["status"].tolist() == ["rejected", "completed", "completed"]
