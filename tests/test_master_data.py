"""Unit tests for master lists and planned stops (ADR-005)."""

from pathlib import Path

import pytest

from src.ingestion.master_data import MasterDataError, load_master_lists, load_planned_stops

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_DIR = PROJECT_ROOT / "data" / "master"


def write_master(directory: Path, reasons_csv: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "lines.csv").write_text("line\nL1\nL2\n", encoding="utf-8")
    (directory / "products.csv").write_text("product\nProducto A\n", encoding="utf-8")
    (directory / "downtime_reasons.csv").write_text(reasons_csv, encoding="utf-8")
    return directory


def test_sample_master_lists_classify_planned_reasons():
    master = load_master_lists(MASTER_DIR)

    assert master.planned_reasons == {"Mantenimiento", "Paro programado"}
    assert master.planned_reasons <= master.downtime_reasons
    assert "Falla de máquina" in master.downtime_reasons


def test_reasons_without_planned_column_are_rejected(tmp_path):
    directory = write_master(tmp_path, "downtime_reason\nOtro\n")

    with pytest.raises(MasterDataError, match="planned"):
        load_master_lists(directory)


def test_invalid_planned_value_is_rejected(tmp_path):
    directory = write_master(tmp_path, "downtime_reason,planned\nOtro,quizás\n")

    with pytest.raises(MasterDataError, match="quizás"):
        load_master_lists(directory)


def test_planned_value_accepts_si_without_accent_and_any_case(tmp_path):
    directory = write_master(tmp_path, "downtime_reason,planned\nOtro,NO\nJunta,Si\n")

    assert load_master_lists(directory).planned_reasons == {"Junta"}


def test_missing_planned_stops_file_means_no_planned_stops(tmp_path):
    stops = load_planned_stops(tmp_path, frozenset({"L1"}))

    assert stops.shifts == set()
    assert stops.invalid_rows == []


def test_planned_stops_empty_shift_means_whole_day(tmp_path):
    (tmp_path / "planned_stops.csv").write_text(
        "date,line,shift,reason\n2026-09-16,L1,,Día festivo\n2026-09-17,L2,3,Sin programa\n",
        encoding="utf-8",
    )

    stops = load_planned_stops(tmp_path, frozenset({"L1", "L2"}))

    assert stops.shifts == {
        ("2026-09-16", "L1", 1), ("2026-09-16", "L1", 2), ("2026-09-16", "L1", 3),
        ("2026-09-17", "L2", 3),
    }


def test_invalid_planned_stop_rows_are_ignored_and_reported(tmp_path):
    (tmp_path / "planned_stops.csv").write_text(
        "date,line,shift,reason\n"
        "2026-09-31,L1,1,x\n"   # invalid date
        "2026-09-16,L9,1,x\n"   # unknown line
        "2026-09-16,L1,5,x\n"   # invalid shift
        "2026-09-16,L1,2,ok\n",
        encoding="utf-8",
    )

    stops = load_planned_stops(tmp_path, frozenset({"L1"}))

    assert stops.shifts == {("2026-09-16", "L1", 2)}
    assert len(stops.invalid_rows) == 3
    assert "2" in stops.invalid_rows[0]  # Excel row number


def test_sample_planned_stops():
    stops = load_planned_stops(MASTER_DIR, load_master_lists(MASTER_DIR).lines)

    assert stops.shifts == {("2026-09-16", "L3", 3)}
