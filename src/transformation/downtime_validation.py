"""Row-level validation of downtime events (REQ-002).

Production records must be loaded first: each event must match an existing
production record (date + line + shift + product), otherwise it is an orphan (ADR-001).
The existing keys are passed in, so this module does not access the database.
"""

from collections import defaultdict
from datetime import date

import pandas as pd

from src.ingestion.master_data import MasterLists
from src.transformation.validation_common import (
    NO_COLUMN,
    RowChecks,
    ValidationResult,
    excel_row,
    parse_int,
    validate_common_fields,
)

DOWNTIME_COLUMNS = [
    "date",
    "line",
    "shift",
    "product",
    "downtime_minutes",
    "downtime_reason",
]
SHIFT_MINUTES = 480

ProductionKey = tuple[str, str, int, str]


def _validate_row(
    row: dict[str, str], master: MasterLists, today: date, production_keys: set[ProductionKey]
):
    errors, parsed = validate_common_fields(row, master, today)

    if row["downtime_minutes"]:
        minutes = parse_int(row["downtime_minutes"])
        if minutes is None:
            errors.append(("downtime_minutes", "not_integer", "Debe ser un número entero de minutos."))
        elif minutes <= 0:
            errors.append(("downtime_minutes", "not_positive", "Debe ser mayor que 0."))
        elif minutes > SHIFT_MINUTES:
            errors.append(
                ("downtime_minutes", "exceeds_shift_length",
                 f"No puede ser mayor que la duración del turno ({SHIFT_MINUTES} min).")
            )
        else:
            parsed["downtime_minutes"] = minutes

    if row["downtime_reason"] and row["downtime_reason"] not in master.downtime_reasons:
        errors.append(
            ("downtime_reason", "unknown_reason", "La causa no está en la lista de causas de paro.")
        )

    key_fields = ("date", "line", "shift", "product")
    if all(field in parsed for field in key_fields):
        key = tuple(parsed[field] for field in key_fields)
        if key not in production_keys:
            errors.append(
                (NO_COLUMN, "orphan_event",
                 "No existe registro de producción para esta fecha, línea, turno y producto. "
                 "Cargue primero la producción.")
            )

    return errors, parsed


def validate_downtime(
    df: pd.DataFrame,
    master: MasterLists,
    today: date,
    production_keys: set[ProductionKey],
) -> ValidationResult:
    checks = RowChecks(
        df, DOWNTIME_COLUMNS, lambda row: _validate_row(row, master, today, production_keys)
    )

    # Total downtime per shift (all products) must not exceed the shift length.
    rows_by_shift: dict[tuple, list[int]] = defaultdict(list)
    for index, key in checks.shift_keys.items():
        if "downtime_minutes" in checks.parsed[index]:
            rows_by_shift[key].append(index)
    for (day, line, shift), indexes in rows_by_shift.items():
        total = sum(checks.parsed[i]["downtime_minutes"] for i in indexes)
        if total > SHIFT_MINUTES:
            for index in indexes:
                checks.add_error(
                    index, NO_COLUMN, "shift_total_exceeded",
                    f"El turno {day} / {line} / {shift} suma {total} min de paro "
                    f"(máximo {SHIFT_MINUTES}).",
                )

    result = checks.finalize(int_columns=["shift", "downtime_minutes"])

    # Identical rows can be real events (e.g., two 10-minute failures): stored, with a warning.
    rejected_rows = {error.row for error in result.errors}
    identical: dict[tuple, list[int]] = defaultdict(list)
    for index, row in enumerate(checks.rows):
        if excel_row(index) not in rejected_rows:
            identical[tuple(row.values())].append(index)
    result.warnings = [
        f"Filas idénticas (se guardaron todas): {', '.join(str(excel_row(i)) for i in indexes)}."
        for indexes in identical.values()
        if len(indexes) > 1
    ]
    return result
