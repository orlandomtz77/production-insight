"""Andon board: one status plate per line for the evaluated day (REQ-014).

Status is shown with color + icon + label, never color alone.
"""

import html
from dataclasses import dataclass

from src.anomaly_detection.alerts import AlertReport
from src.dashboard.formatting import METRIC_LABELS

ALERT, NORMAL, NOT_EVALUATED = "alert", "normal", "not_evaluated"


@dataclass
class LineStatus:
    line: str
    state: str
    label: str
    details: list[str]  # one line per alert, or the reason it was not evaluated


def line_statuses(report: AlertReport, lines) -> list[LineStatus]:
    statuses = []
    for line in sorted(lines):
        alerts = [a for a in report.alerts if a.line == line]
        skipped = [n for n in report.not_evaluated if n[0] == line]
        if alerts:
            count = len(alerts)
            label = f"{count} alerta" + ("s" if count > 1 else "")
            details = [f"Prioridad {a.rank}: {METRIC_LABELS[a.metric]}" for a in alerts]
            statuses.append(LineStatus(line, ALERT, label, details))
        elif skipped and len(skipped) == 3:
            statuses.append(LineStatus(line, NOT_EVALUATED, "Sin evaluar", ["Sin datos suficientes"]))
        else:
            statuses.append(LineStatus(line, NORMAL, "Normal", ["Dentro de su comportamiento habitual"]))
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
