"""Integration tests for REQ-012 and REQ-013 on the sample dataset.

Expected values: data/sample/expected_results.md, sections 4 and 5.
"""

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
def report(tmp_path_factory):
    conn = connect(tmp_path_factory.mktemp("db") / "test.db")
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", conn, MASTER_DIR, TODAY)
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", conn, MASTER_DIR, TODAY)
    yield run_alerts(conn, MASTER_DIR)
    conn.close()


def test_ranking_matches_expected_results(report):
    ranking = [(a.rank, a.line, a.metric) for a in report.alerts]

    assert ranking == [
        (1, "L2", "scrap_rate"),
        (2, "L1", "production_per_available_shift"),
        (3, "L1", "unplanned_downtime_per_shift"),
    ]


@pytest.mark.parametrize(
    ("rank", "daily_impact", "frequency", "cumulative", "score"),
    [
        (1, 115.0, 3, 332.2, 997),
        (2, 651.9, 1, 651.9, 652),
        (3, 536.6, 1, 536.6, 537),
    ],
)
def test_priority_values(report, rank, daily_impact, frequency, cumulative, score):
    alert = report.alerts[rank - 1]

    assert alert.daily_impact == pytest.approx(daily_impact, abs=0.05)
    assert alert.frequency == frequency
    assert alert.cumulative_impact == pytest.approx(cumulative, abs=0.05)
    assert alert.priority_score == pytest.approx(score, abs=0.5)


def test_a1_recurrence_days(report):
    assert report.alerts[0].recurrence_days == [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)]


def test_l1_line_rate(report):
    downtime_alert = report.alerts[2]

    assert downtime_alert.line_rate == pytest.approx(2.925, abs=0.0005)


def test_investigation_area_scrap_points_to_product_c(report):
    area = report.alerts[0].investigation

    assert area.focus == "Producto C"
    assert area.value == pytest.approx(0.09, abs=0.001)
    assert area.shifts == [1, 2]


def test_investigation_area_downtime_points_to_machine_failure_shift_2(report):
    area = report.alerts[2].investigation

    assert area.focus == "Falla de máquina"
    assert area.value == 206  # unplanned minutes of that cause on the line that day
    assert area.shifts == [2]  # shift with the most minutes of that cause


def test_investigation_area_production_points_to_shift_2(report):
    area = report.alerts[1].investigation

    assert area.shifts == [2]
    assert area.focus == "Falla de máquina"  # main unplanned downtime cause that day


def test_alert_explains_baseline_period(report):
    alert = report.alerts[0]

    assert alert.baseline_first_day == date(2026, 9, 1)
    assert alert.baseline_last_day == date(2026, 9, 29)
    assert alert.sample_size == 25
