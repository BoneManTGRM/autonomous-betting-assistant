from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import rows_from_csv_bytes, run_adaptive_repair_scan
from autonomous_betting_agent.reparodynamics_audit import write_reparodynamics_audit_event_from_runner_report
from autonomous_betting_agent.reparodynamics_shadow_results import no_live_mutation_assertions, shadow_result_rows, shadow_summary
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Shadow Mode Results", layout="wide")
LANG = render_app_sidebar("shadow_mode_results", language_key="shadow_mode_results_language", selector="radio")

TEXT = {
    "en": {
        "title": "Shadow Mode Results",
        "caption": "Counterfactual repair-candidate review. Live picks stay unchanged.",
        "warning": "Phase 3B evaluates repair candidates in Shadow Mode only. It does not change confidence, EV, edge, units, bankroll, sportsbooks, filters, reports, or live picks.",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for Shadow Mode scan",
        "uploaded": "Uploaded rows loaded",
        "run": "Run Shadow Mode comparison",
        "summary": "Shadow Mode Summary",
        "candidates": "Repair candidates under Shadow Mode",
        "safety": "No-live-mutation safety checks",
        "no_candidates": "No repair candidates were generated. This is valid when the scan has no data or no qualifying drift/data-quality signals.",
        "audit_written": "Audit event written. Live mutation remains forbidden.",
    },
    "es": {
        "title": "Resultados Shadow Mode",
        "caption": "Revisión contrafactual de candidatos de reparación. Los picks en vivo no cambian.",
        "warning": "La Fase 3B evalúa candidatos de reparación solo en Shadow Mode. No cambia confianza, VE, ventaja, unidades, bankroll, sportsbooks, filtros, reportes ni picks en vivo.",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para escaneo Shadow Mode",
        "uploaded": "Filas subidas cargadas",
        "run": "Ejecutar comparación Shadow Mode",
        "summary": "Resumen Shadow Mode",
        "candidates": "Candidatos de reparación en Shadow Mode",
        "safety": "Controles de seguridad sin mutación en vivo",
        "no_candidates": "No se generaron candidatos de reparación. Esto es válido cuando el escaneo no tiene datos o no hay señales calificadas de deriva/calidad de datos.",
        "audit_written": "Evento de auditoría escrito. La mutación en vivo sigue prohibida.",
    },
}

ES_COLUMNS = {
    "rank": "rango",
    "candidate_id": "id_candidato",
    "pattern_name": "patrón",
    "pattern_type": "tipo",
    "affected_scope": "alcance",
    "sample_size": "muestra",
    "evidence_summary": "evidencia",
    "current_live_behavior": "comportamiento_actual_en_vivo",
    "shadow_mode_action": "acción_shadow_mode",
    "would_change_live_pick": "cambiaría_pick_en_vivo",
    "production_repair_allowed": "reparación_producción_permitida",
    "safety_decision": "decisión_seguridad",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def localize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if LANG != "es" or frame.empty:
        return frame
    return frame.rename(columns={col: ES_COLUMNS.get(col, col) for col in frame.columns})


st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))

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
    st.dataframe(pd.DataFrame(uploaded_rows).head(50), use_container_width=True)

if st.button(t("run"), type="primary"):
    report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    st.session_state["shadow_mode_latest_report"] = report.to_dict()
    write_reparodynamics_audit_event_from_runner_report(report, source="Shadow Mode Results page")
    st.success(t("audit_written"))

report_data = st.session_state.get("shadow_mode_latest_report")
if report_data:
    summary = shadow_summary(report_data)
    assertions = no_live_mutation_assertions(report_data)
    candidate_rows = shadow_result_rows(report_data)

    st.subheader(t("summary"))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rows", summary["rows_scanned"])
    c2.metric("Candidates", summary["candidate_count"])
    c3.metric("Shadow", "ON" if summary["shadow_mode_active"] else "OFF")
    c4.metric("Live changes", "ON" if summary["live_pick_changes"] else "OFF")
    c5.metric("Gate", str(summary["repair_gate_status"]))
    st.json(summary)

    st.subheader(t("safety"))
    st.dataframe(pd.DataFrame([{"check": key, "passed": value} for key, value in assertions.items()]), use_container_width=True, hide_index=True)

    st.subheader(t("candidates"))
    if candidate_rows:
        st.dataframe(localize_frame(pd.DataFrame(candidate_rows)), use_container_width=True, hide_index=True)
    else:
        st.info(t("no_candidates"))
else:
    st.info(t("no_candidates"))
