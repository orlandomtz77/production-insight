"""Tests for REQ-018: upload Excel (.xlsx) files."""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.database.connection import connect
from src.ingestion.file_reader import excel_cell_to_text, read_table_file
from src.ingestion.load_downtime import load_downtime_file
from src.ingestion.load_production import load_production_file
from src.transformation.production_validation import PRODUCTION_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
TODAY = date(2026, 10, 7)


def as_excel(csv_path: Path, xlsx_path: Path, number_columns) -> Path:
    """Save a sample CSV as a real Excel file: date cells and numbers stored as decimals."""
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    for column in number_columns:
        df[column] = df[column].astype(float)
    df.to_excel(xlsx_path, index=False)
    return xlsx_path


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()


# --- Cell conversion -----------------------------------------------------------

@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        (pd.Timestamp("2026-09-30"), "2026-09-30"),
        (datetime(2026, 9, 30, 6, 30), "2026-09-30"),
        (date(2026, 9, 30), "2026-09-30"),
        (1250.0, "1250"),
        (10.5, "10.5"),
        (3, "3"),
        (float("nan"), ""),
        (None, ""),
        ("  L1 ", "L1"),
    ],
)
def test_excel_cell_to_text(cell, expected):
    assert excel_cell_to_text(cell) == expected


# --- Sample dataset as Excel ------------------------------------------------------

def test_sample_dataset_as_excel_loads_like_csv(conn, tmp_path):
    production = as_excel(SAMPLE_DIR / "production.csv", tmp_path / "produccion.xlsx",
                          ["production_quantity", "scrap_quantity"])
    downtime = as_excel(SAMPLE_DIR / "downtime.csv", tmp_path / "paros.xlsx", ["downtime_minutes"])

    loaded_production = load_production_file(production, "produccion.xlsx", conn, MASTER_DIR, TODAY)
    loaded_downtime = load_downtime_file(downtime, "paros.xlsx", conn, MASTER_DIR, TODAY)

    assert loaded_production.summary.rows_stored == 263
    assert loaded_production.summary.rows_rejected == 0
    assert loaded_downtime.summary.rows_stored == 485
    assert loaded_downtime.summary.rows_rejected == 0
    stored = conn.execute("SELECT date, production_quantity FROM production_records ORDER BY id LIMIT 1").fetchone()
    assert stored == ("2026-09-01", 1347)


def test_error_rows_match_excel_rows(conn, tmp_path):
    df = pd.read_csv(SAMPLE_DIR / "production.csv").head(3)
    df.loc[1, "shift"] = 4  # second data row → Excel row 3
    path = tmp_path / "bad.xlsx"
    df.to_excel(path, index=False)

    result = load_production_file(path, "bad.xlsx", conn, MASTER_DIR, TODAY)

    assert {e.row for e in result.errors if e.code == "invalid_shift"} == {3}


def test_workbook_with_several_sheets_reads_the_first_and_warns(tmp_path):
    path = tmp_path / "libro.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.read_csv(SAMPLE_DIR / "production.csv").head(2).to_excel(writer, sheet_name="Produccion", index=False)
        pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="Notas", index=False)

    read = read_table_file(path, "libro.xlsx", PRODUCTION_COLUMNS)

    assert read.file_errors == []
    assert read.rows_read == 2
    assert any("Produccion" in warning for warning in read.warnings)


def test_missing_column_in_excel_is_rejected(tmp_path):
    path = tmp_path / "sin_scrap.xlsx"
    pd.read_csv(SAMPLE_DIR / "production.csv").drop(columns=["scrap_quantity"]).head(2).to_excel(path, index=False)

    read = read_table_file(path, "sin_scrap.xlsx", PRODUCTION_COLUMNS)

    assert any("scrap_quantity" in message for message in read.file_errors)


# --- Rejected files ------------------------------------------------------------------

def test_xls_is_rejected_with_instructions(tmp_path):
    path = tmp_path / "viejo.xls"
    path.write_bytes(b"old excel")

    read = read_table_file(path, "viejo.xls", PRODUCTION_COLUMNS)

    assert any(".xlsx o .csv" in message for message in read.file_errors)


def test_corrupt_xlsx_is_rejected(tmp_path):
    path = tmp_path / "roto.xlsx"
    path.write_bytes(b"this is not a zip file")

    read = read_table_file(path, "roto.xlsx", PRODUCTION_COLUMNS)

    assert read.file_errors
    assert read.data is None


def test_unknown_extension_is_rejected(tmp_path):
    path = tmp_path / "datos.txt"
    path.write_text("date,line\n", encoding="utf-8")

    read = read_table_file(path, "datos.txt", PRODUCTION_COLUMNS)

    assert any("CSV" in message and "Excel" in message for message in read.file_errors)


def test_rejected_excel_upload_is_recorded(conn, tmp_path):
    path = tmp_path / "viejo.xls"
    path.write_bytes(b"old excel")

    result = load_production_file(path, "viejo.xls", conn, MASTER_DIR, TODAY)

    assert result.summary.status == "rejected"
    assert conn.execute("SELECT file_name, status FROM load_history").fetchall() == [("viejo.xls", "rejected")]
