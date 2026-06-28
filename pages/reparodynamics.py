from __future__ import annotations

import re
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
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_runner_report,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.reparodynamics_repair_memory import (
    load_repair_memory,
    manual_review_decision,
    repair_memory_to_frames,
    save_repair_memory,
    stable_memory_run_id,
    update_repair_memory,
)
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "Phase 3D Repair Memory + Manual Review Gate. Live behavior stays unchanged.",
        "warning": "Phase 3D stores Shadow Backtest memory only. No live model, odds, proof ledger, stake, EV, bankroll, or prediction behavior is changed.",
        "storage_warning": "Repair Memory stores simulation summaries separately from proof data. Manual approval does not activate live repairs.",
        "save_warning": "Saving scan rows here only stores research rows locally. It does not train the model, change live picks, or activate Reparodynamics repairs.",
        "phase": "Current phase",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "live_repairs": "Repairs Applied LIVE",
        "model_training": "Model Training",
        "stored_data": "Stored Data Mutation",
        "manual_review": "Manual Review",
        "lockbox": "Phase 4 Lockbox",
        "workspace": "Workspace ID",
        "controls": "Phase 3D scan controls",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for this scan",
        "loaded": "Loaded uploaded rows",
        "save_scan": "Also save scanned rows to Local Control Center research ledger",
        "save_confirm": "I understand this saves scan rows locally only and does not train or mutate the model",
        "run": "Run Phase 3C Shadow Backtest + save to Repair Memory",
        "success": "Shadow Backtest completed and saved to Repair Memory. Audit event written.",
        "save_memory": "Save Phase 3C results to Repair Memory",
        "already_saved": "Already saved to Repair Memory.",
        "memory_saved": "Phase 3C results saved to Repair Memory.",
        "saved": "Rows saved to research ledger",
        "not_saved": "No scan rows were saved to local storage.",
        "no_run": "Run a scan to show Shadow Backtest tables.",
        "phase3c_summary": "Phase 3C Summary",
        "memory": "Phase 3D Repair Memory",
        "manual_gate": "Manual Review Gate",
        "drilldown": "Repair Drilldown",
        "blockers": "Data Blockers",
        "watchlists": "Watchlists",
        "candidates": "Repair Candidates",
        "comparison": "Shadow Backtest Comparison",
        "safety": "Safety Gates",
        "audit": "Audit",
        "latest_audit": "Latest audit event",
        "empty": "No rows in this section.",
        "items_tracked": "Memory items tracked",
        "promising": "Promising repairs",
        "rejected": "Rejected repairs",
        "data_blocked": "Data-blocked repairs",
        "approved": "Manual-approved future repairs",
        "phase4": "Phase 4 lockbox candidates",
        "review_repair": "Repair key",
        "review_action": "Manual decision",
        "review_note": "Manual note",
        "reviewer": "Reviewer",
        "apply_review": "Save manual review decision",
        "review_saved": "Manual review decision saved. No live repairs were activated.",
        "manual_warning": "Manual approval does not activate live repairs.",
        "github_memory": "GitHub Repair Memory persistence",
        "final_rule": "ABA may store repair memory and manual review labels, but live repair remains forbidden.",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Memoria de reparacion Fase 3D + compuerta de revision manual. El comportamiento en vivo no cambia.",
        "warning": "Fase 3D solo guarda memoria de Shadow Backtest. No se cambia el modelo en vivo, cuotas, ledger de prueba, stake, EV, bankroll ni predicciones.",
        "storage_warning": "Repair Memory guarda resumenes de simulacion separados de los datos de prueba. La aprobacion manual no activa reparaciones en vivo.",
        "save_warning": "Guardar filas aqui solo almacena filas de investigacion localmente. No entrena el modelo, no cambia picks en vivo ni activa reparaciones Reparodynamics.",
        "phase": "Fase actual",
        "repair": "Activacion de reparacion",
        "shadow": "Shadow Mode",
        "live_repairs": "Reparaciones aplicadas EN VIVO",
        "model_training": "Entrenamiento del modelo",
        "stored_data": "Mutacion de datos guardados",
        "manual_review": "Revision manual",
        "lockbox": "Lockbox Fase 4",
        "workspace": "ID del espacio de trabajo",
        "controls": "Controles de escaneo Fase 3D",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para este escaneo",
        "loaded": "Filas subidas cargadas",
        "save_scan": "Tambien guardar filas escaneadas en el ledger de investigacion de Local Control Center",
        "save_confirm": "Entiendo que esto solo guarda filas localmente y no entrena ni muta el modelo",
        "run": "Ejecutar Shadow Backtest Fase 3C y guardar en Repair Memory",
        "success": "Shadow Backtest completado y guardado en Repair Memory. Evento de auditoria escrito.",
        "save_memory": "Guardar resultados Fase 3C en memoria de reparacion",
        "already_saved": "Ya guardado en Repair Memory.",
        "memory_saved": "Resultados Fase 3C guardados en Repair Memory.",
        "saved": "Filas guardadas en ledger de investigacion",
        "not_saved": "No se guardaron filas de escaneo en almacenamiento local.",
        "no_run": "Ejecuta un escaneo para mostrar las tablas de Shadow Backtest.",
        "phase3c_summary": "Resumen Fase 3C",
        "memory": "Memoria de reparacion Fase 3D",
        "manual_gate": "Compuerta de revision manual",
        "drilldown": "Detalle de reparacion",
        "blockers": "Bloqueadores de datos",
        "watchlists": "Listas de observacion",
        "candidates": "Candidatos de reparacion",
        "comparison": "Comparacion Shadow Backtest",
        "safety": "Compuertas de seguridad",
        "audit": "Auditoria",
        "latest_audit": "Ultimo evento de auditoria",
        "empty": "No hay filas en esta seccion.",
        "items_tracked": "Memorias rastreadas",
        "promising": "Reparaciones prometedoras",
        "rejected": "Reparaciones rechazadas",
        "data_blocked": "Reparaciones bloqueadas por datos",
        "approved": "Reparaciones futuras aprobadas manualmente",
        "phase4": "Candidatos lockbox Fase 4",
        "review_repair": "Clave de reparacion",
        "review_action": "Decision manual",
        "review_note": "Nota manual",
        "reviewer": "Revisor",
        "apply_review": "Guardar decision de revision manual",
        "review_saved": "Decision de revision manual guardada. No se activaron reparaciones en vivo.",
        "manual_warning": "La aprobacion manual no activa reparaciones en vivo.",
        "github_memory": "Persistencia GitHub de Repair Memory",
        "final_rule": "ABA puede guardar memoria de reparacion y etiquetas de revision manual, pero la reparacion en vivo sigue prohibida.",
    },
}

