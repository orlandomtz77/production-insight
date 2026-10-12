"""Detect deviations on the evaluated day (REQ-011).

A deviation is a value more than ALERT_THRESHOLD standard deviations away from
the line's baseline, in the unfavorable direction.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from src.anomaly_detection.baselines import METRICS, SUNDAY, Baseline, calculate_baseline
from src.anomaly_detection.daily_metrics import daily_line_metrics
from src.database import downtime_repository, production_repository
from src.ingestion.master_data import load_master_lists

ALERT_THRESHOLD = 2.0  # standard deviations; to be reviewed with real data (REQ-011)


@dataclass
class Evaluation:
    line: str
    metric: str
    value: float
    baseline: Baseline
    z: float
    percent_deviation: float
    shifts_worked: int
    direction: int

    @property
    def sample_size(self) -> int:
        return self.baseline.sample_size

    @property
    def is_deviation(self) -> bool:
        return self.direction * self.z > ALERT_THRESHOLD


@dataclass
class DetectionResult:
    evaluated_day: date | None
    evaluations: dict[tuple[str, str], Evaluation] = field(default_factory=dict)
    not_evaluated: list[tuple[str, str, str]] = field(default_factory=list)  # line, metric, reason

    @property
    def deviations(self) -> list[Evaluation]:
        return [e for e in self.evaluations.values() if e.is_deviation]


def evaluated_day(daily: pd.DataFrame) -> date | None:
    """Last Monday–Saturday date with data. Sunday overtime is not evaluated."""
    dates = pd.to_datetime(daily["date"])
    working = dates[dates.dt.weekday != SUNDAY]
    return working.max().date() if not working.empty else None


def detect_deviations(daily: pd.DataFrame) -> DetectionResult:
    day = evaluated_day(daily)
    result = DetectionResult(day)
    if day is None:
        return result

    metrics = [metric for metric in METRICS if metric.name in daily.columns]
    for line in sorted(daily["line"].unique()):
        today = daily[(daily["line"] == line) & (daily["date"] == day.isoformat())]
        for metric in metrics:
            if today.empty or pd.isna(today[metric.name].iloc[0]):
                result.not_evaluated.append((line, metric.name, "no_production"))
                continue
            baseline = calculate_baseline(daily, line, metric.name, day)
            if baseline.status != "ok":
                result.not_evaluated.append((line, metric.name, baseline.status))
                continue
            value = float(today[metric.name].iloc[0])
            result.evaluations[(line, metric.name)] = Evaluation(
                line=line,
                metric=metric.name,
                value=value,
                baseline=baseline,
                z=(value - baseline.mean) / baseline.std,
                percent_deviation=(value - baseline.mean) / baseline.mean * 100,
                shifts_worked=int(today["shifts_worked"].iloc[0]),
                direction=metric.direction,
            )
    return result


def run_detection(conn: sqlite3.Connection, master_dir: Path) -> DetectionResult:
    """Detection always uses all stored data (filters do not apply, REQ-014)."""
    planned_reasons = load_master_lists(master_dir).planned_reasons
    daily = daily_line_metrics(
        production_repository.read_all(conn),
        downtime_repository.read_linked_events(conn),
        planned_reasons,
    )
    return detect_deviations(daily)
