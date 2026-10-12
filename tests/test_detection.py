"""Unit tests for daily metrics, baselines and deviations (REQ-010, REQ-011)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from src.anomaly_detection.baselines import calculate_baseline
from src.anomaly_detection.daily_metrics import daily_line_metrics
from src.anomaly_detection.deviations import detect_deviations, evaluated_day

PLANNED = frozenset({"Mantenimiento", "Paro programado"})


def daily(values, metric="scrap_rate", line="L1", start=date(2026, 9, 1), shifts=3):
    """Daily metrics table with one value per working day (Mon–Sat) for one line and metric."""
    rows, day = [], start
    for value in values:
        while day.weekday() == 6:
            day += timedelta(days=1)
        rows.append({"date": day.isoformat(), "line": line, "shifts_worked": shifts, metric: value})
        day += timedelta(days=1)
    return pd.DataFrame(rows)


# --- Daily metrics -------------------------------------------------------------

def test_daily_metrics_use_available_shifts_and_unplanned_downtime():
    production = pd.DataFrame(
        [("2026-09-01", "L1", s, "Producto A", 900, 18) for s in (1, 2, 3)],
        columns=["date", "line", "shift", "product", "production_quantity", "scrap_quantity"],
    )
    events = pd.DataFrame(
        [
            ("2026-09-01", "L1", 1, "Producto A", 120, "Paro programado"),
            ("2026-09-01", "L1", 2, "Producto A", 60, "Falla de máquina"),
        ],
        columns=["date", "line", "shift", "product", "downtime_minutes", "downtime_reason"],
    )

    row = daily_line_metrics(production, events, PLANNED).iloc[0]

    assert row["available_shifts"] == pytest.approx((3 * 480 - 120) / 480)  # 2.75
    assert row["production_per_available_shift"] == pytest.approx(2700 / 2.75)
    assert row["unplanned_downtime_per_shift"] == pytest.approx(60 / 3)
    assert row["scrap_rate"] == pytest.approx(54 / 2700)


def test_scrap_rate_is_nan_when_day_production_is_zero():
    production = pd.DataFrame(
        [("2026-09-01", "L1", 1, "Producto A", 0, 0)],
        columns=["date", "line", "shift", "product", "production_quantity", "scrap_quantity"],
    )
    events = pd.DataFrame(columns=["date", "line", "shift", "product", "downtime_minutes", "downtime_reason"])

    row = daily_line_metrics(production, events, PLANNED).iloc[0]

    assert pd.isna(row["scrap_rate"])
    assert row["unplanned_downtime_per_shift"] == 0


# --- Evaluated day -------------------------------------------------------------

def test_evaluated_day_is_last_monday_to_saturday_with_data():
    df = pd.DataFrame({"date": ["2026-09-25", "2026-09-26", "2026-09-27"]})  # Fri, Sat, Sun

    assert evaluated_day(df) == date(2026, 9, 26)


# --- Baselines -----------------------------------------------------------------

def test_baseline_excludes_evaluated_day_and_uses_sample_std():
    values = [0.02, 0.04] * 6 + [0.50]  # 12 baseline days, then the evaluated day
    df = daily(values)
    evaluated = date.fromisoformat(df["date"].iloc[-1])

    baseline = calculate_baseline(df, "L1", "scrap_rate", evaluated)

    assert baseline.status == "ok"
    assert baseline.sample_size == 12
    assert baseline.mean == pytest.approx(0.03)
    assert baseline.std == pytest.approx(pd.Series([0.02, 0.04] * 6).std(ddof=1))


def test_baseline_excludes_sundays():
    df = daily([0.03] * 12)
    sunday = pd.DataFrame([{"date": "2026-09-06", "line": "L1", "shifts_worked": 2, "scrap_rate": 0.90}])

    baseline = calculate_baseline(pd.concat([df, sunday]), "L1", "scrap_rate", date(2026, 9, 30))

    assert baseline.mean == pytest.approx(0.03)


def test_baseline_with_less_than_10_days_is_insufficient():
    df = daily([0.03, 0.04] * 4 + [0.05])  # 8 baseline days

    baseline = calculate_baseline(df, "L1", "scrap_rate", date.fromisoformat(df["date"].iloc[-1]))

    assert baseline.status == "insufficient_history"


def test_baseline_without_variation():
    df = daily([0.03] * 12 + [0.05])

    baseline = calculate_baseline(df, "L1", "scrap_rate", date.fromisoformat(df["date"].iloc[-1]))

    assert baseline.status == "no_variation"


def test_including_the_evaluated_day_would_shrink_the_deviation():
    """Why the evaluated day is excluded: the anomaly inflates mean and std of its own baseline."""
    baseline_values = [0.02, 0.04] * 6
    anomaly = 0.10
    df = daily(baseline_values + [anomaly])
    evaluated = date.fromisoformat(df["date"].iloc[-1])

    correct = calculate_baseline(df, "L1", "scrap_rate", evaluated)
    z_correct = (anomaly - correct.mean) / correct.std

    contaminated = pd.Series(baseline_values + [anomaly])
    z_contaminated = (anomaly - contaminated.mean()) / contaminated.std(ddof=1)

    assert z_correct == pytest.approx(6.70, abs=0.01)
    assert z_contaminated == pytest.approx(2.96, abs=0.01)  # less than half


# --- Deviations ----------------------------------------------------------------

def test_unfavorable_deviation_beyond_2_std_is_detected():
    df = daily([0.02, 0.04] * 6 + [0.10])

    result = detect_deviations(df)

    assert len(result.deviations) == 1
    deviation = result.deviations[0]
    assert deviation.line == "L1"
    assert deviation.metric == "scrap_rate"
    assert deviation.value == pytest.approx(0.10)
    assert deviation.percent_deviation == pytest.approx((0.10 - 0.03) / 0.03 * 100)
    assert deviation.sample_size == 12


def test_favorable_deviation_is_not_an_alert():
    df = daily([0.02, 0.04] * 6 + [0.0])  # very low scrap is good news

    assert detect_deviations(df).deviations == []


def test_production_alert_is_for_lower_values_only():
    high = daily([1000, 1100] * 6 + [5000], metric="production_per_available_shift")
    low = daily([1000, 1100] * 6 + [500], metric="production_per_available_shift")

    assert detect_deviations(high).deviations == []
    assert len(detect_deviations(low).deviations) == 1


def test_lines_without_valid_baseline_are_listed_as_not_evaluated():
    df = daily([0.03, 0.04] * 4 + [0.05])  # insufficient history

    result = detect_deviations(df)

    assert result.deviations == []
    assert ("L1", "scrap_rate", "insufficient_history") in result.not_evaluated


def test_line_without_production_on_evaluated_day_is_not_evaluated():
    l1 = daily([0.02, 0.04] * 6 + [0.03], line="L1")
    l2 = daily([0.02, 0.04] * 6, line="L2")  # no data on the evaluated day

    result = detect_deviations(pd.concat([l1, l2]))

    assert ("L2", "scrap_rate", "no_production") in result.not_evaluated


# --- Selected day (REQ-015) ------------------------------------------------------

def test_selected_day_ignores_later_days():
    values = [0.02, 0.04] * 6 + [0.10] + [0.90] * 3  # anomaly, then three later extreme days
    df = daily(values)
    selected = date.fromisoformat(df["date"].iloc[12])

    result = detect_deviations(df, day=selected)

    assert result.evaluated_day == selected
    deviation = result.deviations[0]
    assert deviation.baseline.mean == pytest.approx(0.03)  # later days not in the baseline
    assert deviation.value == pytest.approx(0.10)


def test_working_days_are_monday_to_saturday_newest_first():
    from src.anomaly_detection.deviations import working_days

    df = pd.DataFrame({"date": ["2026-09-26", "2026-09-27", "2026-09-28", "2026-09-28"]})

    assert working_days(df) == [date(2026, 9, 28), date(2026, 9, 26)]  # Sunday 27 excluded
