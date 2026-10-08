"""REQ-001: upload a production CSV."""

import sqlite3
from datetime import date
from pathlib import Path

from src.database import production_repository
from src.ingestion.loader import LoadResult, load_file
from src.transformation.production_validation import PRODUCTION_COLUMNS, validate_production


def load_production_file(
    source,
    file_name: str,
    conn: sqlite3.Connection,
    master_dir: Path,
    today: date | None = None,
) -> LoadResult:
    return load_file(
        source,
        file_name,
        conn,
        master_dir,
        today or date.today(),
        file_type="production",
        columns=PRODUCTION_COLUMNS,
        validate=validate_production,
        replace_shifts=production_repository.replace_shifts,
    )
