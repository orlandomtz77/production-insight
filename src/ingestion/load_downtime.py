"""REQ-002: upload a downtime CSV. Production must be loaded first."""

import sqlite3
from datetime import date
from pathlib import Path

from src.database import downtime_repository, production_repository
from src.ingestion.loader import LoadResult, load_file
from src.transformation.downtime_validation import DOWNTIME_COLUMNS, validate_downtime


def load_downtime_file(
    source,
    file_name: str,
    conn: sqlite3.Connection,
    master_dir: Path,
    today: date | None = None,
) -> LoadResult:
    # The orchestrator reads the database; validation only receives the keys.
    production_keys = production_repository.existing_keys(conn)

    return load_file(
        source,
        file_name,
        conn,
        master_dir,
        today or date.today(),
        file_type="downtime",
        columns=DOWNTIME_COLUMNS,
        validate=lambda df, master, day: validate_downtime(df, master, day, production_keys),
        replace_shifts=downtime_repository.replace_shifts,
    )
