"""Read an uploaded CSV file and check file-level rules (REQ-001, REQ-002)."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class CsvReadResult:
    data: pd.DataFrame | None
    file_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def rows_read(self) -> int:
        return 0 if self.data is None else len(self.data)


def read_csv_file(source, required_columns: list[str]) -> CsvReadResult:
    """Read every value as text; type checks are done by row validation.

    `source` can be a path or a file-like object (e.g., a Streamlit upload).
    `utf-8-sig` also accepts files saved by Excel with a BOM.
    """
    try:
        df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return CsvReadResult(None, ["El archivo está vacío."])
    except (pd.errors.ParserError, UnicodeDecodeError) as error:
        return CsvReadResult(None, [f"El archivo no es un CSV legible: {error}"])

    df.columns = [str(column).strip() for column in df.columns]

    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        return CsvReadResult(df, [f"Faltan columnas obligatorias: {', '.join(missing)}."])
    if df.empty:
        return CsvReadResult(df, ["El archivo no tiene filas de datos."])

    warnings = []
    extra = [column for column in df.columns if column not in required_columns]
    if extra:
        warnings.append(f"Columnas ignoradas (no forman parte del formato): {', '.join(extra)}.")

    return CsvReadResult(df[required_columns], warnings=warnings)
