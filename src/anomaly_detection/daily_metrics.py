"""Daily values per line used by detection (REQ-010).

Values are normalized per shift so that a missing shift does not look like a
drop in production or an improvement in downtime. Planned downtime is not a
loss: it reduces the time available for production (ADR-005).
"""

import pandas as pd

SHIFT_MINUTES = 480
DAY_LINE = ["date", "line"]


def daily_line_metrics(
    production: pd.DataFrame, events: pd.DataFrame, planned_reasons: frozenset[str]
) -> pd.DataFrame:
    """One row per date + line with production.

    Columns: shifts_worked, production, scrap, planned_minutes, unplanned_minutes,
    available_shifts, production_per_available_shift, scrap_rate,
    unplanned_downtime_per_shift.
    """
    days = production.groupby(DAY_LINE).agg(
        shifts_worked=("shift", "nunique"),
        production=("production_quantity", "sum"),
        scrap=("scrap_quantity", "sum"),
    )

    planned = events["downtime_reason"].isin(planned_reasons)
    planned_minutes = events[planned].groupby(DAY_LINE)["downtime_minutes"].sum()
    unplanned_minutes = events[~planned].groupby(DAY_LINE)["downtime_minutes"].sum()

    days = days.join(planned_minutes.rename("planned_minutes")).join(
        unplanned_minutes.rename("unplanned_minutes")
    )
    days = days.fillna({"planned_minutes": 0, "unplanned_minutes": 0})

    days["available_shifts"] = (
        days["shifts_worked"] * SHIFT_MINUTES - days["planned_minutes"]
    ) / SHIFT_MINUTES
    days["production_per_available_shift"] = days["production"] / days["available_shifts"]
    days["scrap_rate"] = days["scrap"] / days["production"].where(days["production"] != 0)
    days["unplanned_downtime_per_shift"] = days["unplanned_minutes"] / days["shifts_worked"]

    return days.reset_index()
