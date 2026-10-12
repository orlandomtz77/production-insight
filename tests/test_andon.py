"""Unit tests for the andon board (REQ-014)."""

from datetime import date

from src.anomaly_detection.alerts import Alert, AlertReport, InvestigationArea
from src.dashboard.andon import andon_html, line_statuses


def alert(line, metric, rank):
    return Alert(
        rank=rank, line=line, metric=metric, evaluated_day=date(2026, 9, 30), value=0, baseline_mean=0,
        baseline_std=1, sample_size=25, baseline_first_day=date(2026, 9, 1),
        baseline_last_day=date(2026, 9, 29), z=3, percent_deviation=10, daily_impact=1,
        cumulative_impact=1, frequency=1, recurrence_days=[], priority_score=1, line_rate=None,
        investigation=InvestigationArea(None, None, []),
    )


def test_each_line_gets_a_status_with_label():
    report = AlertReport(
        evaluated_day=date(2026, 9, 30),
        alerts=[alert("L1", "scrap_rate", 2), alert("L1", "unplanned_downtime_per_shift", 3),
                alert("L2", "scrap_rate", 1)],
        not_evaluated=[("L4", m, "no_production") for m in ("a", "b", "c")],
    )

    statuses = {s.line: s for s in line_statuses(report, ["L1", "L2", "L3", "L4"])}

    assert statuses["L1"].state == "alert" and statuses["L1"].label == "2 alertas"
    assert statuses["L2"].label == "1 alerta"
    assert statuses["L1"].details[0] == "Prioridad 2: Scrap rate"
    assert statuses["L3"].state == "normal"
    assert statuses["L4"].state == "not_evaluated"


def test_html_escapes_line_names_and_never_uses_color_alone():
    report = AlertReport(date(2026, 9, 30), [], [])

    markup = andon_html(line_statuses(report, ["<L1>"]))

    assert "&lt;L1&gt;" in markup
    assert "Normal" in markup  # label next to the color
