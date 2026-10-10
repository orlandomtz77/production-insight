"""Coverage: expected shifts vs. shifts with data (REQ-005).

Working calendar: Monday to Saturday are expected, except planned stops (ADR-005).
Sunday is only worked as overtime and never counts as missing.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.transformation.validation_common import VALID_SHIFTS, ShiftKey

SUNDAY = 6  # date.weekday()


@dataclass
class Coverage:
    period_start: date
    period_end: date
    expected_shifts: int
    covered_shifts: int
    missing_shifts: list[ShiftKey]
    overtime_shifts: list[ShiftKey]  # shifts with data that were not expected (Sunday or planned stop)
    planned_stop_shifts: int

    @property
    def coverage_percent(self) -> float:
        return 100.0 * self.covered_shifts / self.expected_shifts if self.expected_shifts else 0.0


def expected_shifts(start: date, end: date, lines) -> set[ShiftKey]:
    """Every Monday–Saturday date in [start, end] × every line × every shift."""
    return {
        (day.date().isoformat(), line, shift)
        for day in pd.date_range(start, end, freq="D")
        if day.weekday() != SUNDAY
        for line in lines
        for shift in VALID_SHIFTS
    }


def calculate_coverage(
    worked_shifts: set[ShiftKey], lines, planned_stops: set[ShiftKey] = frozenset()
) -> Coverage | None:
    """Compare shifts with production data against the working calendar.

    The period goes from the earliest to the latest date with data. Return None without data.
    """
    if not worked_shifts:
        return None

    dates = sorted(date.fromisoformat(day) for day, _, _ in worked_shifts)
    period_start, period_end = dates[0], dates[-1]
    working_calendar = expected_shifts(period_start, period_end, lines)
    planned = working_calendar & set(planned_stops)
    expected = working_calendar - planned

    return Coverage(
        period_start=period_start,
        period_end=period_end,
        expected_shifts=len(expected),
        covered_shifts=len(expected & worked_shifts),
        missing_shifts=sorted(expected - worked_shifts),
        overtime_shifts=sorted(worked_shifts - expected),
        planned_stop_shifts=len(planned),
    )
