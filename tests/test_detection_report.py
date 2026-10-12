"""Integration tests for REQ-010 and REQ-011 on the sample dataset.

Expected values: data/sample/expected_results.md, section 3.
"""

from datetime import date
from pathlib import Path

import pytest

from src.anomaly_detection.deviations import run_detection
from src.database.connection import connect
from src.ingestion.load_downtime import load_downtime_file
from src.ingestion.load_production import load_production_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
TODAY = date(2026, 10, 7)

PROD = "production_per_available_shift"
SCRAP = "scrap_rate"
DOWNTIME = "unplanned_downtime_per_shift"

# line, metric, value, mean, std, z, alert
EXPECTED = [
    ("L1", PROD, 1104.5, 1324.5, 30.9, -7.11, True),
    ("L1", SCRAP, 0.0235, 0.0253, 0.0021, -0.85, False),
    ("L1", DOWNTIME, 88.3, 27.2, 7.7, 7.91, True),
    ("L2", PROD, 1024.0, 1029.6, 28.6, -0.20, False),
    ("L2", SCRAP, 0.0746, 0.0337, 0.0110, 3.71, True),
    ("L2", DOWNTIME, 42.7, 31.5, 10.1, 1.11, False),
    ("L3", PROD, 832.8, 830.5, 20.5, 0.11, False),
    ("L3", SCRAP, 0.0348, 0.0376, 0.0131, -0.22, False),
    ("L3", DOWNTIME, 29.7, 35.9, 10.0, -0.62, False),
]


def displayed(expected: float):
    """Tolerance: half a unit of the last digit shown in expected_results.md."""
    decimals = len(repr(expected).split(".")[1]) if "." in repr(expected) else 0
    return pytest.approx(expected, abs=0.5 * 10**-decimals + 1e-12)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    conn = connect(tmp_path_factory.mktemp("db") / "test.db")
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", conn, MASTER_DIR, TODAY)
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", conn, MASTER_DIR, TODAY)
    yield run_detection(conn, MASTER_DIR)
    conn.close()


def test_evaluated_day(result):
    assert result.evaluated_day == date(2026, 9, 30)


@pytest.mark.parametrize(("line", "metric", "value", "mean", "std", "z", "alert"), EXPECTED)
def test_baselines_and_z_match_expected_results(result, line, metric, value, mean, std, z, alert):
    evaluation = result.evaluations[(line, metric)]

    assert evaluation.baseline.sample_size == 25
    assert evaluation.value == displayed(value)
    assert evaluation.baseline.mean == displayed(mean)
    assert evaluation.baseline.std == displayed(std)
    assert evaluation.z == displayed(z)
    assert evaluation.is_deviation is alert


def test_detected_deviations(result):
    detected = {(d.line, d.metric) for d in result.deviations}

    assert detected == {("L1", PROD), ("L1", DOWNTIME), ("L2", SCRAP)}


def test_planned_stop_p2_does_not_raise_production_alert(result):
    assert ("L2", PROD) not in {(d.line, d.metric) for d in result.deviations}
