"""Unit tests for coverage calculation (REQ-005). No database needed."""

from datetime import date

from src.analytics.coverage import calculate_coverage, expected_shifts


def test_expected_shifts_are_monday_to_saturday_for_every_line_and_shift():
    # 2026-09-07 is Monday, 2026-09-13 is Sunday.
    shifts = expected_shifts(date(2026, 9, 7), date(2026, 9, 13), ["L1", "L2"])

    assert len(shifts) == 6 * 2 * 3
    assert ("2026-09-12", "L2", 3) in shifts  # Saturday
    assert not any(day == "2026-09-13" for day, _, _ in shifts)  # Sunday


def test_coverage_reports_missing_and_overtime_shifts():
    lines = ["L1"]
    worked = {
        ("2026-09-07", "L1", 1),
        ("2026-09-07", "L1", 2),  # shift 3 missing on Monday
        ("2026-09-08", "L1", 1),
        ("2026-09-08", "L1", 2),
        ("2026-09-08", "L1", 3),
        ("2026-09-13", "L1", 1),  # Sunday overtime
    }

    coverage = calculate_coverage(worked, lines)

    assert coverage.period_start == date(2026, 9, 7)
    assert coverage.period_end == date(2026, 9, 13)
    assert coverage.expected_shifts == 6 * 3  # Mon–Sat in the period
    assert coverage.covered_shifts == 5
    assert ("2026-09-07", "L1", 3) in coverage.missing_shifts
    assert coverage.overtime_shifts == [("2026-09-13", "L1", 1)]


def test_sunday_without_data_is_never_missing():
    worked = {("2026-09-12", "L1", s) for s in (1, 2, 3)} | {("2026-09-14", "L1", s) for s in (1, 2, 3)}

    coverage = calculate_coverage(worked, ["L1"])

    assert coverage.missing_shifts == []
    assert coverage.coverage_percent == 100.0


def test_no_data_returns_none():
    assert calculate_coverage(set(), ["L1"]) is None


def test_planned_stop_is_not_expected():
    worked = {("2026-09-07", "L1", s) for s in (1, 2)}  # shift 3 is a planned stop

    coverage = calculate_coverage(worked, ["L1"], planned_stops={("2026-09-07", "L1", 3)})

    assert coverage.missing_shifts == []
    assert coverage.expected_shifts == 2
    assert coverage.planned_stop_shifts == 1


def test_planned_stop_with_data_is_listed_as_extra_shift():
    worked = {("2026-09-07", "L1", s) for s in (1, 2, 3)}

    coverage = calculate_coverage(worked, ["L1"], planned_stops={("2026-09-07", "L1", 3)})

    assert coverage.overtime_shifts == [("2026-09-07", "L1", 3)]
    assert coverage.covered_shifts == 2
