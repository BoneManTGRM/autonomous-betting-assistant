from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import combined_rows, hash_rows, rows_from_csv_bytes, run_adaptive_repair_scan, system_source_adapters, uploaded_source
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.reparodynamics_audit import write_reparodynamics_audit_event_from_runner_report
from autonomous_betting_agent.reparodynamics_repair_memory import load_repair_memory, repair_memory_to_frames, save_repair_memory, stable_memory_run_id, update_repair_memory
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Shadow Mode Results", layout="wide")
LANG = render_app_sidebar("shadow_mode_results", language_key="shadow_mode_results_language", selector="radio")

TEXT = {
    "en": {
        "title": "Shadow Mode Results",
        "caption": "Phase 3C Shadow Backtest comparison. Live behavior stays unchanged.",
        "warning": "Shadow Mode results are simulation-only. Live behavior was not changed.",
        "memory_warning": "Saving to Repair Memory stores simulation summaries only. It does not change live picks or stored proof data.",
        "include_system": "Include available local system sources",
        "workspace": "Workspace ID",
        "upload": "Optional graded CSV for Shadow Backtest",
        "uploaded": "Uploaded rows loaded",
        "run": "Run Shadow Backtest comparison",
        "save_memory": "Save to Repair Memory",
        "saved_memory": "Saved to Repair Memory. No live repairs were activated.",
        "already_saved": "Already saved to Repair Memory.",
        "memory_preview": "Repair Memory Preview",
        "open_reparodynamics": "Open Reparodynamics page",
        "baseline": "Baseline Metrics",
        "comparison": "Shadow Backtest Comparison",
        "blockers": "Data Blockers",
        "watchlists": "Watchlists",
        "rejected": "Rejected Repairs",
        "manual": "Manual Review Queue",
        "safety": "Safety Gates",
        "no_data": "Run a Shadow Backtest scan to show results.",
        "empty": "No rows in this section.",
        "audit_written": "Audit event written. Live mutation remains forbidden.",
        "rows": "Rows",
        "completed": "Completed",
        "manual_review": "Manual Review",
        "live_repairs": "Live Repairs",
    },
    "es": {
        "title": "Resultados Shadow Mode",
        "caption": "Comparacion Shadow Backtest Fase 3C. El comportamiento en vivo no cambia.",
        "warning": "Los resultados de Shadow Mode son solo simulacion. El comportamiento en vivo no cambio.",
        "memory_warning": "Guardar en Repair Memory almacena solo resumenes de simulacion. No cambia picks en vivo ni datos de prueba guardados.",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "workspace": "ID del espacio de trabajo",
        "upload": "CSV calificado opcional para Shadow Backtest",
        "uploaded": "Filas subidas cargadas",
        "run": "Ejecutar comparacion Shadow Backtest",
        "save_memory": "Guardar en Repair Memory",
        "saved_memory": "Guardado en Repair Memory. No se activaron reparaciones en vivo.",
        "already_saved": "Ya guardado en Repair Memory.",
        "memory_preview": "Vista previa de Repair Memory",
        "open_reparodynamics": "Abrir pagina Reparodynamics",
        "baseline": "Metricas baseline",
        "comparison": "Comparacion Shadow Backtest",
        "blockers": "Bloqueadores de datos",
        "watchlists": "Listas de observacion",
        "rejected": "Reparaciones rechazadas",
        "manual": "Cola de revision manual",
        "safety": "Compuertas de seguridad",
        "no_data": "Ejecuta un escaneo Shadow Backtest para mostrar resultados.",
        "empty": "No hay filas en esta seccion.",
        "audit_written": "Evento de auditoria escrito. La mutacion en vivo sigue prohibida.",
        "rows": "Filas",
        "completed": "Completadas",
        "manual_review": "Revision manual",
        "live_repairs": "Reparaciones en vivo",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def display_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    return localize_dataframe(frame, LANG) if frame is not None else None


def show_table(rows: Any) -> None:
    frame = pd.DataFrame(list(rows or []))
    if frame.empty:
        st.info(t("empty"))
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def show_frame(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info(t("empty"))
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def one_row(data: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([data])


def flat(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in rows or []:
        comparison = item.get("comparison_metrics", {}) or {}
        out.append(
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
                "model_training": item.get("model_training", "FORBIDDEN"),
                "stored_data_mutation": item.get("stored_data_mutation", "FORBIDDEN"),
            }
        )
    return out


def scan_rows(uploaded_rows: list[dict[str, Any]] | None, uploaded_name: str, include_system: bool) -> list[dict[str, Any]]:
    sources = []
    if uploaded_rows is not None:
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=hash_rows(uploaded_rows), source_path=uploaded_name))
    if include_system:
        sources.extend(system_source_adapters())
    return combined_rows(sources)


st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.info(t("memory_warning"))
st.page_link("pages/reparodynamics.py", label=t("open_reparodynamics"))

workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state["aba_test_window_id"] = workspace_id
include_system = st.checkbox(t("include_system"), value=True)
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "shadow_mode_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="shadow_mode_results_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('uploaded')}: {len(uploaded_rows)}")
    st.dataframe(display_frame(pd.DataFrame(uploaded_rows).head(50)), use_container_width=True)

if st.button(t("run"), type="primary"):
    phase3c_report = build_phase3c_report(scan_rows(uploaded_rows, uploaded_name, include_system))
    phase3c_report["memory_run_id"] = stable_memory_run_id(phase3c_report)
    runner_report = run_adaptive_repair_scan(uploaded_rows=uploaded_rows, uploaded_filename=uploaded_name, uploaded_bytes=uploaded_bytes, include_system_sources=include_system)
    write_reparodynamics_audit_event_from_runner_report(runner_report, source="Shadow Mode Results page", phase3c_report=phase3c_report)
    st.session_state["phase3c_latest_report"] = phase3c_report
    st.session_state["shadow_mode_latest_report"] = runner_report.to_dict()
    st.success(t("audit_written"))

report = st.session_state.get("phase3c_latest_report")
if report:
    memory = load_repair_memory(workspace_id)
    run_id = str(report.get("memory_run_id") or stable_memory_run_id(report))
    if run_id in set(str(item) for item in memory.get("saved_run_ids", [])):
        st.info(t("already_saved"))
    elif st.button(t("save_memory")):
        report["memory_run_id"] = run_id
        memory = update_repair_memory(memory, report, source="Shadow Mode Results page")
        memory = save_repair_memory(memory, workspace_id)
        st.session_state["phase3d_repair_memory"] = memory
        if memory.get("last_save_status") == "already_saved":
            st.info(t("already_saved"))
        else:
            st.success(t("saved_memory"))

if not report:
    st.info(t("no_data"))
else:
    counts = dict(report.get("summary_counts", {}) or {})
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(t("rows"), report.get("rows_scanned", 0))
    c2.metric(t("completed"), report.get("completed_rows_used", 0))
    c3.metric(t("blockers"), counts.get("data_blockers_count", 0))
    c4.metric(t("watchlists"), counts.get("watchlists_count", 0))
    c5.metric(t("manual_review"), counts.get("manual_review_eligible_count", 0))
    c6.metric(t("live_repairs"), counts.get("live_repairs_applied_count", 0))
    tabs = st.tabs([t("baseline"), t("comparison"), t("blockers"), t("watchlists"), t("rejected"), t("manual"), t("safety"), t("memory_preview")])
    with tabs[0]:
        st.dataframe(display_frame(one_row(report.get("baseline_metrics", {}) or {})), use_container_width=True, hide_index=True)
    with tabs[1]:
        show_table(flat(list(report.get("shadow_tested_repairs", []) or [])))
    with tabs[2]:
        show_table(report.get("data_blockers", []))
    with tabs[3]:
        show_table(report.get("watchlists", []))
    with tabs[4]:
        show_table(report.get("rejected_repairs", []))
    with tabs[5]:
        show_table(report.get("manual_review_queue", []))
    with tabs[6]:
        st.dataframe(display_frame(one_row(report.get("safety_gates", {}) or {})), use_container_width=True, hide_index=True)
    with tabs[7]:
        memory = st.session_state.get("phase3d_repair_memory") or load_repair_memory(workspace_id)
        frames = repair_memory_to_frames(memory)
        show_frame(frames["summary"])