PAGE_COLUMN_LABELS_ES = {
    "field": "Campo",
    "value": "Valor",
    "description": "Descripcion",
    "created_at_utc": "Creado UTC",
    "created at utc": "Creado UTC",
    "event_id": "ID de evento",
    "event id": "ID de evento",
    "event_type": "Tipo de evento",
    "event type": "Tipo de evento",
    "memory_run_id": "ID de corrida de memoria",
    "repair_key": "Clave de reparacion",
    "repair key": "Clave de reparacion",
    "reviewer": "Revisor",
    "section": "Seccion",
    "source": "Fuente",
    "memory_status": "Estado de memoria",
    "manual_status": "Estado manual",
    "manual_note": "Nota manual",
    "latest_decision": "Decision mas reciente",
    "latest_decision_reason": "Razon mas reciente",
    "times_seen": "Veces detectado",
    "times_shadow_tested": "Veces probado en Shadow",
    "times_data_blocked": "Veces bloqueado por datos",
    "times_watchlist": "Veces en lista de observacion",
    "times_rejected": "Veces rechazado",
    "total_completed_rows_used": "Filas completadas totales",
    "avg_ROI_delta": "Cambio ROI promedio",
    "total_profit_units_delta": "Cambio total en unidades de ganancia",
    "total_avoided_losses": "Derrotas evitadas totales",
    "duplicate_skipped": "Duplicado omitido",
    "rows_added": "Filas agregadas",
}

