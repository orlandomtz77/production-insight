"""Unit tests for review periods (REQ-016)."""

from datetime import date

import pytest

from src.analytics.periods import ReviewPeriod, available_periods, trend_grain

DATES = [date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 27), date(2026, 9, 28), date(2026, 9, 30)]


def test_days_are_monday_to_saturday_newest_first():
    periods = available_periods(DATES, "day")

    assert [p.start for p in periods] == [
        date(2026, 9, 30), date(2026, 9, 28), date(2026, 9, 1), date(2026, 8, 31)
    ]  # Sunday 27 is not offered
    assert periods[0] == ReviewPeriod("day", date(2026, 9, 30), date(2026, 9, 30))


def test_weeks_go_from_monday_to_sunday():
    periods = available_periods(DATES, "week")

    assert [(p.start, p.end) for p in periods] == [
        (date(2026, 9, 28), date(2026, 10, 4)),
        (date(2026, 9, 21), date(2026, 9, 27)),
        (date(2026, 8, 31), date(2026, 9, 6)),
    ]


def test_months_cover_the_whole_month():
    periods = available_periods(DATES, "month")

    assert [(p.start, p.end) for p in periods] == [
        (date(2026, 9, 1), date(2026, 9, 30)),
        (date(2026, 8, 1), date(2026, 8, 31)),
    ]


def test_no_dates_no_periods():
    assert available_periods([], "week") == []


@pytest.mark.parametrize(("grain", "expected"), [("day", None), ("week", "day"), ("month", "week")])
def test_trend_grain(grain, expected):
    assert trend_grain(grain) == expected
