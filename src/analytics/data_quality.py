"""REQ-005: data quality report — orphan downtime events, coverage and load history."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.analytics.coverage import Coverage, calculate_coverage
from src.database import downtime_repository, load_history_repository, production_repository
from src.ingestion.master_data import load_master_lists


@dataclass
class DataQualityReport:
    coverage: Coverage | None
    orphan_events: pd.DataFrame
    load_history: pd.DataFrame

    @property
    def has_data(self) -> bool:
        return self.coverage is not None


def build_data_quality_report(conn: sqlite3.Connection, master_dir: Path) -> DataQualityReport:
    """Raises MasterDataError if the master lists cannot be read."""
    lines = load_master_lists(master_dir).lines
    return DataQualityReport(
        coverage=calculate_coverage(production_repository.worked_shifts(conn), lines),
        orphan_events=downtime_repository.orphan_events(conn),
        load_history=load_history_repository.load_history(conn),
    )