PAGE_VALUE_LABELS_ES = {
    "aba_may_store_repair_memory_and_manual_review_labels_but_live_repair_remains_forbidden": "ABA puede guardar memoria de reparacion y etiquetas de revision manual, pero la reparacion en vivo sigue prohibida.",
    "closing_odds_or_comparable_clv_data_are_unavailable_for_clv_based_evaluation": "No hay cuotas de cierre o datos CLV comparables para evaluacion basada en CLV.",
    "rows_are_missing_decimal_odds_needed_for_price_based_simulation": "Faltan cuotas decimales necesarias para simulacion basada en precio.",
    "dnb_repair_option_cannot_be_simulated_without_draw_no_bet_odds": "La opcion DNB no puede simularse sin cuotas draw-no-bet.",
    "double_chance_repair_option_cannot_be_simulated_without_double_chance_odds": "La opcion de doble oportunidad no puede simularse sin cuotas de doble oportunidad.",
    "completed_result_rows_are_below_the_candidate_threshold": "Las filas completadas estan por debajo del umbral de candidato.",
    "keep_collecting_completed_rows_before_repair_candidacy": "Sigue recolectando filas completadas antes de considerar candidatura de reparacion.",
    "combat_method_round_markets_remain_capped_to_watchlist_until_sample_size_and_roi_gates_are_met": "Los mercados de metodo/ronda de combate siguen en lista de observacion hasta cumplir muestra y compuertas ROI.",
    "clv_is_unavailable_use_roi_only_shadow_testing_until_closing_odds_exist": "CLV no esta disponible; usa pruebas Shadow solo con ROI hasta que existan cuotas de cierre.",
    "phase_3d_repair_memory": "Fase 3D Repair Memory",
    "reparodynamics_phase_3d_scan": "Escaneo Reparodynamics Fase 3D",
    "phase3c_saved_to_memory": "Fase 3C guardada en memoria",
    "phase3c_duplicate_save_skipped": "Guardado duplicado Fase 3C omitido",
    "manual_review_decision": "decision de revision manual",
    "repair_memory_summary": "resumen de Repair Memory",
    "phase4_lockbox_candidate_detected": "candidato lockbox Fase 4 detectado",
    "last_reparodynamics_run": "Ultima ejecucion Reparodynamics",
    "source": "Fuente",
    "phase": "Fase",
    "rows_scanned": "Filas escaneadas",
    "completed_rows_used": "Filas completadas usadas",
    "unique_events_scanned": "Eventos unicos escaneados",
    "duplicates_detected": "Duplicados detectados",
    "new_patterns_detected": "Patrones nuevos detectados",
    "drift_detected": "Drift detectado",
    "data_blockers": "Bloqueadores de datos",
    "watchlists": "Listas de observacion",
    "shadow_tested_repairs": "Reparaciones probadas en Shadow",
    "manual_review_eligible": "Elegibles para revision manual",
    "live_repairs_applied": "Reparaciones en vivo aplicadas",
    "shadow_mode": "Shadow Mode",
    "live_mutation": "Mutacion en vivo",
    "model_training": "Entrenamiento del modelo",
    "stored_data_mutation": "Mutacion de datos guardados",
    "reason": "Razon",
    "yes": "SI",
    "no": "NO",
    "no_data": "SIN DATOS",
    "on": "ENCENDIDO",
    "off": "APAGADO",
    "forbidden": "PROHIBIDO",
    "enabled": "ACTIVADO",
    "preparation_only": "SOLO PREPARACION",
    "repair_candidates": "candidatos de reparacion",
    "rejected_repairs": "reparaciones rechazadas",
    "manual_review_queue": "cola de revision manual",
    "missing_closing_odds": "faltan cuotas de cierre",
    "missing_decimal_odds": "faltan cuotas decimales",
    "missing_draw_no_bet_odds": "faltan cuotas draw-no-bet",
    "missing_double_chance_odds": "faltan cuotas de doble oportunidad",
    "data_blocker": "bloqueador de datos",
    "watchlist": "lista de observacion",
    "repair_candidate": "candidato de reparacion",
    "already_saved": "ya guardado",
    "saved": "guardado",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _page_value_key(value: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())).strip("_")


def page_value(value: Any) -> Any:
    if not str(LANG).lower().startswith("es"):
        return value
    if value is None:
        return value
    text = str(value).strip()
    if not text:
        return value
    localized = localize_value(text, LANG)
    if localized != text:
        return localized
    return PAGE_VALUE_LABELS_ES.get(_page_value_key(text), value)


def metric_value(value: Any) -> str:
    localized = str(page_value(value))
    if str(value).strip().upper() in {"ON", "OFF", "FORBIDDEN", "ENABLED"}:
        return localized.upper()
    return localized


