"""Unit tests for KPI calculations (REQ-007, REQ-008, REQ-009).

Small datasets calculated by hand. No database needed.
"""

from datetime import date

import pandas as pd
import pytest

from src.analytics.kpis import (
    KpiFilters,
    apply_filters,
    downtime_kpis,
    downtime_trend,
    period_start,
    production_kpis,
    quality_kpis,
    scrap_trend,
)

PLANNED = frozenset({"Mantenimiento", "Paro programado"})


def production(*rows):
    return pd.DataFrame(
        rows, columns=["date", "line", "shift", "product", "production_quantity", "scrap_quantity"]
    )


def downtime(*rows):
    return pd.DataFrame(
        rows, columns=["date", "line", "shift", "product", "downtime_minutes", "downtime_reason"]
    )


# --- REQ-007 -----------------------------------------------------------------

def test_average_production_counts_a_shift_with_two_products_once():
    df = production(
        ("2026-09-01", "L1", 1, "Producto A", 600, 0),
        ("2026-09-01", "L1", 1, "Producto B", 400, 0),  # same shift, changeover
        ("2026-09-01", "L1", 2, "Producto A", 1000, 0),
    )

    kpis = production_kpis(df)

    assert kpis.total == 2000
    assert kpis.shifts_worked == 2
    assert kpis.average_per_shift == 1000


def test_production_by_line_shows_shifts_worked():
    df = production(
        ("2026-09-01", "L1", 1, "Producto A", 1000, 0),
        ("2026-09-01", "L1", 2, "Producto A", 1000, 0),
        ("2026-09-01", "L2", 1, "Producto B", 500, 0),
    )

    by_line = production_kpis(df).by_line.set_index("line")

    assert by_line.loc["L1", "production"] == 2000
    assert by_line.loc["L1", "shifts_worked"] == 2
    assert by_line.loc["L2", "shifts_worked"] == 1


def test_groups_are_sorted_highest_first_except_shift():
    df = production(
        ("2026-09-01", "L1", 3, "Producto A", 100, 0),
        ("2026-09-01", "L2", 1, "Producto B", 900, 0),
    )

    kpis = production_kpis(df)

    assert kpis.by_line["line"].tolist() == ["L2", "L1"]
    assert kpis.by_shift["shift"].tolist() == [1, 3]  # natural order


def test_empty_production_has_no_data():
    kpis = production_kpis(production())

    assert kpis.total == 0
    assert kpis.average_per_shift is None


# --- REQ-008 -----------------------------------------------------------------

def test_scrap_rate_is_ratio_of_totals_not_average_of_rates():
    df = production(
        ("2026-09-01", "L1", 1, "Producto A", 1000, 10),  # 1.0%
        ("2026-09-01", "L1", 2, "Producto A", 10, 5),     # 50.0%
    )

    kpis = quality_kpis(df)

    assert kpis.scrap_rate == pytest.approx(15 / 1010)  # 1.5%, not 25.5%


def test_zero_production_does_not_fail_and_group_rate_is_none():
    df = production(
        ("2026-09-01", "L1", 1, "Producto A", 0, 0),
        ("2026-09-01", "L2", 1, "Producto B", 100, 5),
    )

    kpis = quality_kpis(df)

    by_line = kpis.by_line.set_index("line")
    assert pd.isna(by_line.loc["L1", "scrap_rate"])
    assert by_line.loc["L2", "scrap_rate"] == pytest.approx(0.05)
    assert kpis.scrap_rate == pytest.approx(0.05)


def test_empty_quality_rate_is_none():
    assert quality_kpis(production()).scrap_rate is None


def test_scrap_by_shift_and_week_heatmap():
    df = production(
        ("2026-09-07", "L1", 1, "Producto A", 1000, 30),  # Monday, week of Sep 7
        ("2026-09-08", "L1", 1, "Producto A", 1000, 10),
        ("2026-09-14", "L1", 1, "Producto A", 1000, 90),  # week of Sep 14
        ("2026-09-14", "L1", 2, "Producto A", 1000, 20),
    )

    heatmap = quality_kpis(df).by_shift_week

    assert heatmap.loc[1, date(2026, 9, 7)] == pytest.approx(40 / 2000)
    assert heatmap.loc[1, date(2026, 9, 14)] == pytest.approx(0.09)
    assert heatmap.loc[2, date(2026, 9, 14)] == pytest.approx(0.02)
    assert pd.isna(heatmap.loc[2, date(2026, 9, 7)])  # shift 2 did not run that week


