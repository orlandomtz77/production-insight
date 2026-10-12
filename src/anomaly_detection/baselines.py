"""Baselines per line and metric (REQ-010).

A line is compared against its own previous Monday–Saturday days.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

MIN_BASELINE_DAYS = 10
# Floating point: the std of identical values can be ~1e-18 instead of 0.
ZERO_VARIATION = 1e-9
SUNDAY = 6


@dataclass(frozen=True)
class Metric:
    name: str
    label: str        # shown to the user (Spanish)
    direction: int    # +1: higher is unfavorable; −1: lower is unfavorable


METRICS = (
    Metric("production_per_available_shift", "Producción por turno disponible", -1),
    Metric("scrap_rate", "Scrap rate", +1),
    Metric("unplanned_downtime_per_shift", "Paro no programado por turno", +1),
)


@dataclass
class Baseline:
    line: str
    metric: str
    mean: float | None
    std: float | None
    sample_size: int
    first_day: date | None
    last_day: date | None
    status: str  # ok | insufficient_history | no_variation


def baseline_days(daily: pd.DataFrame, line: str, metric: str, evaluated: date) -> pd.DataFrame:
    """Previous Monday–Saturday days of the line with a value for the metric."""
    dates = pd.to_datetime(daily["date"])
    mask = (
        (daily["line"] == line)
        & (dates.dt.date < evaluated)
        & (dates.dt.weekday != SUNDAY)
        & daily[metric].notna()  # e.g., scrap rate on a day with zero production
    )
    return daily[mask]


def calculate_baseline(daily: pd.DataFrame, line: str, metric: str, evaluated: date) -> Baseline:
    days = baseline_days(daily, line, metric, evaluated)
    values = days[metric]
    n = len(values)

    if n < MIN_BASELINE_DAYS:
        return Baseline(line, metric, None, None, n, None, None, "insufficient_history")

    mean = float(values.mean())
    std = float(values.std(ddof=1))  # sample standard deviation
    first_day = date.fromisoformat(days["date"].min())
    last_day = date.fromisoformat(days["date"].max())
    status = "no_variation" if std <= ZERO_VARIATION * max(1.0, abs(mean)) else "ok"
    return Baseline(line, metric, mean, std, n, first_day, last_day, status)
