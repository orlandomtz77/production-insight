"""Upload flow shared by production (REQ-001) and downtime (REQ-002).

master lists → read file → validate rows → replace shifts + load history (one transaction).
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.database.load_history_repository import LoadSummary, insert_load_history
from src.ingestion.csv_reader import read_csv_file
from src.ingestion.master_data import MasterDataError, MasterLists, load_master_lists
from src.transformation.validation_common import RowError, ValidationResult

Validate = Callable[[pd.DataFrame, MasterLists, date], ValidationResult]
ReplaceShifts = Callable[[sqlite3.Connection, pd.DataFrame], tuple[int, int]]


@dataclass
class LoadResult:
    summary: LoadSummary
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _reject_file(conn, file_type, file_name, rows_read, file_errors, warnings) -> LoadResult:
    summary = LoadSummary(
        loaded_at=_now(),
        file_type=file_type,
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
        insert_load_history(conn, summary)
    return LoadResult(summary, warnings=warnings, file_errors=file_errors)


def load_file(
    source,
    file_name: str,
    conn: sqlite3.Connection,
    master_dir: Path,
    today: date,
    file_type: str,
    columns: list[str],
    validate: Validate,
    replace_shifts: ReplaceShifts,
) -> LoadResult:
    try:
        master = load_master_lists(master_dir)
    except MasterDataError as error:
        return _reject_file(conn, file_type, file_name, 0, [str(error)], [])

    read = read_csv_file(source, columns)
    if read.file_errors:
        return _reject_file(conn, file_type, file_name, read.rows_read, read.file_errors, read.warnings)

    validation = validate(read.data, master, today)
    warnings = read.warnings + validation.warnings

    with conn:
        replaced, new = replace_shifts(conn, validation.valid_rows)
        summary = LoadSummary(
            loaded_at=_now(),
            file_type=file_type,
            file_name=file_name,
            rows_read=read.rows_read,
            rows_stored=len(validation.valid_rows),
            rows_rejected=validation.rows_rejected,
            shifts_replaced=replaced,
            shifts_new=new,
            shifts_rejected=len(validation.shifts_rejected),
            warnings=len(warnings),
            status="completed",
        )
        insert_load_history(conn, summary)

    return LoadResult(summary, errors=validation.errors, warnings=warnings)
