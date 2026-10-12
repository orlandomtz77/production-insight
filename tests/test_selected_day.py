"""Integration tests for REQ-015: review a selected day, on the sample dataset."""

from datetime import date
from pathlib import Path

import pytest

from src.anomaly_detection.alerts import run_alerts
from src.database.connection import connect
from src.ingestion.load_downtime import load_downtime_file
from src.ingestion.load_production import load_production_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
TODAY = date(2026, 10, 7)


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    connection = connect(tmp_path_factory.mktemp("db") / "test.db")
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", connection, MASTER_DIR, TODAY)
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", connection, MASTER_DIR, TODAY)
    yield connection
    connection.close()


def ranking(report):
    return [(a.line, a.metric) for a in report.alerts]


def test_default_day_is_unchanged(conn):
    default = run_alerts(conn, MASTER_DIR)
    selected = run_alerts(conn, MASTER_DIR, day=date(2026, 9, 30))

    assert default.evaluated_day == date(2026, 9, 30)
    assert ranking(default) == ranking(selected)
    assert [round(a.priority_score) for a in selected.alerts] == [997, 652, 537]


def test_first_day_of_a1_shows_only_l2_scrap(conn):
    report = run_alerts(conn, MASTER_DIR, day=date(2026, 9, 28))

    assert report.evaluated_day == date(2026, 9, 28)
    assert ranking(report) == [("L2", "scrap_rate")]
    assert report.alerts[0].frequency == 1
    assert report.alerts[0].baseline_last_day == date(2026, 9, 26)  # never later days


def test_a3_day_cannot_be_evaluated_with_short_history(conn):
    report = run_alerts(conn, MASTER_DIR, day=date(2026, 9, 10))

    assert report.alerts == []
    reasons = {reason for _, _, reason in report.not_evaluated}
    assert reasons == {"insufficient_history"}
