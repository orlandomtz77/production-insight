"""Action plan items and their rules (REQ-019)."""

from dataclasses import dataclass
from datetime import date

STAGES = ("open", "in_progress", "in_review", "done")
PRIORITIES = ("high", "medium", "low")
DONE = "done"
HIGH_PRIORITY_RANKS = 3  # alerts ranked 1–3 create high-priority actions


@dataclass(frozen=True)
class ActionItem:
    problem: str
    line: str
    action: str
    owner: str
    due_date: date | None
    priority: str
    stage: str = "open"
    source_alert: str | None = None
    id: int | None = None


def validate_action(item: ActionItem, lines: frozenset[str]) -> list[str]:
    """Return the reasons why the action cannot be saved (Spanish, for the user)."""
    errors = []
    if not item.problem.strip():
        errors.append("Falta el problema.")
    if not item.action.strip():
        errors.append("Falta la acción (contramedida).")
    if not item.owner.strip():
        errors.append("Falta el responsable.")
    if item.line not in lines:
        errors.append(f"La línea '{item.line}' no está en la lista de líneas.")
    if not isinstance(item.due_date, date):
        errors.append("Falta la fecha compromiso.")
    if item.priority not in PRIORITIES:
        errors.append(f"Prioridad inválida: '{item.priority}'.")
    if item.stage not in STAGES:
        errors.append(f"Etapa inválida: '{item.stage}'.")
    return errors


def is_overdue(stage: str, due_date: date, today: date) -> bool:
    """Past its due date and not finished. Due today is not overdue yet."""
    return stage != DONE and due_date < today


def default_priority(alert_rank: int) -> str:
    return "high" if alert_rank <= HIGH_PRIORITY_RANKS else "medium"


def alert_key(day: date, line: str, metric: str) -> str:
    """Link between an action and the alert it came from (one action per alert)."""
    return f"{day.isoformat()}|{line}|{metric}"
