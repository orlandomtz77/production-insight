"""Integration tests for alerts of a period (REQ-016)."""

from datetime import date
from pathlib import Path

import pytest

from src.anomaly_detection.alerts import run_alerts, run_alerts_for_period
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


def keys(report):
    return [(a.evaluated_day, a.line, a.metric) for a in report.alerts]


def test_single_day_period_matches_daily_alerts(conn):
    day = date(2026, 9, 30)

    period = run_alerts_for_period(conn, MASTER_DIR, day, day)
    daily = run_alerts(conn, MASTER_DIR, day)

    assert keys(period) == keys(daily)
    assert [a.rank for a in period.alerts] == [1, 2, 3]


def test_week_lists_every_alert_with_its_date_sorted_by_score(conn):
    report = run_alerts_for_period(conn, MASTER_DIR, date(2026, 9, 28), date(2026, 10, 4))

    found = keys(report)
    assert (date(2026, 9, 28), "L2", "scrap_rate") in found
    for metric in ("scrap_rate",):
        assert (date(2026, 9, 30), "L2", metric) in found
    assert (date(2026, 9, 30), "L1", "production_per_available_shift") in found
    assert (date(2026, 9, 30), "L1", "unplanned_downtime_per_shift") in found
    scores = [a.priority_score for a in report.alerts]
    assert scores == sorted(scores, reverse=True)
    assert [a.rank for a in report.alerts] == list(range(1, len(report.alerts) + 1))
    assert report.evaluated_days == [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)]


def test_month_summarizes_lines_not_evaluated(conn):
    report = run_alerts_for_period(conn, MASTER_DIR, date(2026, 9, 1), date(2026, 9, 30))

    summary = {(line, metric, reason): days for line, metric, reason, days in report.not_evaluated}
    assert summary[("L1", "scrap_rate", "insufficient_history")] == 10  # Sep 1–11: fewer than 10 previous working days
    assert report.evaluated_lines == {"L1", "L2", "L3"}

