"""Impact, recurrence and priority score (REQ-013, ADR-003).

Priority Score    = Cumulative Impact × Frequency
Cumulative Impact = lost pieces over the days beyond the threshold in the last 6 working days
"""

from datetime import date

import pandas as pd

from src.anomaly_detection.baselines import SUNDAY
from src.anomaly_detection.daily_metrics import SHIFT_MINUTES
from src.anomaly_detection.deviations import ALERT_THRESHOLD, Evaluation

RECURRENCE_WINDOW = 6  # working days, including the evaluated day

PROD = "production_per_available_shift"
SCRAP = "scrap_rate"
DOWNTIME = "unplanned_downtime_per_shift"


def line_rate(mean_production_per_shift: float, mean_unplanned_downtime: float) -> float:
    """Pieces per minute of the line, from its own baseline."""
    return mean_production_per_shift / (SHIFT_MINUTES - mean_unplanned_downtime)


def daily_impact(metric: str, day: pd.Series, baseline_mean: float, rate: float | None) -> float:
    """Lost pieces on one day compared with the baseline."""
    if metric == PROD:
        return (baseline_mean - day[PROD]) * day["available_shifts"]
    if metric == SCRAP:
        return (day[SCRAP] - baseline_mean) * day["production"]
    if metric == DOWNTIME:
        return (day[DOWNTIME] - baseline_mean) * day["shifts_worked"] * rate
    raise ValueError(f"Unknown metric '{metric}'.")


def last_working_days(daily: pd.DataFrame, count: int = RECURRENCE_WINDOW) -> list[date]:
    dates = pd.to_datetime(daily["date"].drop_duplicates())
    working = sorted(dates[dates.dt.weekday != SUNDAY].dt.date)
    return working[-count:]


def recurrence(
    daily: pd.DataFrame, evaluation: Evaluation, rate: float | None
) -> tuple[list[date], float]:
    """Days in the last working days beyond the threshold, and their cumulative impact.

    Uses the same baseline (mean, std) as the evaluated day.
    """
    baseline = evaluation.baseline
    line_days = daily[daily["line"] == evaluation.line].set_index("date")

    days, cumulative = [], 0.0
    for day in last_working_days(daily):
        if day.isoformat() not in line_days.index:
            continue
        row = line_days.loc[day.isoformat()]
        value = row[evaluation.metric]
        if pd.isna(value):
            continue
        z = (value - baseline.mean) / baseline.std
        if evaluation.direction * z > ALERT_THRESHOLD:
            days.append(day)
            cumulative += daily_impact(evaluation.metric, row, baseline.mean, rate)
    return days, cumulative
