"""Dashboard smoke tests with Streamlit AppTest (REQ-014). No browser needed.

The visual design is reviewed by eye; these tests check that the app runs and
shows the expected content.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.analytics.periods import ReviewPeriod

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
        "Resumen", "Alertas", "Plan de acción", "Producción", "Calidad", "Paros", "Calidad de datos"
    ]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Scrap rate"] == "4.4%"  # default period: day 2026-09-30


def test_default_review_is_the_last_working_day(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    assert app.sidebar.radio[0].value == "day"
    selector = app.sidebar.selectbox[0]
    assert selector.value == ReviewPeriod("day", date(2026, 9, 30), date(2026, 9, 30))
    assert selector.options[0] == "miércoles 30 de septiembre de 2026"
    assert "domingo 27 de septiembre de 2026" not in selector.options  # Sunday overtime is not offered
    captions = [caption.value for caption in app.caption]
    assert any("3 alertas del miércoles 30 de septiembre de 2026." in c for c in captions)


def test_old_time_controls_are_gone(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    assert len(app.sidebar.date_input) == 0  # "Periodo" filter replaced by "Revisar por"
    assert [radio.label for radio in app.sidebar.radio] == ["Revisar por"]


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


def test_selecting_a_day(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.sidebar.selectbox[0].set_value(ReviewPeriod("day", date(2026, 9, 28), date(2026, 9, 28))).run()

    assert not app.exception
    assert any("1 alerta del lunes 28 de septiembre de 2026." in c.value for c in app.caption)
    alerts = next(df.value for df in app.dataframe if "Prioridad" in df.value.columns)
    assert alerts["Línea"].tolist() == ["L2"]


def test_week_review_lists_alerts_of_every_day(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.sidebar.radio[0].set_value("week").run()

    assert not app.exception
    assert app.sidebar.selectbox[0].options[0] == "Semana del 28-sep al 04-oct"
    captions = [caption.value for caption in app.caption]
    assert any("Acumulado de la semana del 28 de septiembre al 4 de octubre de 2026" in c for c in captions)
    alerts = next(df.value for df in app.dataframe if "Prioridad" in df.value.columns)
    assert {"28-sep", "30-sep"} <= set(alerts["Fecha"])


def test_month_review(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.sidebar.radio[0].set_value("month").run()

    assert not app.exception
    assert app.sidebar.selectbox[0].options == ["septiembre 2026"]
    assert any("Acumulado de septiembre de 2026" in c.value for c in app.caption)


def test_clear_all_data_requires_confirmation(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    delete = next(b for b in app.sidebar.button if b.label == "Borrar todos los datos")
    assert delete.disabled

    app.sidebar.checkbox[0].check().run()
    next(b for b in app.sidebar.button if b.label == "Borrar todos los datos").click().run()

    assert not app.exception
    assert any("Se borraron todos los datos" in s.value for s in app.success)
    assert any("Cargue primero" in info.value for info in app.info)



# --- Action plan (REQ-019) ---------------------------------------------------------

def test_empty_plan_invites_to_create_actions(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    assert any("Todavía no hay acciones" in info.value for info in app.info)


def test_create_manual_action(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.text_input(key="new_problem").input("Fuga de aire en L3")
    app.text_area(key="new_action").input("Cambiar conexiones de la estación 4")
    app.selectbox(key="new_line").set_value("L3")
    app.text_input(key="new_owner").input("Luis")
    app.button(key="new_submit").click().run()

    assert not app.exception
    assert any("Acción #1 creada" in s.value for s in app.success)
    assert any("Fuga de aire en L3" in h.proto.body for h in app.get("html"))


def test_manual_action_without_owner_is_rejected(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)

    app.text_input(key="new_problem").input("Fuga de aire")
    app.text_area(key="new_action").input("Revisar")
    app.button(key="new_submit").click().run()

    assert any("Falta el responsable" in e.value for e in app.error)


def test_create_action_from_alert_once(loaded_db, monkeypatch):
    app = run_app(loaded_db, monkeypatch)
    key = "2026-09-30|L2|scrap_rate"

    app.text_area(key=f"action_{key}").input("Revisar molde del Producto C")
    app.text_input(key=f"owner_{key}").input("Ana")
    app.button(key=f"submit_{key}").click().run()

    assert not app.exception
    assert any("Acción #1 creada" in s.value for s in app.success)
    assert any("Acción #1 (Abierta)" in c.value for c in app.caption)  # no second form for this alert
