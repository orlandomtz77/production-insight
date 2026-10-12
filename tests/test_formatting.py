"""Unit tests for user-facing formatting (Spanish) of numbers and alerts."""

from datetime import date

import pytest

from src.anomaly_detection.alerts import Alert, InvestigationArea
from src.dashboard.formatting import (
    alert_message,
    alert_title,
    format_minutes,
    format_number,
    format_percent,
    format_shifts,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(12450, "12,450"), (1046.158, "1,046"), (None, "N/A"), (float("nan"), "N/A")],
)
def test_format_number(value, expected):
    assert format_number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(0.032, "3.2%"), (0.0746, "7.5%"), (None, "N/A")]
)
def test_format_percent(value, expected):
    assert format_percent(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(45, "45 min"), (1230, "1,230 min (20.5 h)"), (None, "N/A")]
)
def test_format_minutes(value, expected):
    assert format_minutes(value) == expected


def scrap_alert():
    return Alert(
        rank=1, line="L2", metric="scrap_rate", evaluated_day=date(2026, 9, 30),
        value=0.0746, baseline_mean=0.0337, baseline_std=0.011, sample_size=25,
        baseline_first_day=date(2026, 9, 1), baseline_last_day=date(2026, 9, 29),
        z=3.71, percent_deviation=121.4, daily_impact=115.0, cumulative_impact=332.2,
        frequency=3, recurrence_days=[date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)],
        priority_score=996.6, line_rate=2.296,
        investigation=InvestigationArea(focus="Producto C", value=0.0899, shifts=[1, 2]),
    )


def test_alert_title():
    assert alert_title(scrap_alert()) == "L2: Scrap rate por encima de lo normal (2026-09-30)"


def test_alert_message_has_every_required_part():
    message = alert_message(scrap_alert())

    assert "7.5%" in message                      # current value
    assert "3.4%" in message                      # baseline
    assert "25 días" in message                   # sample size
    assert "2026-09-01 a 2026-09-29" in message   # baseline period
    assert "+121.4%" in message                   # deviation
    assert "3.7 desviaciones" in message
    assert "115 piezas" in message and "332 piezas" in message  # impact
    assert "3 de los últimos 6" in message        # recurrence
    assert "Producto C" in message                # where to investigate
    assert "turnos 1 y 2" in message
    assert "_" not in message                     # no internal names


@pytest.mark.parametrize(
    ("shifts", "expected"),
    [([2], "turno 2"), ([1, 2], "turnos 1 y 2"), ([1, 2, 3], "turnos 1, 2 y 3")],
)
def test_format_shifts(shifts, expected):
    assert format_shifts(shifts) == expected


@pytest.mark.parametrize(
    ("grain", "expected"),
    [("day", "30-sep"), ("week", "Sem. 30-sep"), ("month", "sep 2026")],
)
def test_format_period(grain, expected):
    from src.dashboard.formatting import format_period

    assert format_period(date(2026, 9, 30), grain) == expected


def test_format_long_date():
    from src.dashboard.formatting import format_long_date

    assert format_long_date(date(2026, 9, 30)) == "miércoles 30 de septiembre de 2026"


def test_alert_card_escapes_and_separates_where_to_investigate():
    from src.dashboard.andon import alert_card_html
    from src.dashboard.formatting import alert_facts

    card = alert_card_html("L2 <test>", alert_facts(scrap_alert()))

    assert "L2 &lt;test&gt;" in card
    assert '<div class="alert-focus"><strong>Dónde investigar:</strong>' in card


def test_alert_message_names_the_evaluated_day_instead_of_ese_dia():
    message = alert_message(scrap_alert())

    assert "ese día" not in message
    assert "9.0% el 30-sep" in message or "el 30-sep" in message
    assert "115 piezas el 30-sep" in message


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 9, 1), date(2026, 9, 30), "del 1 al 30 de septiembre de 2026"),
        (date(2026, 8, 28), date(2026, 9, 3), "del 28 de agosto al 3 de septiembre de 2026"),
        (date(2025, 12, 29), date(2026, 1, 2), "del 29 de diciembre de 2025 al 2 de enero de 2026"),
        (date(2026, 9, 30), date(2026, 9, 30), "del 30 de septiembre de 2026"),
    ],
)
def test_format_date_range(start, end, expected):
    from src.dashboard.formatting import format_date_range

    assert format_date_range(start, end) == expected
