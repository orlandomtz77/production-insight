"""Row-level validation of production records (REQ-001)."""

from datetime import date

import pandas as pd

from src.ingestion.master_data import MasterLists
from src.transformation.validation_common import (
    NO_COLUMN,
    RowChecks,
    ValidationResult,
    parse_int,
    validate_common_fields,
)

PRODUCTION_COLUMNS = [
    "date",
    "line",
    "shift",
    "product",
    "production_quantity",
    "scrap_quantity",
]
QUANTITY_COLUMNS = ["production_quantity", "scrap_quantity"]


def _validate_row(row: dict[str, str], master: MasterLists, today: date):
    errors, parsed = validate_common_fields(row, master, today)

    for column in QUANTITY_COLUMNS:
        if not row[column]:
            continue
        quantity = parse_int(row[column])
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
    checks = RowChecks(df, PRODUCTION_COLUMNS, lambda row: _validate_row(row, master, today))

    # Duplicates: same date + line + shift + product inside the file. All copies are rejected,
    # because the system cannot know which one is correct.
    record_keys: dict[tuple, list[int]] = {}
    for index, key in checks.shift_keys.items():
        record_keys.setdefault((*key, checks.rows[index]["product"]), []).append(index)
    for indexes in record_keys.values():
        if len(indexes) > 1:
            for index in indexes:
                checks.add_error(
                    index, NO_COLUMN, "duplicate_row",
                    "Registro duplicado en el archivo (misma fecha, línea, turno y producto).",
                )

    return checks.finalize(int_columns=["shift", *QUANTITY_COLUMNS])