def display_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None:
        return None
    if not str(LANG).lower().startswith("es"):
        return frame
    out = frame.copy()
    out = out.rename(columns={column: str(column).strip().replace(" ", "_") for column in out.columns})
    if not out.empty:
        for column in out.columns:
            if out[column].dtype == object:
                out[column] = out[column].map(page_value)
    out = localize_dataframe(out, LANG)
    return out.rename(columns={column: PAGE_COLUMN_LABELS_ES.get(str(column), column) for column in out.columns})


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


def memory_counts(memory: dict[str, Any]) -> dict[str, int]:
    items = list((memory.get("items") or {}).values())
    return {
        "items": len(items),
        "promising": sum(1 for item in items if item.get("memory_status") == "promising"),
        "rejected": sum(1 for item in items if item.get("memory_status") == "rejected"),
        "data_blocked": sum(1 for item in items if item.get("memory_status") == "data_blocked"),
        "approved": sum(1 for item in items if item.get("manual_status") == "manual_approved_for_future"),
        "phase4": sum(1 for item in items if item.get("eligible_for_phase4_lockbox")),
    }


def render_memory_save_status(memory_payload: dict[str, Any]) -> None:
    if memory_payload.get("last_save_status") == "already_saved":
        st.info(t("already_saved"))
    elif memory_payload.get("last_save_status") == "saved":
        st.success(t("memory_saved"))


doctrine = get_reparodynamics_doctrine()

st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.info(t("storage_warning"))
st.page_link("pages/shadow_mode_results.py", label=t("comparison"))

workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state["aba_test_window_id"] = workspace_id
memory = load_repair_memory(workspace_id)
counts = memory_counts(memory)

cols = st.columns(8)
cols[0].metric(t("phase"), metric_value(doctrine.get("current_phase", "")))
cols[1].metric(t("shadow"), metric_value(doctrine.get("shadow_mode_activation", "ON")))
cols[2].metric(t("repair"), metric_value(doctrine.get("repair_activation", "OFF")))
cols[3].metric(t("live_repairs"), int(doctrine.get("repairs_applied_live", 0) or 0))
cols[4].metric(t("model_training"), metric_value(doctrine.get("model_training", "FORBIDDEN")))
cols[5].metric(t("stored_data"), metric_value(doctrine.get("stored_data_mutation", "FORBIDDEN")))
cols[6].metric(t("manual_review"), metric_value(doctrine.get("manual_review", "ENABLED")))
cols[7].metric(t("lockbox"), metric_value(doctrine.get("phase4_lockbox", "PREPARATION ONLY")))

mem_cols = st.columns(6)
mem_cols[0].metric(t("items_tracked"), counts["items"])
mem_cols[1].metric(t("promising"), counts["promising"])
mem_cols[2].metric(t("rejected"), counts["rejected"])
mem_cols[3].metric(t("data_blocked"), counts["data_blocked"])
mem_cols[4].metric(t("approved"), counts["approved"])
mem_cols[5].metric(t("phase4"), counts["phase4"])
st.caption(f"{t('github_memory')}: {metric_value(memory.get('github_persistence_enabled', False))}")

st.subheader(t("controls"))
st.caption(t("save_warning"))
include_system = st.checkbox(t("include_system"), value=True)
save_scan_rows = st.checkbox(t("save_scan"), value=False, key="reparodynamics_save_scan_rows")
save_confirmed = st.checkbox(t("save_confirm"), value=False, key="reparodynamics_save_confirmed")
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_phase3d_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('loaded')}: {len(uploaded_rows)}")
    st.dataframe(display_frame(pd.DataFrame(uploaded_rows).head(50)), use_container_width=True)

