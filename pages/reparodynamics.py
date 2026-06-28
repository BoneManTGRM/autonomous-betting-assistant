from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import (
    combined_rows,
    hash_rows,
    rows_from_csv_bytes,
    run_adaptive_repair_scan,
    system_source_adapters,
    uploaded_source,
)
from autonomous_betting_agent.local_storage_import import save_reparodynamics_rows_to_research
from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_runner_report,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_value, tr

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "Measured self-repair doctrine and Phase 3C Shadow Backtest control panel.",
        "warning": "Phase 3C is Shadow Backtest only. No live model, odds, proof ledger, stake, EV, bankroll, or prediction behavior is changed.",
        "storage_warning": "Local storage may not persist across redeploys unless persistent storage is configured. Use exports for long-term proof backup.",
        "save_warning": "Saving scan rows here only stores research rows locally. It does not train the model, change live picks, or activate Reparodynamics repairs.",
        "phase": "Current phase",
        "mode": "Operating mode",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "live_repairs": "Repairs Applied LIVE",
        "model_training": "Model Training",
        "stored_data": "Stored Data Mutation",
        "controls": "Phase 3C scan controls",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for this scan",
        "loaded": "Loaded uploaded rows",
        "save_scan": "Also save scanned rows to Local Control Center research ledger",
        "save_confirm": "I understand this saves scan rows locally only and does not train or mutate the model",
        "run": "Run Phase 3C Shadow Backtest",
        "success": "Phase 3C Shadow Backtest completed. Audit event written.",
        "saved": "Rows saved to research ledger",
        "not_saved": "No scan rows were saved to local storage.",
        "no_run": "Run a Phase 3C scan to show Shadow Backtest tables.",
        "summary": "Phase 3C Summary",
        "blockers": "Data Blockers",
        "watchlists": "Watchlists",
        "candidates": "Repair Candidates",
        "comparison": "Shadow Backtest Comparison",
        "manual": "Manual Review Queue",
        "safety": "Safety Gates",
        "audit": "Audit",
        "latest_audit": "Latest audit event",
        "empty": "No rows in this section.",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Doctrina de autorreparacion medida y panel de Shadow Backtest Fase 3C.",
        "warning": "Fase 3C es solo Shadow Backtest. No se cambia el modelo en vivo, cuotas, ledger de prueba, stake, EV, bankroll ni predicciones.",
        "storage_warning": "El almacenamiento local puede no persistir entre redeploys si no hay almacenamiento persistente configurado. Usa exportaciones como respaldo de prueba a largo plazo.",
        "save_warning": "Guardar filas aqui solo almacena filas de investigacion localmente. No entrena el modelo, no cambia picks en vivo ni activa reparaciones Reparodynamics.",
        "phase": "Fase actual",
        "mode": "Modo operativo",
        "repair": "Activacion de reparacion",
        "shadow": "Shadow Mode",
        "live_repairs": "Reparaciones aplicadas EN VIVO",
        "model_training": "Entrenamiento del modelo",
        "stored_data": "Mutacion de datos guardados",
        "controls": "Controles de escaneo Fase 3C",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para este escaneo",
        "loaded": "Filas subidas cargadas",
        "save_scan": "Tambien guardar filas escaneadas en el ledger de investigacion de Local Control Center",
        "save_confirm": "Entiendo que esto solo guarda filas localmente y no entrena ni muta el modelo",
        "run": "Ejecutar Shadow Backtest Fase 3C",
        "success": "Shadow Backtest Fase 3C completado. Evento de auditoria escrito.",
        "saved": "Filas guardadas en ledger de investigacion",
        "not_saved": "No se guardaron filas de escaneo en almacenamiento local.",
        "no_run": "Ejecuta un escaneo Fase 3C para mostrar las tablas de Shadow Backtest.",
        "summary": "Resumen Fase 3C",
        "blockers": "Bloqueadores de datos",
        "watchlists": "Listas de observacion",
        "candidates": "Candidatos de reparacion",
        "comparison": "Comparacion Shadow Backtest",
        "manual": "Cola de revision manual",
        "safety": "Compuertas de seguridad",
        "audit": "Auditoria",
        "latest_audit": "Ultimo evento de auditoria",
        "empty": "No hay filas en esta seccion.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def metric_value(value: Any) -> str:
    localized = str(localize_value(value, LANG))
    if str(value).strip().upper() in {"ON", "OFF", "FORBIDDEN"}:
        return localized.upper()
    return localized


def display_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None:
        return None
    return localize_dataframe(frame, LANG)


def show_table(rows: Any) -> None:
    frame = pd.DataFrame(list(rows or []))
    if frame.empty:
        st.info(t("empty"))
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def frame_from_mapping(data: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([data])


def flatten_shadow_tests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in rows or []:
        comparison = item.get("comparison_metrics", {}) or {}
        flattened.append(
            {
                "title": item.get("title", ""),
                "finding_type": item.get("finding_type", ""),
                "candidate_type": item.get("candidate_type", ""),
                "sample_size": item.get("sample_size", 0),
                "baseline_ROI": comparison.get("baseline_ROI"),
                "shadow_ROI": comparison.get("shadow_ROI"),
                "ROI_delta": comparison.get("ROI_delta"),
                "baseline_profit_units": comparison.get("baseline_profit_units"),
                "shadow_profit_units": comparison.get("shadow_profit_units"),
                "profit_units_delta": comparison.get("profit_units_delta"),
                "baseline_losses": comparison.get("baseline_losses"),
                "shadow_losses": comparison.get("shadow_losses"),
                "losses_delta": comparison.get("losses_delta"),
                "decision": item.get("decision", ""),
                "decision_reason": item.get("decision_reason", ""),
                "eligible_for_manual_review": item.get("eligible_for_manual_review", False),
                "live_mutation": item.get("live_mutation", "FORBIDDEN"),
            }
        )
    return flattened


def build_scan_rows(uploaded_rows: list[dict[str, Any]] | None, uploaded_name: str, include_system: bool) -> list[dict[str, Any]]:
    sources = []
    if uploaded_rows is not None:
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=hash_rows(uploaded_rows), source_path=uploaded_name))
    if include_system:
        sources.extend(system_source_adapters())
    return combined_rows(sources)


