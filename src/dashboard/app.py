"""Streamlit dashboard (REQ-014). All text shown to the user is in Spanish.

Each visualization is introduced by the question it answers (CLAUDE.md §15).
The dashboard only displays results; every calculation lives in src/analytics
and src/anomaly_detection, where it is tested.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analytics.data_quality import build_data_quality_report
from src.analytics.kpis import KpiFilters, apply_filters, build_kpi_report, downtime_trend, scrap_trend
from src.anomaly_detection.alerts import run_alerts
from src.anomaly_detection.baselines import METRICS
from src.dashboard import charts
from src.dashboard.formatting import (
    GRAIN_LABELS,
    NOT_EVALUATED_REASONS,
    alert_message,
    alert_title,
    format_metric_value,
    format_minutes,
    format_long_date,
    format_number,
    format_percent,
    format_period,
)
from src.database import downtime_repository, production_repository
from src.database.connection import DEFAULT_DB_PATH, connect
from src.ingestion.load_downtime import load_downtime_file
from src.ingestion.load_production import load_production_file
from src.ingestion.master_data import MasterDataError, load_master_lists

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MASTER_DIR = PROJECT_ROOT / "data" / "master"
METRIC_LABELS = {metric.name: metric.label for metric in METRICS}
NO_DATA = "Cargue primero el CSV de producción y después el CSV de paros (barra lateral)."


def _theme_mode() -> str:
    theme = getattr(st.context, "theme", None)
    return "dark" if getattr(theme, "type", "light") == "dark" else "light"


def _question(text: str) -> None:
    st.markdown(f"**{text}**")


def _chart(fig) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# --- Sidebar ---------------------------------------------------------------------

def _upload_section(conn, master_dir) -> None:
    st.sidebar.header("Cargar datos")
    st.sidebar.caption("Primero producción, después paros.")
    uploads = [
        ("1. Producción (CSV)", "production_file", "Cargar producción", load_production_file, "Producción"),
        ("2. Paros (CSV)", "downtime_file", "Cargar paros", load_downtime_file, "Paros"),
    ]
    for label, key, button, loader, name in uploads:
        uploaded = st.sidebar.file_uploader(label, type="csv", key=key)
        if st.sidebar.button(button, disabled=uploaded is None, width="stretch"):
            st.session_state["last_load"] = (name, loader(uploaded, uploaded.name, conn, master_dir))


def _filters_section(production: pd.DataFrame, master) -> tuple[KpiFilters, str]:
    st.sidebar.header("Filtros")
    filters = KpiFilters()
    if not production.empty:
        first = pd.to_datetime(production["date"]).min().date()
        last = pd.to_datetime(production["date"]).max().date()
        period = st.sidebar.date_input("Periodo", value=(first, last), min_value=first, max_value=last)
        if isinstance(period, (tuple, list)) and period:
            filters.start, filters.end = period[0], period[-1]

    def multiselect(label, options):
        selected = st.sidebar.multiselect(label, options, default=options)
        return None if len(selected) == len(options) else selected

    filters.lines = multiselect("Línea", sorted(master.lines))
    filters.products = multiselect("Producto", sorted(master.products))
    filters.shifts = multiselect("Turno", [1, 2, 3])
    grain = st.sidebar.radio("Agrupar tendencias por", list(GRAIN_LABELS),
                             format_func=GRAIN_LABELS.get, horizontal=True, index=1)
    return filters, grain


# --- Load result -------------------------------------------------------------------

def _show_last_load() -> None:
    if "last_load" not in st.session_state:
        return
    name, result = st.session_state["last_load"]
    summary = result.summary
    with st.container(border=True):
        if summary.status == "rejected":
            st.error(f"Carga de {name.lower()} rechazada: {summary.file_name}")
            for message in result.file_errors:
                st.markdown(f"- {message}")
            return
        st.success(f"Carga de {name.lower()} completada: {summary.file_name}")
        cols = st.columns(5)
        cols[0].metric("Filas leídas", format_number(summary.rows_read))
        cols[1].metric("Filas guardadas", format_number(summary.rows_stored))
        cols[2].metric("Filas rechazadas", format_number(summary.rows_rejected))
        cols[3].metric("Turnos nuevos / reemplazados", f"{summary.shifts_new} / {summary.shifts_replaced}")
        cols[4].metric("Turnos rechazados", format_number(summary.shifts_rejected))
        for warning in result.warnings:
            st.warning(warning)
        if result.errors:
            errors = pd.DataFrame(
                [(e.row, e.column, e.value, e.reason) for e in result.errors],
                columns=["Fila", "Columna", "Valor", "Motivo"],
            )
            st.dataframe(errors, hide_index=True, width="stretch")
            st.download_button(
                "Descargar errores (CSV)",
                errors.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"errores_{summary.file_name}",
                mime="text/csv",
            )


# --- Tabs --------------------------------------------------------------------------

def _tab_summary(kpis, alert_report) -> None:
    cols = st.columns(4)
    cols[0].metric("Producción total", f"{format_number(kpis.production.total)} piezas")
    cols[1].metric("Scrap rate", format_percent(kpis.quality.scrap_rate))
    cols[2].metric("Paro no programado", f"{format_number(kpis.downtime.unplanned_total)} min",
                   help=format_minutes(kpis.downtime.unplanned_total))
    cols[3].metric("Alertas", len(alert_report.alerts))

    _question("¿Cuál es el problema más importante ahora?")
    if not alert_report.alerts:
        st.info("Ninguna línea se desvió de lo normal en el día evaluado.")
        return
    top = alert_report.alerts[0]
    st.warning(f"**Prioridad 1: {alert_title(top)}**  \n" + alert_message(top).replace("\n", "  \n"), icon="⚠️")


def _tab_alerts(alert_report, filters: KpiFilters) -> None:
    day = alert_report.evaluated_day
    st.caption(
        f"Día evaluado: {day.isoformat() if day else 'N/A'} (último día hábil con datos). "
        "El filtro de periodo no cambia las alertas; el filtro de línea sí."
    )
    alerts = [a for a in alert_report.alerts if filters.lines is None or a.line in filters.lines]

    _question("¿Qué problema debo investigar primero?")
    if not alerts:
        st.info("Ninguna línea se desvió de lo normal en el día evaluado.")
    else:
        table = pd.DataFrame(
            [
                {
                    "Prioridad": a.rank,
                    "Línea": a.line,
                    "Problema": METRIC_LABELS[a.metric],
                    "Valor actual": format_metric_value(a.metric, a.value, compact=True),
                    "Línea base": format_metric_value(a.metric, a.baseline_mean, compact=True),
                    "Desviación": f"{a.percent_deviation:+.1f}%",
                    "Impacto (pzs)": format_number(a.cumulative_impact),
                    "Recurrencia": f"{a.frequency} de 6 días",
                }
                for a in alerts
            ]
        )
        st.dataframe(table, hide_index=True, width="stretch")

        _question("¿Por qué se marcó y por dónde empiezo?")
        for alert in alerts:
            with st.expander(f"{alert.rank}. {alert_title(alert)}", expanded=alert.rank == 1):
                st.markdown(alert_message(alert).replace("\n", "  \n"))

    st.caption(
        "El puntaje de prioridad (impacto acumulado × recurrencia) es una herramienta de apoyo "
        "para decidir qué investigar primero; no es una medida absoluta de importancia."
    )

    _question("¿Falta algo en la evaluación?")
    not_evaluated = [n for n in alert_report.not_evaluated if filters.lines is None or n[0] in filters.lines]
    if not_evaluated:
        st.dataframe(
            pd.DataFrame(
                [(line, METRIC_LABELS[m], NOT_EVALUATED_REASONS[r]) for line, m, r in not_evaluated],
                columns=["Línea", "Métrica", "Motivo"],
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Todas las líneas y métricas fueron evaluadas.")


def _tab_production(kpis, mode) -> None:
    production = kpis.production
    _question("¿Qué línea produjo más y cuál menos?")
    _chart(charts.bar(production.by_line["line"], production.by_line["production"], mode,
                      hover_text=[f"{p:,.0f} piezas en {s} turnos" for p, s in
                                  zip(production.by_line["production"], production.by_line["shifts_worked"])]))
    left, right = st.columns(2)
    with left:
        _question("¿Qué productos concentran el volumen?")
        _chart(charts.bar(production.by_product["product"], production.by_product["production"], mode))
    with right:
        _question("¿Hay algún turno con menor producción?")
        _chart(charts.bar([f"Turno {s}" for s in production.by_shift["shift"]],
                          production.by_shift["production"], mode))


def _tab_quality(kpis, production_rows, colors, grain, mode) -> None:
    quality = kpis.quality
    _question("¿Qué línea tiene el scrap rate más alto?")
    _chart(charts.bar(quality.by_line["line"], quality.by_line["scrap_rate"], mode, percent=True,
                      hover_text=[f"{r:.1%} ({s:,.0f} piezas de scrap)" for r, s in
                                  zip(quality.by_line["scrap_rate"], quality.by_line["scrap"])]))
    left, right = st.columns(2)
    with left:
        _question("¿Qué producto tiene el scrap rate más alto?")
        _chart(charts.bar(quality.by_product["product"], quality.by_product["scrap_rate"], mode, percent=True))
    with right:
        _question("¿El scrap se concentra en un turno?")
        _chart(charts.bar([f"Turno {s}" for s in quality.by_shift["shift"]],
                          quality.by_shift["scrap_rate"], mode, percent=True))

    _question("¿El problema es recurrente o está empeorando?")
    trend = scrap_trend(production_rows, grain)
    labels = {p: format_period(p, grain) for p in trend["period"].unique()}
    _chart(charts.trend(trend, labels, "scrap_rate", colors, mode, percent=True))
    with st.expander("Ver datos"):
        st.dataframe(
            trend.assign(Periodo=trend["period"].map(labels), **{"Scrap rate": trend["scrap_rate"].map(format_percent)})
            [["Periodo", "line", "Scrap rate"]].rename(columns={"line": "Línea"}),
            hide_index=True, width="stretch",
        )

    _question("¿El problema está siempre en el mismo turno?")
    heat = quality.by_shift_week
    if not heat.empty:
        _chart(charts.heatmap(heat, [f"Turno {s}" for s in heat.index],
                              [format_period(w, "week") for w in heat.columns], mode))
        st.caption("Cada semana empieza en lunes; la primera y la última pueden estar incompletas. "
                   "Celda vacía: el turno no trabajó esa semana.")


def _tab_downtime(kpis, production_rows, events, planned_reasons, colors, grain, mode) -> None:
    downtime = kpis.downtime
    _question("¿Cuánto paro es una pérdida real?")
    cols = st.columns(3)
    cols[0].metric("Paro no programado", f"{format_number(downtime.unplanned_total)} min",
                   help=format_minutes(downtime.unplanned_total))
    cols[1].metric("Paro programado", f"{format_number(downtime.planned_total)} min",
                   help=format_minutes(downtime.planned_total))
    cols[2].metric("Promedio no programado por turno", format_minutes(downtime.average_unplanned_per_shift))

    _question("¿Qué línea tuvo más paro no programado?")
    _chart(charts.bar(downtime.by_line["line"], downtime.by_line["downtime"], mode))

    _question("¿Cuáles son las principales causas de paro?")
    by_cause = downtime.by_cause
    palette = charts.PALETTE[mode]
    _chart(charts.bar(
        by_cause["downtime_reason"], by_cause["minutes"], mode,
        colors=[palette["muted"] if p else palette["series"][0] for p in by_cause["planned"]],
        hover_text=[f"{m:,.0f} min · {e} eventos · {pct:.1%} del total · {'programado' if p else 'no programado'}"
                    for m, e, pct, p in zip(by_cause["minutes"], by_cause["events"], by_cause["percent"], by_cause["planned"])],
    ))
    st.caption("Azul: paro no programado (pérdida). Gris: paro programado (mantenimiento preventivo, juntas, limpieza).")

    left, right = st.columns(2)
    with left:
        _question("¿El paro se concentra en un turno?")
        _chart(charts.bar([f"Turno {s}" for s in downtime.by_shift["shift"]], downtime.by_shift["downtime"], mode))
    with right:
        _question("¿El paro se concentra en un producto?")
        _chart(charts.bar(downtime.by_product["product"], downtime.by_product["downtime"], mode))

    _question("¿El paro no programado está aumentando?")
    trend = downtime_trend(production_rows, events, planned_reasons, grain)
    labels = {p: format_period(p, grain) for p in trend["period"].unique()}
    _chart(charts.trend(trend, labels, "downtime_per_shift", colors, mode, unit=" min"))
    with st.expander("Ver datos"):
        st.dataframe(
            trend.assign(Periodo=trend["period"].map(labels),
                         **{"Min. por turno": trend["downtime_per_shift"].round(1)})
            [["Periodo", "line", "Min. por turno"]].rename(columns={"line": "Línea"}),
            hide_index=True, width="stretch",
        )


def _tab_data_quality(report) -> None:
    coverage = report.coverage
    _question("¿Puedo confiar en los KPIs? ¿Faltan datos?")
    cols = st.columns(4)
    cols[0].metric("Cobertura", format_percent(coverage.coverage_percent / 100))
    cols[1].metric("Turnos faltantes", len(coverage.missing_shifts))
    cols[2].metric("Turnos extra", len(coverage.overtime_shifts),
                   help="Turnos con datos que no se esperaban: domingo o día en paro programado.")
    cols[3].metric("Turnos en paro programado", coverage.planned_stop_shifts)
    st.caption(
        f"Periodo {coverage.period_start.isoformat()} a {coverage.period_end.isoformat()}: "
        f"{coverage.covered_shifts} de {coverage.expected_shifts} turnos esperados (lunes a sábado) tienen datos."
    )
    shift_table = lambda keys: pd.DataFrame(keys, columns=["Fecha", "Línea", "Turno"])
    if coverage.missing_shifts:
        with st.expander(f"Turnos faltantes ({len(coverage.missing_shifts)}): datos faltantes, no errores"):
            st.dataframe(shift_table(coverage.missing_shifts), hide_index=True, width="stretch")
    if coverage.overtime_shifts:
        with st.expander(f"Turnos extra ({len(coverage.overtime_shifts)})"):
            st.dataframe(shift_table(coverage.overtime_shifts), hide_index=True, width="stretch")
    for message in report.planned_stops_invalid:
        st.warning(f"Calendario de paros programados: {message}")

    _question("¿Hay paros sin registro de producción?")
    if report.orphan_events.empty:
        st.caption("No hay paros huérfanos.")
    else:
        st.warning(f"{len(report.orphan_events)} paros no tienen registro de producción y se excluyen de los KPIs. "
                   "Recargue el CSV de paros de esos turnos.")
        st.dataframe(report.orphan_events.rename(columns={
            "date": "Fecha", "line": "Línea", "shift": "Turno", "product": "Producto",
            "downtime_minutes": "Minutos", "downtime_reason": "Causa"}), hide_index=True, width="stretch")

    _question("¿Qué se cargó, cuándo y con qué resultado?")
    history = report.load_history.rename(columns={
        "loaded_at": "Fecha de carga", "file_type": "Tipo", "file_name": "Archivo", "rows_read": "Leídas",
        "rows_stored": "Guardadas", "rows_rejected": "Rechazadas", "shifts_replaced": "Turnos reemplazados",
        "shifts_new": "Turnos nuevos", "shifts_rejected": "Turnos rechazados", "warnings": "Advertencias",
        "status": "Estado"})
    history["Tipo"] = history["Tipo"].map({"production": "Producción", "downtime": "Paros"})
    history["Estado"] = history["Estado"].map({"completed": "Completada", "rejected": "Rechazada"})
    st.dataframe(history.drop(columns=["id"]), hide_index=True, width="stretch")


# --- Main --------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Production Insight", page_icon="🏭", layout="wide")
    db_path = Path(os.environ.get("PRODUCTION_INSIGHT_DB", DEFAULT_DB_PATH))
    master_dir = Path(os.environ.get("PRODUCTION_INSIGHT_MASTER_DIR", DEFAULT_MASTER_DIR))

    st.title("Production Insight")

    try:
        master = load_master_lists(master_dir)
    except MasterDataError as error:
        st.error(f"No se pudieron leer las listas maestras: {error}")
        return

    conn = connect(db_path)
    try:
        _upload_section(conn, master_dir)
        all_production = production_repository.read_all(conn)
        filters, grain = _filters_section(all_production, master)
        _show_last_load()

        if all_production.empty:
            st.info(NO_DATA)
            return

        mode = _theme_mode()
        colors = charts.line_colors(master.lines, mode)
        kpis = build_kpi_report(conn, master_dir, filters)
        alert_report = run_alerts(conn, master_dir)
        quality_report = build_data_quality_report(conn, master_dir)
        production_rows = apply_filters(all_production, filters)
        events = apply_filters(downtime_repository.read_linked_events(conn), filters)

        day = alert_report.evaluated_day
        if day:
            st.caption(f"Revisión del {format_long_date(day)}, último día hábil con datos. "
                       "Dónde investigar primero y por qué.")
        if kpis.orphans_excluded:
            st.caption(f"{kpis.orphans_excluded} paros sin registro de producción se excluyen de los KPIs "
                       "(ver Calidad de datos).")

        tabs = st.tabs(["Resumen", "Alertas", "Producción", "Calidad", "Paros", "Calidad de datos"])
        with tabs[5]:
            _tab_data_quality(quality_report)
        with tabs[1]:
            _tab_alerts(alert_report, filters)
        if not kpis.has_data:
            for tab in (tabs[0], tabs[2], tabs[3], tabs[4]):
                tab.info("No hay datos para estos filtros.")
            return
        with tabs[0]:
            _tab_summary(kpis, alert_report)
        with tabs[2]:
            _tab_production(kpis, mode)
        with tabs[3]:
            _tab_quality(kpis, production_rows, colors, grain, mode)
        with tabs[4]:
            _tab_downtime(kpis, production_rows, events, master.planned_reasons, colors, grain, mode)
    finally:
        conn.close()