# --- REQ-009 -----------------------------------------------------------------

def test_average_downtime_counts_shifts_without_downtime_as_zero():
    prod = production(*[("2026-09-01", "L1", s, "Producto A", 1000, 0) for s in (1, 2, 3)],
                      ("2026-09-02", "L1", 1, "Producto A", 1000, 0))
    events = downtime(
        ("2026-09-01", "L1", 1, "Producto A", 60, "Falla de máquina"),
        ("2026-09-02", "L1", 1, "Producto A", 20, "Otro"),
    )

    kpis = downtime_kpis(prod, events, PLANNED)

    assert kpis.average_unplanned_per_shift == 20  # 80 / 4, not 40


def test_planned_and_unplanned_downtime_are_separated():
    prod = production(("2026-09-01", "L1", 1, "Producto A", 1000, 0))
    events = downtime(
        ("2026-09-01", "L1", 1, "Producto A", 30, "Falla de máquina"),
        ("2026-09-01", "L1", 1, "Producto A", 60, "Mantenimiento"),
    )

    kpis = downtime_kpis(prod, events, PLANNED)

    assert kpis.unplanned_total == 30
    assert kpis.planned_total == 60
    assert kpis.total == 90
    assert kpis.by_line.set_index("line").loc["L1", "downtime"] == 30  # unplanned by default


def test_downtime_by_cause_sorted_with_events_percent_and_planned_flag():
    prod = production(("2026-09-01", "L1", 1, "Producto A", 1000, 0))
    events = downtime(
        ("2026-09-01", "L1", 1, "Producto A", 10, "Otro"),
        ("2026-09-01", "L1", 1, "Producto A", 10, "Otro"),
        ("2026-09-01", "L1", 1, "Producto A", 60, "Mantenimiento"),
    )

    by_cause = downtime_kpis(prod, events, PLANNED).by_cause

    assert by_cause["downtime_reason"].tolist() == ["Mantenimiento", "Otro"]
    otro = by_cause.set_index("downtime_reason").loc["Otro"]
    assert otro["minutes"] == 20
    assert otro["events"] == 2
    assert otro["percent"] == pytest.approx(0.25)
    assert bool(otro["planned"]) is False


def test_empty_downtime():
    kpis = downtime_kpis(production(), downtime(), PLANNED)

    assert kpis.total == 0
    assert kpis.average_unplanned_per_shift is None


# --- Filters and time grain ----------------------------------------------------

def test_filters_by_period_line_product_and_shift():
    df = production(
        ("2026-09-01", "L1", 1, "Producto A", 1, 0),
        ("2026-09-02", "L1", 1, "Producto A", 1, 0),
        ("2026-09-02", "L2", 1, "Producto A", 1, 0),
        ("2026-09-02", "L1", 2, "Producto B", 1, 0),
    )
    filters = KpiFilters(
        start=date(2026, 9, 2), end=date(2026, 9, 2), lines=["L1"], products=["Producto A"], shifts=[1]
    )

    assert len(apply_filters(df, filters)) == 1
    assert len(apply_filters(df, KpiFilters())) == 4  # no filters: all data


@pytest.mark.parametrize(
    ("grain", "expected"),
    [("day", date(2026, 9, 10)), ("week", date(2026, 9, 7)), ("month", date(2026, 9, 1))],
)
def test_period_start(grain, expected):
    assert period_start(pd.Series(["2026-09-10"]), grain).iloc[0] == expected


def test_scrap_trend_recalculates_ratio_of_totals_per_period():
    df = production(
        ("2026-09-07", "L1", 1, "Producto A", 1000, 10),
        ("2026-09-08", "L1", 1, "Producto A", 10, 5),
    )

    trend = scrap_trend(df, "week")

    assert len(trend) == 1
    assert trend.iloc[0]["scrap_rate"] == pytest.approx(15 / 1010)


def test_downtime_trend_is_unplanned_minutes_per_shift_worked():
    prod = production(("2026-09-07", "L1", 1, "Producto A", 1, 0), ("2026-09-08", "L1", 1, "Producto A", 1, 0))
    events = downtime(
        ("2026-09-07", "L1", 1, "Producto A", 40, "Falla de máquina"),
        ("2026-09-07", "L1", 1, "Producto A", 100, "Mantenimiento"),  # planned: excluded
    )

    trend = downtime_trend(prod, events, PLANNED, "week")

    assert trend.iloc[0]["downtime_per_shift"] == 20  # 40 / 2 shifts worked
