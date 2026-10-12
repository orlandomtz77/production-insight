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


def format_metric_value(metric: str, value) -> str:
    if metric == SCRAP:
        return format_percent(value)
    if metric == DOWNTIME:
        return format_minutes(value) + " por turno"
    return format_number(value) + " piezas por turno disponible"


def alert_title(alert: Alert) -> str:
    label = METRIC_LABELS[alert.metric]
    return f"{alert.line} — {label} {DIRECTION_TEXT[alert.metric]} ({alert.evaluated_day.isoformat()})"


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
        return f"{area.focus} en {alert.line} — scrap rate {format_percent(area.value)} ese día ({shifts})."
    if alert.metric == DOWNTIME:
        return f"{area.focus} — {format_minutes(area.value)} ese día en {alert.line}, sobre todo en el {shifts}."
    cause = f"; causa principal de paro no programado: {area.focus}" if area.focus else ""
    return f"{shifts.capitalize()} de {alert.line} (producción más baja del día){cause}."


def alert_message(alert: Alert) -> str:
    sign = "+" if alert.percent_deviation >= 0 else ""
    return "\n".join(
        [
            f"Valor actual:  {format_metric_value(alert.metric, alert.value)}",
            f"Línea base:    {format_metric_value(alert.metric, alert.baseline_mean)} "
            f"(promedio de {alert.sample_size} días hábiles, "
            f"{alert.baseline_first_day.isoformat()} a {alert.baseline_last_day.isoformat()})",
            f"Desviación:    {sign}{alert.percent_deviation:.1f}% "
            f"({abs(alert.z):.1f} desviaciones estándar)",
            f"Impacto:       ~{format_number(alert.daily_impact)} piezas ese día "
            f"(~{format_number(alert.cumulative_impact)} piezas en los últimos {RECURRENCE_WINDOW} días hábiles)",
            f"Recurrencia:   {alert.frequency} de los últimos {RECURRENCE_WINDOW} días hábiles",
            f"Dónde investigar: {investigation_text(alert)}",
        ]
    )
