"""Master lists (data/master/*.csv): lines, products, downtime reasons and planned stops."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

MASTER_FILES = {
    "lines": ("lines.csv", "line"),
    "products": ("products.csv", "product"),
    "downtime_reasons": ("downtime_reasons.csv", "downtime_reason"),
}
REASONS_FILE = "downtime_reasons.csv"
PLANNED_COLUMN = "planned"
PLANNED_VALUES = {"sí": True, "si": True, "no": False}

PLANNED_STOPS_FILE = "planned_stops.csv"
PLANNED_STOPS_COLUMNS = ["date", "line", "shift", "reason"]
ALL_SHIFTS = (1, 2, 3)
FIRST_DATA_ROW = 2  # Excel row numbers: the header is row 1


class MasterDataError(Exception):
    """A master list is missing, unreadable or invalid."""


@dataclass(frozen=True)
class MasterLists:
    lines: frozenset[str]
    products: frozenset[str]
    downtime_reasons: frozenset[str]
    planned_reasons: frozenset[str] = frozenset()  # subset of downtime_reasons (ADR-005)


@dataclass
class PlannedStops:
    shifts: set[tuple[str, str, int]] = field(default_factory=set)
    invalid_rows: list[str] = field(default_factory=list)


def _read_master_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise MasterDataError(f"No se encontró la lista maestra '{path}'.")
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        raise MasterDataError(f"No se pudo leer la lista maestra '{path}': {error}") from error
    df.columns = [str(column).strip() for column in df.columns]
    return df.apply(lambda column: column.str.strip())


def _planned_reasons(df: pd.DataFrame, path: Path) -> frozenset[str]:
    if PLANNED_COLUMN not in df.columns:
        raise MasterDataError(
            f"La lista maestra '{path}' no tiene la columna '{PLANNED_COLUMN}' (sí / no)."
        )
    planned = set()
    for reason, value in zip(df["downtime_reason"], df[PLANNED_COLUMN]):
        if not reason:
            continue
        if value.lower() not in PLANNED_VALUES:
            raise MasterDataError(
                f"En '{path}', la causa '{reason}' tiene planned = '{value}'; debe ser 'sí' o 'no'."
            )
        if PLANNED_VALUES[value.lower()]:
            planned.add(reason)
    return frozenset(planned)


def load_master_lists(master_dir: Path) -> MasterLists:
    values = {}
    for name, (file_name, column) in MASTER_FILES.items():
        path = Path(master_dir) / file_name
        df = _read_master_csv(path)
        if column not in df.columns:
            raise MasterDataError(f"La lista maestra '{path}' no tiene la columna '{column}'.")
        items = frozenset(value for value in df[column] if value)
        if not items:
            raise MasterDataError(f"La lista maestra '{path}' está vacía.")
        values[name] = items
        if file_name == REASONS_FILE:
            values["planned_reasons"] = _planned_reasons(df, path)
    return MasterLists(**values)


def load_planned_stops(master_dir: Path, lines: frozenset[str]) -> PlannedStops:
    """Read the optional planned stops calendar (ADR-005).

    An empty shift means the whole day. Invalid rows are ignored and reported.
    """
    path = Path(master_dir) / PLANNED_STOPS_FILE
    if not path.exists():
        return PlannedStops()

    df = _read_master_csv(path)
    missing = [column for column in PLANNED_STOPS_COLUMNS if column not in df.columns]
    if missing:
        return PlannedStops(invalid_rows=[f"'{path}': faltan columnas {', '.join(missing)}; se ignoró."])

    stops = PlannedStops()
    for index, row in enumerate(df.to_dict("records")):
        problems = []
        try:
            day = datetime.strptime(row["date"], "%Y-%m-%d").date().isoformat()
        except ValueError:
            problems.append(f"fecha inválida '{row['date']}'")
        if row["line"] not in lines:
            problems.append(f"línea desconocida '{row['line']}'")
        if row["shift"] == "":
            shifts = ALL_SHIFTS
        elif row["shift"] in {str(s) for s in ALL_SHIFTS}:
            shifts = (int(row["shift"]),)
        else:
            problems.append(f"turno inválido '{row['shift']}'")

        if problems:
            stops.invalid_rows.append(
                f"{PLANNED_STOPS_FILE}, fila {index + FIRST_DATA_ROW}: {'; '.join(problems)}."
            )
        else:
            stops.shifts.update((day, row["line"], shift) for shift in shifts)
    return stops
