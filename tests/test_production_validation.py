"""Unit tests for production row validation (REQ-001)."""

from datetime import date

import pandas as pd
import pytest

from src.ingestion.master_data import MasterLists
from src.transformation.production_validation import validate_production

TODAY = date(2026, 10, 7)
MASTER = MasterLists(
    lines=frozenset({"L1", "L2"}),
    products=frozenset({"Producto A", "Producto B"}),
    downtime_reasons=frozenset({"Otro"}),
)
VALID_ROW = {
    "date": "2026-09-01",
    "line": "L1",
    "shift": "1",
    "product": "Producto A",
    "production_quantity": "1000",
    "scrap_quantity": "30",
}


def validate(*rows):
    return validate_production(pd.DataFrame(rows, dtype=str), MASTER, TODAY)


def error_codes(result):
    return {error.code for error in result.errors}


def test_valid_row_is_accepted_and_typed():
    result = validate(VALID_ROW)

    assert result.errors == []
    assert len(result.valid_rows) == 1
    row = result.valid_rows.iloc[0]
    assert row["shift"] == 1
    assert row["production_quantity"] == 1000
    assert result.shifts_accepted == {("2026-09-01", "L1", 1)}


@pytest.mark.parametrize(
    ("column", "value", "code"),
    [
        ("date", "", "missing_value"),
        ("date", "2026-09-31", "invalid_date"),
        ("date", "01/09/2026", "invalid_date"),
        ("date", "2026-10-08", "future_date"),
        ("line", "L9", "unknown_line"),
        ("product", "Producto Z", "unknown_product"),
        ("shift", "4", "invalid_shift"),
        ("shift", "uno", "invalid_shift"),
        ("production_quantity", "-5", "negative_value"),
        ("production_quantity", "10.5", "not_integer"),
        ("scrap_quantity", "abc", "not_integer"),
        ("scrap_quantity", "1001", "scrap_exceeds_production"),
    ],
)
def test_invalid_value_is_rejected_with_its_code(column, value, code):
    result = validate({**VALID_ROW, column: value})

    assert code in error_codes(result)
    assert result.valid_rows.empty
    error = next(e for e in result.errors if e.code == code)
    assert error.row == 2  # Excel row: header is row 1
    assert error.column == column
    assert error.value == value
    assert error.reason  # message for the user


def test_values_are_trimmed():
    result = validate({**VALID_ROW, "line": "  L1 ", "product": "Producto A "})

    assert result.errors == []
    assert result.valid_rows.iloc[0]["line"] == "L1"


def test_today_is_not_a_future_date():
    result = validate({**VALID_ROW, "date": "2026-10-07"})

    assert result.errors == []


def test_production_zero_is_valid():
    result = validate({**VALID_ROW, "production_quantity": "0", "scrap_quantity": "0"})

    assert result.errors == []


def test_duplicate_rows_are_all_rejected():
    result = validate(VALID_ROW, VALID_ROW)

    duplicates = [e for e in result.errors if e.code == "duplicate_row"]
    assert [e.row for e in duplicates] == [2, 3]
    assert result.valid_rows.empty


def test_valid_row_in_shift_with_invalid_row_is_rejected():
    invalid = {**VALID_ROW, "production_quantity": "-1"}
    same_shift_other_product = {**VALID_ROW, "product": "Producto B"}
    other_shift = {**VALID_ROW, "shift": "2"}

    result = validate(invalid, same_shift_other_product, other_shift)

    rejected = next(e for e in result.errors if e.row == 3)
    assert rejected.code == "shift_rejected"
    assert result.shifts_rejected == {("2026-09-01", "L1", 1)}
    assert result.shifts_accepted == {("2026-09-01", "L1", 2)}
    assert len(result.valid_rows) == 1


def test_row_with_several_errors_reports_all_of_them():
    result = validate({**VALID_ROW, "line": "L9", "production_quantity": "-5"})

    assert {"unknown_line", "negative_value"} <= error_codes(result)
    assert result.rows_rejected == 1
