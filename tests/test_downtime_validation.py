"""Unit tests for downtime row validation (REQ-002)."""

from datetime import date

import pandas as pd
import pytest

from src.ingestion.master_data import MasterLists
from src.transformation.downtime_validation import validate_downtime

TODAY = date(2026, 10, 7)
MASTER = MasterLists(
    lines=frozenset({"L1", "L2"}),
    products=frozenset({"Producto A", "Producto B"}),
    downtime_reasons=frozenset({"Falla de máquina", "Otro"}),
)
PRODUCTION_KEYS = {
    ("2026-09-01", "L1", 1, "Producto A"),
    ("2026-09-01", "L1", 2, "Producto A"),
}
VALID_ROW = {
    "date": "2026-09-01",
    "line": "L1",
    "shift": "1",
    "product": "Producto A",
    "downtime_minutes": "30",
    "downtime_reason": "Falla de máquina",
}


def validate(*rows):
    return validate_downtime(pd.DataFrame(rows, dtype=str), MASTER, TODAY, PRODUCTION_KEYS)


def error_codes(result):
    return {error.code for error in result.errors}


def test_valid_row_is_accepted_and_typed():
    result = validate(VALID_ROW)

    assert result.errors == []
    assert result.valid_rows.iloc[0]["downtime_minutes"] == 30
    assert result.shifts_accepted == {("2026-09-01", "L1", 1)}


@pytest.mark.parametrize(
    ("column", "value", "code"),
    [
        ("downtime_minutes", "0", "not_positive"),
        ("downtime_minutes", "481", "exceeds_shift_length"),
        ("downtime_minutes", "1.5", "not_integer"),
        ("downtime_minutes", "", "missing_value"),
        ("downtime_reason", "Falla", "unknown_reason"),
        ("line", "L9", "unknown_line"),
        ("date", "2026-10-08", "future_date"),
    ],
)
def test_invalid_value_is_rejected_with_its_code(column, value, code):
    result = validate({**VALID_ROW, column: value})

    assert code in error_codes(result)
    assert result.valid_rows.empty


def test_event_without_production_record_is_orphan():
    result = validate({**VALID_ROW, "product": "Producto B"})

    assert error_codes(result) == {"orphan_event"}


def test_shift_total_over_480_rejects_all_rows_of_shift():
    result = validate(
        {**VALID_ROW, "downtime_minutes": "300"},
        {**VALID_ROW, "downtime_minutes": "210"},
    )

    exceeded = [e for e in result.errors if e.code == "shift_total_exceeded"]
    assert [e.row for e in exceeded] == [2, 3]
    assert "510" in exceeded[0].reason
    assert result.valid_rows.empty


def test_shift_total_of_exactly_480_is_valid():
    result = validate(
        {**VALID_ROW, "downtime_minutes": "300"},
        {**VALID_ROW, "downtime_minutes": "180"},
    )

    assert result.errors == []


def test_identical_rows_are_stored_with_warning():
    result = validate(VALID_ROW, VALID_ROW)

    assert result.errors == []
    assert len(result.valid_rows) == 2
    assert len(result.warnings) == 1
    assert "2" in result.warnings[0] and "3" in result.warnings[0]


def test_valid_row_in_shift_with_invalid_row_is_rejected():
    result = validate(
        {**VALID_ROW, "downtime_reason": "Falla"},
        VALID_ROW,
        {**VALID_ROW, "shift": "2"},
    )

    assert next(e for e in result.errors if e.row == 3).code == "shift_rejected"
    assert result.shifts_accepted == {("2026-09-01", "L1", 2)}
