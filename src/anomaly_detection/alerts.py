"""Explainable, prioritized alerts (REQ-012, REQ-013).

Alerts are structured data. Text for the user is built in src/dashboard/formatting.py.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from src.anomaly_detection.baselines import calculate_baseline
from src.anomaly_detection.daily_metrics import daily_line_metrics
from src.anomaly_detection.deviations import DetectionResult, Evaluation, detect_deviations
from src.anomaly_detection.priority import DOWNTIME, PROD, SCRAP, daily_impact, line_rate, recurrence
from src.database import downtime_repository, production_repository
from src.ingestion.master_data import load_master_lists


@dataclass
class InvestigationArea:
    """Where to start looking (not the root cause).

    scrap:      focus = product with the highest scrap rate, value = its rate
    downtime:   focus = unplanned cause with most minutes, value = its minutes
    production: focus = main unplanned downtime cause, value = its minutes
    shifts:     shifts to look at
    """

    focus: str | None
    value: float | None
    shifts: list[int] = field(default_factory=list)


@dataclass
class Alert:
    rank: int
    line: str
    metric: str
    evaluated_day: date
    value: float
    baseline_mean: float
    baseline_std: float
    sample_size: int
    baseline_first_day: date
    baseline_last_day: date
    z: float
    percent_deviation: float
    daily_impact: float
    cumulative_impact: float
    frequency: int
    recurrence_days: list[date]
    priority_score: float
    line_rate: float | None
    investigation: InvestigationArea


@dataclass
class AlertReport:
    evaluated_day: date | None
    alerts: list[Alert]
    not_evaluated: list[tuple[str, str, str]]


def _main_unplanned_cause(day_events: pd.DataFrame) -> tuple[str | None, float | None, pd.DataFrame]:
    if day_events.empty:
        return None, None, day_events
    by_cause = day_events.groupby("downtime_reason")["downtime_minutes"].sum()
    cause = by_cause.idxmax()
    return cause, int(by_cause.max()), day_events[day_events["downtime_reason"] == cause]


def investigation_area(
    metric: str, day_production: pd.DataFrame, day_unplanned: pd.DataFrame
) -> InvestigationArea:
    if metric == SCRAP:
        by_product = day_production.groupby("product")[["scrap_quantity", "production_quantity"]].sum()
        by_product = by_product[by_product["production_quantity"] > 0]
        rates = by_product["scrap_quantity"] / by_product["production_quantity"]
        product = rates.idxmax()
        shifts = sorted(day_production.loc[day_production["product"] == product, "shift"].unique())
        return InvestigationArea(product, float(rates.max()), [int(s) for s in shifts])

    cause, minutes, cause_events = _main_unplanned_cause(day_unplanned)

    if metric == DOWNTIME:
        shift = cause_events.groupby("shift")["downtime_minutes"].sum().idxmax() if cause else None
        return InvestigationArea(cause, minutes, [int(shift)] if shift is not None else [])

    if metric == PROD:
        lowest = day_production.groupby("shift")["production_quantity"].sum().idxmin()
        return InvestigationArea(cause, minutes, [int(lowest)])

    raise ValueError(f"Unknown metric '{metric}'.")


def _line_rate(daily: pd.DataFrame, evaluation: Evaluation, day: date) -> float | None:
    production = calculate_baseline(daily, evaluation.line, PROD, day)
    downtime = calculate_baseline(daily, evaluation.line, DOWNTIME, day)
    if production.mean is None or downtime.mean is None:
        return None
    return line_rate(production.mean, downtime.mean)


def build_alerts(
    daily: pd.DataFrame,
    detection: DetectionResult,
    production: pd.DataFrame,
    unplanned_events: pd.DataFrame,
) -> list[Alert]:
    day = detection.evaluated_day
    alerts = []
    for evaluation in detection.deviations:
        rate = _line_rate(daily, evaluation, day)
        today = daily[(daily["line"] == evaluation.line) & (daily["date"] == day.isoformat())].iloc[0]
        days, cumulative = recurrence(daily, evaluation, rate)
        on_day = lambda df: df[(df["line"] == evaluation.line) & (df["date"] == day.isoformat())]
        baseline = evaluation.baseline

        alerts.append(
            Alert(
                rank=0,
                line=evaluation.line,
                metric=evaluation.metric,
                evaluated_day=day,
                value=evaluation.value,
                baseline_mean=baseline.mean,
                baseline_std=baseline.std,
                sample_size=baseline.sample_size,
                baseline_first_day=baseline.first_day,
                baseline_last_day=baseline.last_day,
                z=evaluation.z,
                percent_deviation=evaluation.percent_deviation,
                daily_impact=daily_impact(evaluation.metric, today, baseline.mean, rate),
                cumulative_impact=cumulative,
                frequency=len(days),
                recurrence_days=days,
                priority_score=cumulative * len(days),
                line_rate=rate,
                investigation=investigation_area(
                    evaluation.metric, on_day(production), on_day(unplanned_events)
                ),
            )
        )

    alerts.sort(key=lambda alert: alert.priority_score, reverse=True)
    for rank, alert in enumerate(alerts, start=1):
        alert.rank = rank
    return alerts


def run_alerts(conn: sqlite3.Connection, master_dir: Path) -> AlertReport:
    """Alerts always use all stored data; the dashboard may filter them by line (REQ-014)."""
    planned_reasons = load_master_lists(master_dir).planned_reasons
    production = production_repository.read_all(conn)
    events = downtime_repository.read_linked_events(conn)
    unplanned = events[~events["downtime_reason"].isin(planned_reasons)]

    daily = daily_line_metrics(production, events, planned_reasons)
    detection = detect_deviations(daily)
    return AlertReport(
        evaluated_day=detection.evaluated_day,
        alerts=build_alerts(daily, detection, production, unplanned),
        not_evaluated=detection.not_evaluated,
    )
