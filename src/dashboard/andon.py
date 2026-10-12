"""Andon board: one status plate per line for the reviewed period (REQ-014, REQ-016).

Status is shown with color + icon + label, never color alone.
"""

import html
from dataclasses import dataclass

from src.anomaly_detection.alerts import Alert
from src.dashboard.formatting import METRIC_LABELS, format_period

ALERT, NORMAL, NOT_EVALUATED = "alert", "normal", "not_evaluated"
MAX_DETAILS = 3


@dataclass
class LineStatus:
    line: str
    state: str
    label: str
    details: list[str]  # top alerts, or the reason it was not evaluated


def line_statuses(
    alerts: list[Alert], evaluated_lines: set[str], lines, show_dates: bool = False
) -> list[LineStatus]:
    """State per line: alerts in the period, normal if evaluated without alerts, otherwise not evaluated.

    `show_dates` adds the alert date to each detail (periods longer than one day).
    """
    statuses = []
    for line in sorted(lines):
        line_alerts = [a for a in alerts if a.line == line]  # already ranked
        if line_alerts:
            count = len(line_alerts)
            label = f"{count} alerta" + ("s" if count > 1 else "")
            details = [
                f"Prioridad {a.rank}: {METRIC_LABELS[a.metric]}"
                + (f" ({format_period(a.evaluated_day, 'day')})" if show_dates else "")
                for a in line_alerts[:MAX_DETAILS]
            ]
            if count > MAX_DETAILS:
                details.append(f"y {count - MAX_DETAILS} más")
            statuses.append(LineStatus(line, ALERT, label, details))
        elif line in evaluated_lines:
            statuses.append(LineStatus(line, NORMAL, "Normal", ["Dentro de su comportamiento habitual"]))
        else:
            statuses.append(LineStatus(line, NOT_EVALUATED, "Sin evaluar", ["Sin datos suficientes"]))
    return statuses


ICONS = {ALERT: "▲", NORMAL: "●", NOT_EVALUATED: "○"}


def andon_html(statuses: list[LineStatus]) -> str:
    plates = []
    for status in statuses:
        details = "".join(f"<li>{html.escape(d)}</li>" for d in status.details)
        plates.append(
            f'<div class="andon-plate andon-{status.state}" role="status">'
            f'<div class="andon-lamp"></div>'
            f'<div class="andon-line">{html.escape(status.line)}</div>'
            f'<div class="andon-label"><span aria-hidden="true">{ICONS[status.state]}</span> '
            f"{html.escape(status.label)}</div>"
            f'<ul class="andon-details">{details}</ul>'
            f"</div>"
        )
    return f'<div class="andon-board">{"".join(plates)}</div>'


def alert_card_html(title: str, facts: list[tuple[str, str]], heading: bool = True) -> str:
    """Alert card: facts as a definition list; 'Dónde investigar' set apart at the end."""
    *details, (focus_label, focus_text) = facts
    rows = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(text)}</dd>" for label, text in details)
    focus = (
        f'<div class="alert-focus"><strong>{html.escape(focus_label)}:</strong> {html.escape(focus_text)}</div>'
    )
    header = f"<h3>{html.escape(title)}</h3>" if heading else ""
    return f'<div class="alert-card" role="note">{header}<dl>{rows}{focus}</dl></div>'
