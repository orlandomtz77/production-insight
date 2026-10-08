"""REQ-001: upload a production CSV.

Flow: master lists → read file → validate rows → replace shifts + load history
(one transaction).
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from src.database import production_repository
from src.database.production_repository import LoadSummary
from src.ingestion.csv_reader import read_csv_file
from src.ingestion.master_data import MasterDataError, load_master_lists
from src.transformation.production_validation import (
    PRODUCTION_COLUMNS,
    RowError,
    validate_production,
)

FILE_TYPE = "production"


@dataclass
class LoadResult:
    summary: LoadSummary
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _reject_file(conn, file_name, rows_read, file_errors, warnings) -> LoadResult:
    summary = LoadSummary(
        loaded_at=_now(),
        file_type=FILE_TYPE,
        file_name=file_name,
        rows_read=rows_read,
        rows_stored=0,
        rows_rejected=rows_read,
        shifts_replaced=0,
        shifts_new=0,
        shifts_rejected=0,
        warnings=len(warnings),
        status="rejected",
    )
    with conn:
        production_repository.insert_load_history(conn, summary)
    return LoadResult(summary, warnings=warnings, file_errors=file_errors)


def load_production_file(
    source,
    file_name: str,
    conn: sqlite3.Connection,
    master_dir: Path,
    today: date | None = None,
) -> LoadResult:
    today = today or date.today()

    try:
        master = load_master_lists(master_dir)
    except MasterDataError as error:
        return _reject_file(conn, file_name, 0, [str(error)], [])

    read = read_csv_file(source, PRODUCTION_COLUMNS)
    if read.file_errors:
        return _reject_file(conn, file_name, read.rows_read, read.file_errors, read.warnings)

    validation = validate_production(read.data, master, today)

    with conn:
        replaced, new = production_repository.replace_shifts(conn, validation.valid_rows)
        summary = LoadSummary(
            loaded_at=_now(),
            file_type=FILE_TYPE,
            file_name=file_name,
            rows_read=read.rows_read,
            rows_stored=len(validation.valid_rows),
            rows_rejected=validation.rows_rejected,
            shifts_replaced=replaced,
            shifts_new=new,
            shifts_rejected=len(validation.shifts_rejected),
            warnings=len(read.warnings),
            status="completed",
        )
        production_repository.insert_load_history(conn, summary)

    return LoadResult(summary, errors=validation.errors, warnings=read.warnings)
