"""Row-level validation of production records (REQ-001).

Rules: docs/requirements.md, REQ-001 and Cross-Cutting Decisions.
A shift (date + line + shift) is accepted only if all its rows are valid (ADR-002).
"""

from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from src.ingestion.master_data import MasterLists

PRODUCTION_COLUMNS = [
    "date",
    "line",
    "shift",
    "product",
    "production_quantity",
    "scrap_quantity",
]
VALID_SHIFTS = (1, 2, 3)
FIRST_DATA_ROW = 2  # row numbers match Excel: the header is row 1

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
    shifts_accepted: set[ShiftKey] = field(default_factory=set)
    shifts_rejected: set[ShiftKey] = field(default_factory=set)

    @property
    def rows_rejected(self) -> int:
        return len({error.row for error in self.errors})


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _validate_row(row: dict[str, str], master: MasterLists, today: date):
    """Return (errors as (column, code, reason), parsed values) for one row."""
    errors = []
    parsed = {}

    for column in PRODUCTION_COLUMNS:
        if row[column] == "":
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

    if row["product"] and row["product"] not in master.products:
        errors.append(("product", "unknown_product", "El producto no está en la lista de productos."))

    if row["shift"]:
        shift = _parse_int(row["shift"])
        if shift in VALID_SHIFTS:
            parsed["shift"] = shift
        else:
            errors.append(("shift", "invalid_shift", "Turno inválido; debe ser 1, 2 o 3."))

    for column in ("production_quantity", "scrap_quantity"):
        if not row[column]:
            continue
        quantity = _parse_int(row[column])
        if quantity is None:
            errors.append((column, "not_integer", "Debe ser un número entero."))
        elif quantity < 0:
            errors.append((column, "negative_value", "No puede ser negativo."))
        else:
            parsed[column] = quantity

    production = parsed.get("production_quantity")
    scrap = parsed.get("scrap_quantity")
    if production is not None and scrap is not None and scrap > production:
        errors.append(
            ("scrap_quantity", "scrap_exceeds_production",
             f"El scrap es mayor que la producción ({production}).")
        )

    return errors, parsed


def validate_production(df: pd.DataFrame, master: MasterLists, today: date) -> ValidationResult:
    rows = [
        {column: str(value).strip() for column, value in record.items()}
        for record in df[PRODUCTION_COLUMNS].to_dict("records")
    ]

    errors: list[RowError] = []
    invalid_rows: set[int] = set()
    shift_keys: dict[int, ShiftKey] = {}
    parsed_rows: dict[int, dict] = {}

    for index, row in enumerate(rows):
        excel_row = index + FIRST_DATA_ROW
        row_errors, parsed = _validate_row(row, master, today)
        for column, code, reason in row_errors:
            errors.append(RowError(excel_row, column, row[column], code, reason))
        if row_errors:
            invalid_rows.add(index)
        else:
            parsed_rows[index] = {**row, **parsed}
        # Rows with an invalid date, line or shift cannot be assigned to a shift.
        if {"date", "line", "shift"} <= parsed.keys():
            shift_keys[index] = (parsed["date"], parsed["line"], parsed["shift"])

    # Duplicates: same date + line + shift + product inside the file. All copies are rejected,
    # because the system cannot know which one is correct.
    record_keys: dict[tuple, list[int]] = {}
    for index, key in shift_keys.items():
        record_keys.setdefault((*key, rows[index]["product"]), []).append(index)
    for indexes in record_keys.values():
        if len(indexes) > 1:
            for index in indexes:
                errors.append(
                    RowError(index + FIRST_DATA_ROW, "—", "", "duplicate_row",
                             "Registro duplicado en el archivo (misma fecha, línea, turno y producto).")
                )
                invalid_rows.add(index)
                parsed_rows.pop(index, None)

    # A shift is accepted only if all its rows are valid.
    shifts_rejected = {shift_keys[index] for index in invalid_rows if index in shift_keys}
    for index in list(parsed_rows):
        key = shift_keys[index]
        if key in shifts_rejected:
            date_, line, shift = key
            errors.append(
                RowError(index + FIRST_DATA_ROW, "—", "", "shift_rejected",
                         f"Rechazada: el turno {date_} / {line} / {shift} tiene filas inválidas.")
            )
            parsed_rows.pop(index)

    valid_rows = pd.DataFrame(list(parsed_rows.values()), columns=PRODUCTION_COLUMNS)
    if not valid_rows.empty:
        valid_rows = valid_rows.astype(
            {"shift": int, "production_quantity": int, "scrap_quantity": int}
        )

    return ValidationResult(
        valid_rows=valid_rows,
        errors=sorted(errors, key=lambda error: error.row),
        shifts_accepted={shift_keys[index] for index in parsed_rows},
        shifts_rejected=shifts_rejected,
    )
