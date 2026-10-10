"""Integration tests for KPIs on the sample dataset (REQ-007, REQ-008, REQ-009).

Expected values calculated independently from data/sample/*.csv.
"""

from datetime import date
from pathlib import Path

import pytest

from src.analytics.kpis import KpiFilters, build_kpi_report
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
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", connection, MASTER_DIR, TODAY)
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", connection, MASTER_DIR, TODAY)
    yield connection
    connection.close()


def test_sample_dataset_kpis(conn):
    report = build_kpi_report(conn, MASTER_DIR, KpiFilters())

    assert report.production.total == 244_801
    assert report.production.shifts_worked == 234
    assert report.production.average_per_shift == pytest.approx(1046.158, abs=0.001)
    assert report.quality.scrap_total == 7_730
    assert report.quality.scrap_rate == pytest.approx(0.031577, abs=1e-6)
    assert report.downtime.unplanned_total == 7_541
    assert report.downtime.planned_total == 1_840
    assert report.downtime.average_unplanned_per_shift == pytest.approx(32.226, abs=0.001)
    assert report.downtime.by_cause.iloc[0]["downtime_reason"] == "Falla de máquina"
    assert report.orphans_excluded == 0


def test_heatmap_shows_l2_scrap_concentrated_in_shifts_1_and_2(conn):
    """A1 is visible in the shift × week view: shifts 1 and 2 at ~9%, shift 3 normal."""
    report = build_kpi_report(conn, MASTER_DIR, KpiFilters(lines=["L2"]))

    last_week = report.quality.by_shift_week[date(2026, 9, 28)]
    assert last_week.loc[1] == pytest.approx(0.0899, abs=1e-4)
    assert last_week.loc[2] == pytest.approx(0.0900, abs=1e-4)
    assert last_week.loc[3] == pytest.approx(0.0291, abs=1e-4)


def test_filters_reach_all_kpis(conn):
    report = build_kpi_report(conn, MASTER_DIR, KpiFilters(lines=["L1"]))

    assert report.production.total == 104_133
    assert report.quality.scrap_total == 2_628
    assert set(report.downtime.by_line["line"]) == {"L1"}


def test_orphans_are_excluded_and_counted(conn):
    load_production_file(
        SAMPLE_DIR / "production_reload.csv", "production_reload.csv", conn, MASTER_DIR, TODAY
    )

    report = build_kpi_report(conn, MASTER_DIR, KpiFilters())

    assert report.orphans_excluded == 2
    assert report.downtime.total == 7_541 + 1_840 - 25  # 19 + 6 orphan minutes excluded


def test_no_data_for_filters(conn):
    report = build_kpi_report(conn, MASTER_DIR, KpiFilters(lines=["L9"]))

    assert report.has_data is False