if st.button(t("run"), type="primary"):
    scan_rows = build_scan_rows(uploaded_rows, uploaded_name, include_system)
    phase3c_report = build_phase3c_report(scan_rows)
    phase3c_report["memory_run_id"] = stable_memory_run_id(phase3c_report)
    memory = update_repair_memory(memory, phase3c_report, source="Reparodynamics page")
    memory = save_repair_memory(memory, workspace_id)
    runner_report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    write_reparodynamics_audit_event_from_runner_report(runner_report, source="Reparodynamics Phase 3D scan", phase3c_report=phase3c_report)
    st.session_state["phase3c_latest_report"] = phase3c_report
    st.session_state["phase3d_repair_memory"] = memory
    st.session_state["shadow_mode_latest_report"] = runner_report.to_dict()
    render_memory_save_status(memory)
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
    run_id = str(phase3c.get("memory_run_id") or stable_memory_run_id(phase3c))
    already_saved = run_id in set(str(item) for item in memory.get("saved_run_ids", []))
    if already_saved:
        st.info(t("already_saved"))
    elif st.button(t("save_memory")):
        phase3c["memory_run_id"] = run_id
        memory = update_repair_memory(load_repair_memory(workspace_id), phase3c, source="Manual page save")
        memory = save_repair_memory(memory, workspace_id)
        st.session_state["phase3d_repair_memory"] = memory
        render_memory_save_status(memory)

memory = st.session_state.get("phase3d_repair_memory") or load_repair_memory(workspace_id)
frames = repair_memory_to_frames(memory)
items = memory.get("items", {}) or {}
repair_keys = sorted(items.keys())

tabs = st.tabs([t("phase3c_summary"), t("memory"), t("manual_gate"), t("drilldown"), t("blockers"), t("watchlists"), t("candidates"), t("comparison"), t("safety"), t("audit")])

with tabs[0]:
    if phase3c:
        st.dataframe(display_frame(frame_from_mapping(phase3c.get("baseline_metrics", {}) or {})), use_container_width=True, hide_index=True)
        st.json(phase3c.get("summary_counts", {}))
    else:
        st.info(t("no_run"))

with tabs[1]:
    show_frame(frames["summary"])

with tabs[2]:
    st.info(t("manual_warning"))
    if not repair_keys:
        st.info(t("empty"))
    else:
        selected_key = st.selectbox(t("review_repair"), repair_keys, key="manual_repair_key")
        action_display, action_reverse = localize_options(["keep_testing", "reject", "watchlist", "manual_approved_for_future", "clear_manual_decision"], LANG)
        action_label = st.selectbox(t("review_action"), action_display, key="manual_repair_action")
        action = action_reverse[action_label]
        reviewer = st.text_input(t("reviewer"), value="manual", key="manual_reviewer")
        note = st.text_area(t("review_note"), value="", key="manual_review_note")
        if st.button(t("apply_review")):
            memory = manual_review_decision(load_repair_memory(workspace_id), selected_key, action, reviewer=reviewer, note=note)
            memory = save_repair_memory(memory, workspace_id)
            st.session_state["phase3d_repair_memory"] = memory
            st.success(t("review_saved"))
        show_frame(frames["summary"])

with tabs[3]:
    if not repair_keys:
        st.info(t("empty"))
    else:
        selected_key = st.selectbox(t("review_repair"), repair_keys, key="drilldown_repair_key")
        selected = dict(items.get(selected_key, {}))
        history = pd.DataFrame(list(selected.pop("history", []) or []))
        st.dataframe(display_frame(frame_from_mapping(selected)), use_container_width=True, hide_index=True)
        show_frame(history)

with tabs[4]:
    show_table((phase3c or {}).get("data_blockers", []))
with tabs[5]:
    show_table((phase3c or {}).get("watchlists", []))
with tabs[6]:
    show_table((phase3c or {}).get("repair_candidates", []))
with tabs[7]:
    show_table(flatten_shadow_tests(list((phase3c or {}).get("shadow_tested_repairs", []) or [])))
with tabs[8]:
    safety = (phase3c or {}).get("safety_gates", {}) or {
        "live_mutation": doctrine.get("live_mutation", "FORBIDDEN"),
        "model_training": doctrine.get("model_training", "FORBIDDEN"),
        "stored_data_mutation": doctrine.get("stored_data_mutation", "FORBIDDEN"),
        "repairs_applied_live": doctrine.get("repairs_applied_live", 0),
    }
    st.dataframe(display_frame(frame_from_mapping(safety)), use_container_width=True, hide_index=True)
with tabs[9]:
    latest = latest_reparodynamics_audit_event()
    if latest is None:
        st.info(t("no_run"))
    else:
        st.dataframe(display_frame(pd.DataFrame(audit_event_display_rows(latest))), use_container_width=True, hide_index=True)
    show_frame(frames["events"])

st.success(t("final_rule"))
