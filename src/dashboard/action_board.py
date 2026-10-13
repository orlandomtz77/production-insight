"""Action plan board: one column per stage (REQ-019).

Overdue is shown with an icon and a label, never color alone.
"""

import html
from datetime import date

import pandas as pd

from src.action_plan.model import STAGES, is_overdue
from src.dashboard.formatting import PRIORITY_LABELS, STAGE_LABELS, format_period


def _card(row, today: date) -> str:
    due = date.fromisoformat(row["due_date"])
    overdue = is_overdue(row["stage"], due, today)
    badge = '<span class="kanban-overdue"><span aria-hidden="true">▲</span> Vencida</span>' if overdue else ""
    return (
        f'<div class="kanban-card{" kanban-card-overdue" if overdue else ""}">'
        f'<div class="kanban-id">#{int(row["id"])}, línea {html.escape(row["line"])}</div>'
        f'<div class="kanban-problem">{html.escape(row["problem"])}</div>'
        f'<div class="kanban-meta">{html.escape(row["owner"])}</div>'
        f'<div class="kanban-meta">Compromiso: {format_period(due, "day")} {badge}</div>'
        f'<div class="kanban-meta">Prioridad {PRIORITY_LABELS[row["priority"]].lower()}</div>'
        f"</div>"
    )


def board_html(actions: pd.DataFrame, today: date) -> str:
    """Four columns (Abierta, En proceso, En revisión, Terminada), cards sorted by due date."""
    columns = []
    for stage in STAGES:
        rows = actions[actions["stage"] == stage].sort_values(["due_date", "id"]) if not actions.empty else actions
        cards = "".join(_card(row, today) for _, row in rows.iterrows())
        empty = '<div class="kanban-empty">Sin acciones</div>' if not cards else ""
        columns.append(
            f'<section class="kanban-column" aria-label="{STAGE_LABELS[stage]}">'
            f'<h4>{STAGE_LABELS[stage]} <span class="kanban-count">{len(rows)}</span></h4>'
            f"{cards}{empty}</section>"
        )
    return f'<div class="kanban-board">{"".join(columns)}</div>'
