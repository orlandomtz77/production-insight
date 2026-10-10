"""KPIs: production (REQ-007), quality (REQ-008) and downtime (REQ-009).

Rules (docs/requirements.md, KPI Common Rules):
- Rates are always a ratio of totals, never an average of rates.
- A shift worked is a distinct date + line + shift with production.
- Orphan downtime events are excluded and counted.
- Planned downtime is shown separately; grouped downtime is unplanned (ADR-005).
"""

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from src.database import downtime_repository, production_repository
from src.ingestion.master_data import load_master_lists

SHIFT_KEY = ["date", "line", "shift"]
TIME_GRAINS = ("day", "week", "month")


@dataclass
class KpiFilters:
    """None means "all"."""

    start: date | None = None
    end: date | None = None
    lines: list[str] | None = None
    products: list[str] | None = None
    shifts: list[int] | None = None


def apply_filters(df: pd.DataFrame, filters: KpiFilters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if filters.start:
        mask &= df["date"] >= filters.start.isoformat()  # ISO dates compare as text
    if filters.end:
        mask &= df["date"] <= filters.end.isoformat()
    if filters.lines is not None:
        mask &= df["line"].isin(filters.lines)
    if filters.products is not None:
        mask &= df["product"].isin(filters.products)
    if filters.shifts is not None:
        mask &= df["shift"].isin(filters.shifts)
    return df[mask]


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _rate_column(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Element-wise ratio; NaN where the denominator is 0 (shown as N/A)."""
    return numerator / denominator.where(denominator != 0)


def _sort(df: pd.DataFrame, column: str, by: str) -> pd.DataFrame:
    """Highest first, except shift, which keeps its natural order (1, 2, 3)."""
    if column == "shift":
        return df.sort_values("shift").reset_index(drop=True)
    return df.sort_values(by, ascending=False, na_position="last").reset_index(drop=True)


def _shifts_worked(production: pd.DataFrame, column: str) -> pd.Series:
    return production.drop_duplicates([column, *SHIFT_KEY]).groupby(column).size()


# --- REQ-007 -----------------------------------------------------------------

@dataclass
class ProductionKpis:
    total: int
    shifts_worked: int
    average_per_shift: float | None
    by_line: pd.DataFrame
    by_product: pd.DataFrame
    by_shift: pd.DataFrame


def _production_by(production: pd.DataFrame, column: str) -> pd.DataFrame:
    grouped = production.groupby(column)["production_quantity"].sum().rename("production")
    df = pd.concat([grouped, _shifts_worked(production, column).rename("shifts_worked")], axis=1)
    return _sort(df.reset_index(), column, "production")


def production_kpis(production: pd.DataFrame) -> ProductionKpis:
    total = int(production["production_quantity"].sum())
    shifts_worked = len(production.drop_duplicates(SHIFT_KEY))
    return ProductionKpis(
        total=total,
        shifts_worked=shifts_worked,
        average_per_shift=_ratio(total, shifts_worked),
        by_line=_production_by(production, "line"),
        by_product=_production_by(production, "product"),
        by_shift=_production_by(production, "shift"),
    )


# --- REQ-008 -----------------------------------------------------------------

@dataclass
class QualityKpis:
    scrap_total: int
    production_total: int
    scrap_rate: float | None
    by_line: pd.DataFrame
    by_product: pd.DataFrame
    by_shift: pd.DataFrame
    by_shift_week: pd.DataFrame  # rows: shift; columns: week start (Monday); values: scrap rate


def _quality_by(production: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = (
        production.groupby(columns)[["production_quantity", "scrap_quantity"]]
        .sum()
        .rename(columns={"production_quantity": "production", "scrap_quantity": "scrap"})
        .reset_index()
    )
    df["scrap_rate"] = _rate_column(df["scrap"], df["production"])
    return df


def quality_kpis(production: pd.DataFrame) -> QualityKpis:
    scrap_total = int(production["scrap_quantity"].sum())
    production_total = int(production["production_quantity"].sum())

    with_week = production.assign(week=period_start(production["date"], "week"))
    by_shift_week = (
        _quality_by(with_week, ["shift", "week"])
        .pivot(index="shift", columns="week", values="scrap_rate")
        if not production.empty
        else pd.DataFrame()
    )

    return QualityKpis(
        scrap_total=scrap_total,
        production_total=production_total,
        scrap_rate=_ratio(scrap_total, production_total),
        by_line=_sort(_quality_by(production, ["line"]), "line", "scrap_rate"),
        by_product=_sort(_quality_by(production, ["product"]), "product", "scrap_rate"),
        by_shift=_sort(_quality_by(production, ["shift"]), "shift", "scrap_rate"),
        by_shift_week=by_shift_week,
    )


# --- REQ-009 -----------------------------------------------------------------

@dataclass
class DowntimeKpis:
    unplanned_total: int
    planned_total: int
    total: int
    shifts_worked: int
    average_unplanned_per_shift: float | None
    by_line: pd.DataFrame      # unplanned
    by_product: pd.DataFrame   # unplanned
    by_shift: pd.DataFrame     # unplanned
    by_cause: pd.DataFrame     # all reasons, with planned flag


def _split(events: pd.DataFrame, planned_reasons: frozenset[str]):
    planned = events["downtime_reason"].isin(planned_reasons)
    return events[~planned], events[planned]


def _downtime_by(unplanned: pd.DataFrame, column: str) -> pd.DataFrame:
    df = unplanned.groupby(column)["downtime_minutes"].sum().rename("downtime").reset_index()
    return _sort(df, column, "downtime")


def downtime_kpis(
    production: pd.DataFrame, events: pd.DataFrame, planned_reasons: frozenset[str]
) -> DowntimeKpis:
    unplanned, planned = _split(events, planned_reasons)
    unplanned_total = int(unplanned["downtime_minutes"].sum())
    planned_total = int(planned["downtime_minutes"].sum())
    shifts_worked = len(production.drop_duplicates(SHIFT_KEY))

    by_cause = (
        events.groupby("downtime_reason")["downtime_minutes"]
        .agg(minutes="sum", events="count")
        .reset_index()
    )
    total = unplanned_total + planned_total
    by_cause["percent"] = by_cause["minutes"] / total if total else float("nan")
    by_cause["planned"] = by_cause["downtime_reason"].isin(planned_reasons)
    by_cause = by_cause.sort_values("minutes", ascending=False).reset_index(drop=True)

    return DowntimeKpis(
        unplanned_total=unplanned_total,
        planned_total=planned_total,
        total=total,
        shifts_worked=shifts_worked,
        average_unplanned_per_shift=_ratio(unplanned_total, shifts_worked),
        by_line=_downtime_by(unplanned, "line"),
        by_product=_downtime_by(unplanned, "product"),
        by_shift=_downtime_by(unplanned, "shift"),
        by_cause=by_cause[["downtime_reason", "planned", "minutes", "events", "percent"]],
    )


# --- Time grain and trends ----------------------------------------------------

def period_start(dates: pd.Series, grain: str) -> pd.Series:
    """First day of the day / week (Monday) / month of each ISO date."""
    if grain not in TIME_GRAINS:
        raise ValueError(f"Unknown time grain '{grain}'; expected one of {TIME_GRAINS}.")
    parsed = pd.to_datetime(dates)
    if grain == "week":
        parsed = parsed - pd.to_timedelta(parsed.dt.weekday, unit="D")
    elif grain == "month":
        parsed = parsed.dt.to_period("M").dt.start_time
    return parsed.dt.date


def scrap_trend(production: pd.DataFrame, grain: str) -> pd.DataFrame:
    """Scrap rate per line and period (ratio of totals per period)."""
    with_period = production.assign(period=period_start(production["date"], grain))
    return _quality_by(with_period, ["period", "line"])


def downtime_trend(
    production: pd.DataFrame, events: pd.DataFrame, planned_reasons: frozenset[str], grain: str
) -> pd.DataFrame:
    """Unplanned downtime per shift worked, per line and period."""
    unplanned, _ = _split(events, planned_reasons)
    worked = production.drop_duplicates(SHIFT_KEY)
    shifts = (
        worked.assign(period=period_start(worked["date"], grain))
        .groupby(["period", "line"])
        .size()
        .rename("shifts_worked")
    )
    minutes = (
        unplanned.assign(period=period_start(unplanned["date"], grain))
        .groupby(["period", "line"])["downtime_minutes"]
        .sum()
        .rename("unplanned_minutes")
    )
    df = pd.concat([shifts, minutes], axis=1).fillna({"unplanned_minutes": 0}).reset_index()
    df["downtime_per_shift"] = _rate_column(df["unplanned_minutes"], df["shifts_worked"])
    return df


# --- Report -------------------------------------------------------------------

@dataclass
class KpiReport:
    production: ProductionKpis
    quality: QualityKpis
    downtime: DowntimeKpis
    orphans_excluded: int

    @property
    def has_data(self) -> bool:
        return self.production.shifts_worked > 0


def build_kpi_report(conn: sqlite3.Connection, master_dir: Path, filters: KpiFilters) -> KpiReport:
    """Raises MasterDataError if the master lists cannot be read."""
    planned_reasons = load_master_lists(master_dir).planned_reasons
    production = apply_filters(production_repository.read_all(conn), filters)
    events = apply_filters(downtime_repository.read_linked_events(conn), filters)
    orphans = apply_filters(downtime_repository.orphan_events(conn), filters)

    return KpiReport(
        production=production_kpis(production),
        quality=quality_kpis(production),
        downtime=downtime_kpis(production, events, planned_reasons),
        orphans_excluded=len(orphans),
    )
