"""Unit tests for impact, frequency and priority score (REQ-013, ADR-003)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from src.anomaly_detection.baselines import Baseline
from src.anomaly_detection.deviations import Evaluation
from src.anomaly_detection.priority import daily_impact, line_rate, recurrence

PROD = "production_per_available_shift"
SCRAP = "scrap_rate"
DOWNTIME = "unplanned_downtime_per_shift"


def baseline(metric, mean, std=1.0, line="L1"):
    return Baseline(line, metric, mean, std, 25, None, None, "ok")


def evaluation(metric, value, mean, std, direction, line="L1"):
    return Evaluation(
        line=line, metric=metric, value=value, baseline=baseline(metric, mean, std, line),
        z=(value - mean) / std, percent_deviation=0.0, shifts_worked=3, direction=direction,
    )


def test_line_rate_from_requirements_example():
    # L1: baseline 1,200 pieces/shift, baseline downtime 40 min/shift.
    assert line_rate(1200, 40) == pytest.approx(1200 / 440)


def test_downtime_impact_from_requirements_example():
    # Evaluated day: 95 min/shift, 3 shifts worked → ≈ 450 pieces.
    day = pd.Series({DOWNTIME: 95, "shifts_worked": 3})

    impact = daily_impact(DOWNTIME, day, baseline_mean=40, rate=1200 / 440)

    assert impact == pytest.approx(450, abs=1)


def test_production_impact_uses_available_shifts():
    day = pd.Series({PROD: 900, "available_shifts": 2.75})

    assert daily_impact(PROD, day, baseline_mean=1000, rate=None) == pytest.approx(100 * 2.75)


def test_scrap_impact_is_extra_scrap_pieces():
    day = pd.Series({SCRAP: 0.07, "production": 3000})

    assert daily_impact(SCRAP, day, baseline_mean=0.03, rate=None) == pytest.approx(120)


def daily_values(values, metric=SCRAP, line="L1", start=date(2026, 9, 21)):
    rows, day = [], start
    for value in values:
        while day.weekday() == 6:
            day += timedelta(days=1)
        rows.append({"date": day.isoformat(), "line": line, "shifts_worked": 3,
                     "production": 1000, metric: value})
        day += timedelta(days=1)
    return pd.DataFrame(rows)


def test_recurrence_counts_last_6_working_days_beyond_threshold():
    # 8 working days; the last 6 are evaluated: 3 of them beyond mean + 2 std.
    daily = daily_values([0.09, 0.09, 0.03, 0.03, 0.03, 0.09, 0.09, 0.09])
    ev = evaluation(SCRAP, 0.09, mean=0.03, std=0.01, direction=+1)

    days, cumulative = recurrence(daily, ev, rate=None)

    assert [d.isoformat() for d in days] == ["2026-09-26", "2026-09-28", "2026-09-29"]
    assert cumulative == pytest.approx(3 * (0.09 - 0.03) * 1000)


def test_recurrence_ignores_favorable_days():
    daily = daily_values([0.03, 0.03, 0.03, 0.03, 0.00, 0.09])  # 0.00 is far but favorable
    ev = evaluation(SCRAP, 0.09, mean=0.03, std=0.01, direction=+1)

    days, _ = recurrence(daily, ev, rate=None)

    assert len(days) == 1


def test_recurrence_counts_6_working_days_up_to_the_selected_day():
    # Days 21..29 (Sun 27 skipped); select the 26th: window is 21..26.
    daily = daily_values([0.09, 0.03, 0.03, 0.03, 0.03, 0.09, 0.09, 0.09])
    ev = evaluation(SCRAP, 0.09, mean=0.03, std=0.01, direction=+1)

    days, _ = recurrence(daily, ev, rate=None, until=date(2026, 9, 26))

    assert [d.isoformat() for d in days] == ["2026-09-21", "2026-09-26"]
