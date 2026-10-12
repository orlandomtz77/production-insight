"""User-facing text in Spanish: numbers (KPI Common Rules) and alert messages (REQ-012)."""

import math

from src.anomaly_detection.alerts import Alert
from src.anomaly_detection.baselines import METRICS
from src.anomaly_detection.priority import DOWNTIME, PROD, SCRAP, RECURRENCE_WINDOW

NOT_AVAILABLE = "N/A"
METRIC_LABELS = {metric.name: metric.label for metric in METRICS}
DIRECTION_TEXT = {PROD: "por debajo de lo normal", SCRAP: "por encima de lo normal", DOWNTIME: "por encima de lo normal"}


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def format_number(value) -> str:
    return NOT_AVAILABLE if _missing(value) else f"{value:,.0f}"


def format_percent(value) -> str:
    return NOT_AVAILABLE if _missing(value) else f"{value * 100:.1f}%"


def format_minutes(value) -> str:
    if _missing(value):
        return NOT_AVAILABLE
    text = f"{value:,.0f} min"
    return f"{text} ({value / 60:.1f} h)" if value >= 60 else text


def format_metric_value(metric: str, value, compact: bool = False) -> str:
    """Compact form for tables: '1,104 pzs/turno', '88 min/turno'."""
    if metric == SCRAP:
        return format_percent(value)
    if metric == DOWNTIME:
        return f"{format_number(value)} min/turno" if compact else format_minutes(value) + " por turno"
    if compact:
        return f"{format_number(value)} pzs/turno"
    return format_number(value) + " piezas por turno disponible"


def alert_title(alert: Alert) -> str:
    label = METRIC_LABELS[alert.metric]
    return f"{alert.line}: {label} {DIRECTION_TEXT[alert.metric]} ({alert.evaluated_day.isoformat()})"


def format_shifts(shifts: list[int]) -> str:
    """[2] → "turno 2"; [1, 2] → "turnos 1 y 2"; [1, 2, 3] → "turnos 1, 2 y 3"."""
    if len(shifts) == 1:
        return f"turno {shifts[0]}"
    numbers = [str(s) for s in shifts]
    return f"turnos {', '.join(numbers[:-1])} y {numbers[-1]}"


def investigation_text(alert: Alert) -> str:
    area = alert.investigation
    shifts = format_shifts(area.shifts)
    if alert.metric == SCRAP:
        return f"{area.focus} en {alert.line}, con scrap rate de {format_percent(area.value)} ese día ({shifts})."
    if alert.metric == DOWNTIME:
        return f"{area.focus}: {format_minutes(area.value)} ese día en {alert.line}, sobre todo en el {shifts}."
    cause = f"; causa principal de paro no programado: {area.focus}" if area.focus else ""
    return f"{shifts.capitalize()} de {alert.line} (producción más baja del día){cause}."


def alert_facts(alert: Alert) -> list[tuple[str, str]]:
    """The parts every alert must explain (CLAUDE.md §12), as (label, text)."""
    sign = "+" if alert.percent_deviation >= 0 else ""
    return [
        ("Valor actual", format_metric_value(alert.metric, alert.value)),
        ("Línea base",
         f"{format_metric_value(alert.metric, alert.baseline_mean)} (promedio de {alert.sample_size} "
         f"días hábiles, {alert.baseline_first_day.isoformat()} a {alert.baseline_last_day.isoformat()})"),
        ("Desviación", f"{sign}{alert.percent_deviation:.1f}% ({abs(alert.z):.1f} desviaciones estándar)"),
        ("Impacto",
         f"~{format_number(alert.daily_impact)} piezas ese día (~{format_number(alert.cumulative_impact)} "
         f"piezas en los últimos {RECURRENCE_WINDOW} días hábiles)"),
        ("Recurrencia", f"{alert.frequency} de los últimos {RECURRENCE_WINDOW} días hábiles"),
        ("Dónde investigar", investigation_text(alert)),
    ]


def alert_message(alert: Alert) -> str:
    return "\n".join(f"{label}: {text}" for label, text in alert_facts(alert))


MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
NOT_EVALUATED_REASONS = {
    "insufficient_history": "Historial insuficiente (menos de 10 días hábiles)",
    "no_variation": "Sin variación en la línea base",
    "no_production": "Sin producción en el día evaluado",
}
GRAIN_LABELS = {"day": "Día", "week": "Semana", "month": "Mes"}


def format_period(day, grain: str) -> str:
    """Period label in Spanish: day '30-sep', week 'Sem. 31-ago', month 'sep 2026'."""
    short = f"{day.day:02d}-{MONTHS[day.month - 1]}"
    if grain == "week":
        return f"Sem. {short}"
    if grain == "month":
        return f"{MONTHS[day.month - 1]} {day.year}"
    return short

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def format_long_date(day) -> str:
    """'miércoles 30 de septiembre de 2026'."""
    return f"{WEEKDAYS[day.weekday()]} {day.day} de {MONTH_NAMES[day.month - 1]} de {day.year}"
