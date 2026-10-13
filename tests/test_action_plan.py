"""Tests for REQ-019: action plan (kaizen)."""

from dataclasses import replace
from datetime import date

import pytest

from src.action_plan.model import ActionItem, alert_key, default_priority, is_overdue, validate_action
from src.database import action_repository
from src.database.connection import connect
from src.database.maintenance import clear_all_data
from src.dashboard.action_board import board_html

LINES = frozenset({"L1", "L2"})
TODAY = date(2026, 10, 12)
NOW = "2026-10-12 09:00:00"


def item(**changes):
    base = ActionItem(
        problem="Scrap alto en L2", line="L2", action="Revisar molde del Producto C",
        owner="Ana", due_date=date(2026, 10, 20), priority="high",
    )
    return replace(base, **changes)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()


# --- Model ---------------------------------------------------------------------

def test_valid_action_has_no_errors():
    assert validate_action(item(), LINES) == []


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"problem": "  "}, "problema"),
        ({"action": ""}, "acción"),
        ({"owner": ""}, "responsable"),
        ({"line": "L9"}, "línea"),
        ({"due_date": None}, "fecha"),
        ({"priority": "urgent"}, "prioridad"),
        ({"stage": "paused"}, "etapa"),
    ],
)
def test_invalid_action_is_rejected_with_reason(changes, fragment):
    errors = validate_action(item(**changes), LINES)

    assert any(fragment in error.lower() for error in errors)


def test_overdue_only_when_past_due_and_not_finished():
    assert is_overdue("in_progress", date(2026, 10, 11), TODAY)
    assert not is_overdue("in_progress", TODAY, TODAY)  # due today is not overdue yet
    assert not is_overdue("done", date(2026, 10, 1), TODAY)


def test_default_priority_by_alert_rank():
    assert default_priority(1) == "high"
    assert default_priority(3) == "high"
    assert default_priority(4) == "medium"


def test_alert_key():
    assert alert_key(date(2026, 9, 30), "L2", "scrap_rate") == "2026-09-30|L2|scrap_rate"


# --- Repository -----------------------------------------------------------------------

def test_create_and_list(conn):
    action_id = action_repository.create_action(conn, item(), NOW)

    actions = action_repository.list_actions(conn)
    assert actions["id"].tolist() == [action_id]
    row = actions.iloc[0]
    assert row["stage"] == "open"
    assert row["due_date"] == "2026-10-20"
    assert row["created_at"] == NOW


def test_finishing_records_closing_date_and_reopening_clears_it(conn):
    action_id = action_repository.create_action(conn, item(), NOW)

    action_repository.update_action(conn, item(id=action_id, stage="done"), "2026-10-15 10:00:00")
    closed = action_repository.list_actions(conn).iloc[0]
    assert closed["closed_at"] == "2026-10-15 10:00:00"
    assert closed["updated_at"] == "2026-10-15 10:00:00"

    action_repository.update_action(conn, item(id=action_id, stage="done", owner="Luis"), "2026-10-16 10:00:00")
    assert action_repository.list_actions(conn).iloc[0]["closed_at"] == "2026-10-15 10:00:00"  # kept

    action_repository.update_action(conn, item(id=action_id, stage="in_progress"), "2026-10-17 10:00:00")
    assert action_repository.list_actions(conn).iloc[0]["closed_at"] is None


def test_one_action_per_alert(conn):
    key = alert_key(date(2026, 9, 30), "L2", "scrap_rate")
    action_id = action_repository.create_action(conn, item(source_alert=key), NOW)

    assert action_repository.action_for_alert(conn, key) == (action_id, "open")
    assert action_repository.action_for_alert(conn, "2026-09-30|L1|scrap_rate") is None
    with pytest.raises(Exception):
        action_repository.create_action(conn, item(source_alert=key), NOW)


def test_clear_all_data_keeps_actions(conn):
    action_repository.create_action(conn, item(), NOW)

    clear_all_data(conn)

    assert len(action_repository.list_actions(conn)) == 1


# --- Board ------------------------------------------------------------------------------

def test_board_has_four_columns_with_counts_and_marks_overdue(conn):
    action_repository.create_action(conn, item(due_date=date(2026, 10, 1), stage="in_progress"), NOW)
    action_repository.create_action(conn, item(problem="<Paro L1>", line="L1"), NOW)

    markup = board_html(action_repository.list_actions(conn), TODAY)

    for label in ("Abierta", "En proceso", "En revisión", "Terminada"):
        assert label in markup
    assert "Vencida" in markup          # icon + label, not color alone
    assert "&lt;Paro L1&gt;" in markup  # escaped
    assert markup.count('class="kanban-card') == 2
