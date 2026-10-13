"""Read an uploaded file (CSV or Excel .xlsx) and check file-level rules (REQ-001, REQ-002, REQ-018).

Every value is returned as text; type checks are done by row validation, so CSV
and Excel files go through exactly the same rules.
"""

import math
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

CSV, XLSX = ".csv", ".xlsx"
OLD_EXCEL = ".xls"


@dataclass
class TableReadResult:
    data: pd.DataFrame | None
    file_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def rows_read(self) -> int:
        return 0 if self.data is None else len(self.data)


def excel_cell_to_text(value) -> str:
    """Convert an Excel cell to the text the validation expects (REQ-018).

    Dates → 'YYYY-MM-DD'; whole numbers stored as decimals (1250.0) → '1250';
    other decimals keep their value ('10.5', rejected later as not an integer);
    empty cells → ''.
    """
    if value is None:
        return ""
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()


def _read_csv(source) -> TableReadResult:
    # utf-8-sig also accepts CSV files saved by Excel with a BOM.
    try:
        df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return TableReadResult(None, ["El archivo está vacío."])
    except (pd.errors.ParserError, UnicodeDecodeError) as error:
        return TableReadResult(None, [f"El archivo no es un CSV legible: {error}"])
    return TableReadResult(df)


def _read_xlsx(source) -> TableReadResult:
    try:
        workbook = pd.ExcelFile(source, engine="openpyxl")
    except (zipfile.BadZipFile, ValueError, KeyError, OSError) as error:
        return TableReadResult(None, [f"El archivo no es un Excel (.xlsx) legible: {error}"])
    with workbook:
        sheet = workbook.sheet_names[0]
        df = workbook.parse(sheet, dtype=object)
        warnings = []
        if len(workbook.sheet_names) > 1:
            warnings.append(f"El archivo tiene {len(workbook.sheet_names)} hojas; se leyó la primera: '{sheet}'.")
    if df.columns.empty:
        return TableReadResult(None, ["El archivo está vacío."])
    df = df.map(excel_cell_to_text)
    return TableReadResult(df, warnings=warnings)


def _check_columns(read: TableReadResult, required_columns: list[str]) -> TableReadResult:
    df = read.data
    df.columns = [str(column).strip() for column in df.columns]

    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        return TableReadResult(df, [f"Faltan columnas obligatorias: {', '.join(missing)}."], read.warnings)
    if df.empty:
        return TableReadResult(df, ["El archivo no tiene filas de datos."], read.warnings)

    warnings = list(read.warnings)
    extra = [column for column in df.columns if column not in required_columns]
    if extra:
        warnings.append(f"Columnas ignoradas (no forman parte del formato): {', '.join(extra)}.")
    return TableReadResult(df[required_columns], warnings=warnings)


def read_table_file(source, file_name: str, required_columns: list[str]) -> TableReadResult:
    """Read a CSV or .xlsx file by its extension.

    `source` can be a path or a file-like object (e.g., a Streamlit upload).
    """
    extension = Path(file_name).suffix.lower()
    if extension == CSV:
        read = _read_csv(source)
    elif extension == XLSX:
        read = _read_xlsx(source)
    elif extension == OLD_EXCEL:
        return TableReadResult(None, [
            "Los archivos .xls (Excel 97-2003) no son compatibles. "
            "Ábralo en Excel y guárdelo como .xlsx o .csv."
        ])
    else:
        return TableReadResult(None, [
            f"Tipo de archivo no compatible ('{extension or 'sin extensión'}'). Use un archivo CSV o Excel (.xlsx)."
        ])

    if read.file_errors:
        return read
    return _check_columns(read, required_columns)
