"""Validation building blocks shared by production (REQ-001) and downtime (REQ-002).

A shift (date + line + shift) is accepted only if all its rows are valid (ADR-002).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pandas as pd

from src.ingestion.master_data import MasterLists

FIRST_DATA_ROW = 2  # row numbers match Excel: the header is row 1
VALID_SHIFTS = (1, 2, 3)
NO_COLUMN = "—"  # errors that concern the whole row

ShiftKey = tuple[str, str, int]


@dataclass(frozen=True)
class RowError:
    row: int
    column: str
    value: str
    code: str
    reason: str


@dataclass
class ValidationResult:
    valid_rows: pd.DataFrame
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    shifts_accepted: set[ShiftKey] = field(default_factory=set)
    shifts_rejected: set[ShiftKey] = field(default_factory=set)

    @property
    def rows_rejected(self) -> int:
        return len({error.row for error in self.errors})


def excel_row(index: int) -> int:
    return index + FIRST_DATA_ROW


def parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def validate_common_fields(row: dict[str, str], master: MasterLists, today: date):
    """Check required values, date, line, shift and product.

    Return (errors as (column, code, reason), parsed values).
    """
    errors = []
    parsed = {}

    for column, value in row.items():
        if value == "":
            errors.append((column, "missing_value", "Campo obligatorio vacío."))

    if row["date"]:
        try:
            parsed_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except ValueError:
            errors.append(("date", "invalid_date", "Fecha inválida; el formato es AAAA-MM-DD."))
        else:
            if parsed_date > today:
                errors.append(("date", "future_date", "La fecha es posterior a hoy."))
            else:
                parsed["date"] = parsed_date.isoformat()

    if row["line"]:
        if row["line"] in master.lines:
            parsed["line"] = row["line"]
        else:
            errors.append(("line", "unknown_line", "La línea no está en la lista de líneas."))

    if row["shift"]:
        shift = parse_int(row["shift"])
        if shift in VALID_SHIFTS:
            parsed["shift"] = shift
        else:
            errors.append(("shift", "invalid_shift", "Turno inválido; debe ser 1, 2 o 3."))

    if row["product"]:
        if row["product"] in master.products:
            parsed["product"] = row["product"]
        else:
            errors.append(
                ("product", "unknown_product", "El producto no está en la lista de productos.")
            )

    return errors, parsed


class RowChecks:
    """Collect row errors, then apply the shift rule and build the result."""

    def __init__(
        self,
        df: pd.DataFrame,
        columns: list[str],
        validate_row: Callable[[dict[str, str]], tuple[list, dict]],
    ):
        self.columns = columns
        self.rows = [
            {column: str(value).strip() for column, value in record.items()}
            for record in df[columns].to_dict("records")
        ]
        self.errors: list[RowError] = []
        self.invalid: set[int] = set()
        self.parsed: dict[int, dict] = {}
        self.shift_keys: dict[int, ShiftKey] = {}

        for index, row in enumerate(self.rows):
            row_errors, parsed = validate_row(row)
            for column, code, reason in row_errors:
                self.add_error(index, column, code, reason)
            self.parsed[index] = parsed
            # Rows with an invalid date, line or shift cannot be assigned to a shift.
            if {"date", "line", "shift"} <= parsed.keys():
                self.shift_keys[index] = (parsed["date"], parsed["line"], parsed["shift"])

    def add_error(self, index: int, column: str, code: str, reason: str) -> None:
        value = self.rows[index].get(column, "")
        self.errors.append(RowError(excel_row(index), column, value, code, reason))
        self.invalid.add(index)

    def finalize(self, int_columns: list[str]) -> ValidationResult:
        shifts_rejected = {self.shift_keys[i] for i in self.invalid if i in self.shift_keys}

        valid_indexes = []
        for index in range(len(self.rows)):
            if index in self.invalid:
                continue
            key = self.shift_keys[index]
            if key in shifts_rejected:
                day, line, shift = key
                self.add_error(
                    index, NO_COLUMN, "shift_rejected",
                    f"Rechazada: el turno {day} / {line} / {shift} tiene filas inválidas.",
                )
            else:
                valid_indexes.append(index)

        valid_rows = pd.DataFrame(
            [{**self.rows[i], **self.parsed[i]} for i in valid_indexes], columns=self.columns
        )
        if not valid_rows.empty:
            valid_rows = valid_rows.astype({column: int for column in int_columns})

        return ValidationResult(
            valid_rows=valid_rows,
            errors=sorted(self.errors, key=lambda error: error.row),
            shifts_accepted={self.shift_keys[i] for i in valid_indexes},
            shifts_rejected=shifts_rejected,
        )
