"""Dashboard smoke tests with Streamlit AppTest (REQ-014). No browser needed.

The visual design is reviewed by eye; these tests check that the app runs and
shows the expected content.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.database.connection import connect
from src.ingestion.load_downtime import load_downtime_file
from src.ingestion.load_production import load_production_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"
APP = str(PROJECT_ROOT / "app.py")


def run_app(db_path, monkeypatch) -> AppTest:
    monkeypatch.setenv("PRODUCTION_INSIGHT_DB", str(db_path))
    monkeypatch.setenv("PRODUCTION_INSIGHT_MASTER_DIR", str(MASTER_DIR))
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    return app


@pytest.fixture
def loaded_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    load_production_file(SAMPLE_DIR / "production.csv", "production.csv", conn, MASTER_DIR, date(2026, 10, 7))
    load_downtime_file(SAMPLE_DIR / "downtime.csv", "downtime.csv", conn, MASTER_DIR, date(2026, 10, 7))
    conn.close()
    return db_path


def test_empty_database_shows_how_to_start(tmp_path, monkeypatch):
    app = run_app(tmp_path / "empty.db", monkeypatch)

    assert not app.exception
    assert any("Cargue primero" in info.value for info in app.info)


def test_dashboard_with_sample_data(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Resumen", "Alertas", "Producción", "Calidad", "Paros", "Calidad de datos"
    ]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Scrap rate"] == "3.2%"


def test_summary_names_the_evaluated_day_and_the_period(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    captions = [caption.value for caption in app.caption]
    assert any("Día evaluado: miércoles 30 de septiembre de 2026. 3 alertas ese día." in c for c in captions)
    assert any("Acumulado del 1 al 30 de septiembre de 2026" in c for c in captions)


def test_period_filter_changes_the_period_text(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.sidebar.date_input[0].set_value((date(2026, 9, 7), date(2026, 9, 12))).run()

    assert not app.exception
    assert any("Acumulado del 7 al 12 de septiembre de 2026" in c.value for c in app.caption)


def test_alerts_table_is_ranked(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    alerts = next(df.value for df in app.dataframe if "Prioridad" in df.value.columns)
    assert alerts["Línea"].tolist() == ["L2", "L1", "L1"]
    assert alerts["Problema"].iloc[0] == "Scrap rate"


def test_line_filter_reaches_alerts(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.sidebar.multiselect[0].set_value(["L1"]).run()

    assert not app.exception
    alerts = next(df.value for df in app.dataframe if "Prioridad" in df.value.columns)
    assert set(alerts["Línea"]) == {"L1"}
