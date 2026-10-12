"""Review periods: day, week or month (REQ-016)."""

from dataclasses import dataclass
from datetime import date, timedelta

SUNDAY = 6
GRAINS = ("day", "week", "month")
TREND_GRAIN = {"day": None, "week": "day", "month": "week"}  # one level finer than the period


@dataclass(frozen=True)
class ReviewPeriod:
    grain: str
    start: date
    end: date


def _month_end(day: date) -> date:
    first_next = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first_next - timedelta(days=1)


def _period_of(day: date, grain: str) -> ReviewPeriod:
    if grain == "day":
        return ReviewPeriod("day", day, day)
    if grain == "week":
        monday = day - timedelta(days=day.weekday())
        return ReviewPeriod("week", monday, monday + timedelta(days=6))
    if grain == "month":
        return ReviewPeriod("month", day.replace(day=1), _month_end(day))
    raise ValueError(f"Unknown grain '{grain}'; expected one of {GRAINS}.")


def available_periods(dates, grain: str) -> list[ReviewPeriod]:
    """Periods that contain data, newest first. Days are Monday–Saturday only (REQ-015)."""
    days = set(dates)
    if grain == "day":
        days = {d for d in days if d.weekday() != SUNDAY}
    return sorted({_period_of(d, grain) for d in days}, key=lambda p: p.start, reverse=True)


def trend_grain(grain: str) -> str | None:
    """Grain for trend charts inside a period; None for a single day (one point)."""
    return TREND_GRAIN[grain]