doctrine = get_reparodynamics_doctrine()

st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.info(t("storage_warning"))
st.page_link("pages/shadow_mode_results.py", label=t("comparison"))

cols = st.columns(6)
cols[0].metric(t("phase"), metric_value(doctrine.get("current_phase", "")))
cols[1].metric(t("shadow"), metric_value(doctrine.get("shadow_mode_activation", "ON")))
cols[2].metric(t("repair"), metric_value(doctrine.get("repair_activation", "OFF")))
cols[3].metric(t("live_repairs"), int(doctrine.get("repairs_applied_live", 0) or 0))
cols[4].metric(t("model_training"), metric_value(doctrine.get("model_training", "FORBIDDEN")))
cols[5].metric(t("stored_data"), metric_value(doctrine.get("stored_data_mutation", "FORBIDDEN")))

st.subheader(t("controls"))
st.caption(t("save_warning"))
include_system = st.checkbox(t("include_system"), value=True)
save_scan_rows = st.checkbox(t("save_scan"), value=False, key="reparodynamics_save_scan_rows")
save_confirmed = st.checkbox(t("save_confirm"), value=False, key="reparodynamics_save_confirmed")
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_phase3c_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('loaded')}: {len(uploaded_rows)}")
    st.dataframe(display_frame(pd.DataFrame(uploaded_rows).head(50)), use_container_width=True)

if st.button(t("run"), type="primary"):
    scan_rows = build_scan_rows(uploaded_rows, uploaded_name, include_system)
    phase3c_report = build_phase3c_report(scan_rows)
    runner_report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    write_reparodynamics_audit_event_from_runner_report(runner_report, source="Reparodynamics Phase 3C scan", phase3c_report=phase3c_report)
    st.session_state["phase3c_latest_report"] = phase3c_report
    st.session_state["shadow_mode_latest_report"] = runner_report.to_dict()
    st.success(t("success"))
    if save_scan_rows:
        rows_to_save = uploaded_rows or []
        if rows_to_save and save_confirmed:
            save_result = save_reparodynamics_rows_to_research(rows_to_save, run_id=runner_report.run_id, filename=uploaded_name, confirmed=True)
            st.success(f"{t('saved')}: {save_result['rows_imported']} ({save_result['rows_skipped_duplicate']} duplicate)")
        elif rows_to_save and not save_confirmed:
            st.warning(t("not_saved"))
        else:
            st.info(t("not_saved"))

phase3c = st.session_state.get("phase3c_latest_report")

if phase3c:
    counts = dict(phase3c.get("summary_counts", {}) or {})
    metric_cols = st.columns(7)
    metric_cols[0].metric(t("summary"), phase3c.get("rows_scanned", 0))
    metric_cols[1].metric(t("blockers"), counts.get("data_blockers_count", 0))
    metric_cols[2].metric(t("watchlists"), counts.get("watchlists_count", 0))
    metric_cols[3].metric(t("candidates"), counts.get("repair_candidates_count", 0))
    metric_cols[4].metric(t("comparison"), counts.get("shadow_tested_repairs_count", 0))
    metric_cols[5].metric(t("manual"), counts.get("manual_review_eligible_count", 0))
    metric_cols[6].metric(t("live_repairs"), counts.get("live_repairs_applied_count", 0))

    tabs = st.tabs([t("summary"), t("blockers"), t("watchlists"), t("candidates"), t("comparison"), t("manual"), t("safety"), t("audit")])
    with tabs[0]:
        st.dataframe(display_frame(frame_from_mapping(phase3c.get("baseline_metrics", {}) or {})), use_container_width=True, hide_index=True)
        st.json(phase3c.get("summary_counts", {}))
    with tabs[1]:
        show_table(phase3c.get("data_blockers", []))
    with tabs[2]:
        show_table(phase3c.get("watchlists", []))
    with tabs[3]:
        show_table(phase3c.get("repair_candidates", []))
    with tabs[4]:
        show_table(flatten_shadow_tests(list(phase3c.get("shadow_tested_repairs", []) or [])))
    with tabs[5]:
        show_table(phase3c.get("manual_review_queue", []))
    with tabs[6]:
        st.dataframe(display_frame(frame_from_mapping(phase3c.get("safety_gates", {}) or {})), use_container_width=True, hide_index=True)
    with tabs[7]:
        latest = latest_reparodynamics_audit_event()
        if latest is None:
            st.info(t("no_run"))
        else:
            st.dataframe(display_frame(pd.DataFrame(audit_event_display_rows(latest))), use_container_width=True, hide_index=True)
else:
    st.info(t("no_run"))
    latest = latest_reparodynamics_audit_event()
    if latest is not None:
        st.subheader(t("latest_audit"))
        st.dataframe(display_frame(pd.DataFrame(audit_event_display_rows(latest))), use_container_width=True, hide_index=True)

st.success(str(localize_value(doctrine.get("final_rule", ""), LANG)))
