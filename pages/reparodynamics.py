from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import rows_from_csv_bytes, run_adaptive_repair_scan
from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_runner_report,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "ABA Signal Pro operating doctrine for measured self-repair.",
        "phase": "Current phase",
        "mode": "Operating mode",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "motive": "Doctrine motive",
        "principles": "Repair principles",
        "safety": "Safety principles",
        "forbidden": "Forbidden in Phase 3B",
        "status": "Activation status",
        "audit": "Reparodynamics Audit Log",
        "controls": "Shadow Mode scan controls",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for this Reparodynamics scan",
        "upload_loaded": "Loaded uploaded rows for Shadow Mode scan.",
        "run_now": "Run Phase 3B Shadow Mode scan now",
        "run_success": "Reparodynamics Shadow Mode scan completed and audit event written.",
        "scan_summary": "Latest scan summary",
        "no_run": "No run recorded yet.",
        "phase3b_explanation": "Phase 3B evaluates repairs in Shadow Mode only. It scans graded results, detects real drift, finds duplicate-event issues, and creates counterfactual repair candidates without changing live picks, confidence, bankroll, sportsbook recommendations, filters, or model behavior.",
        "final": "Final rule",
        "warning": "This page can run a real Shadow Mode scan and write an audit event. Shadow Mode is ON for counterfactual evaluation only. Live repairs, TGRM activation, RYE activation, confidence changes, bet-tier changes, bankroll changes, sportsbook changes, filters, and model mutation remain blocked.",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Doctrina operativa de ABA Signal Pro para autorreparación medida.",
        "phase": "Fase actual",
        "mode": "Modo operativo",
        "repair": "Activación de reparación",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "motive": "Motivo de la doctrina",
        "principles": "Principios de reparación",
        "safety": "Principios de seguridad",
        "forbidden": "Prohibido en Fase 3B",
        "status": "Estado de activación",
        "audit": "Registro de Auditoría Reparodynamics",
        "controls": "Controles de escaneo Shadow Mode",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para este escaneo Reparodynamics",
        "upload_loaded": "Filas subidas cargadas para escaneo Shadow Mode.",
        "run_now": "Ejecutar escaneo Shadow Mode Fase 3B ahora",
        "run_success": "Escaneo Shadow Mode Reparodynamics completado y evento de auditoría escrito.",
        "scan_summary": "Resumen del último escaneo",
        "no_run": "Todavía no hay ejecución registrada.",
        "phase3b_explanation": "La Fase 3B evalúa reparaciones solo en Shadow Mode. Escanea resultados calificados, detecta deriva real, encuentra problemas de eventos duplicados y crea candidatos contrafactuales sin cambiar picks en vivo, confianza, bankroll, recomendaciones de sportsbook, filtros ni comportamiento del modelo.",
        "final": "Regla final",
        "warning": "Esta página puede ejecutar un escaneo real en Shadow Mode y escribir un evento de auditoría. Shadow Mode está ON solo para evaluación contrafactual. Reparaciones en vivo, activación TGRM, activación RYE, cambios de confianza, niveles de apuesta, bankroll, sportsbook, filtros y mutación del modelo siguen bloqueados.",
    },
}

ES_VALUE_MAP = {
    "Phase 3A": "Fase 3A",
    "Phase 3B": "Fase 3B",
    "Observation-only": "Solo observación",
    "Shadow Mode evaluation": "Evaluación Shadow Mode",
    "Evidence-gated targeted repair": "Reparación dirigida con control de evidencia",
    "Forbidden": "Prohibido",
    "FORBIDDEN": "PROHIBIDO",
    "OFF": "APAGADO",
    "ON": "ENCENDIDO",
    "YES": "SÍ",
    "NO": "NO",
    "NO DATA": "SIN DATOS",
    "Phase 3A observation-only": "Fase 3A solo observación",
    "Phase 3B Shadow Mode; live mutation forbidden": "Fase 3B Shadow Mode; mutación en vivo prohibida",
    "ABA should learn automatically, but repair cautiously.": "ABA debe aprender automáticamente, pero reparar con cautela.",
    "ABA may test repairs in Shadow Mode, but live repair remains forbidden.": "ABA puede probar reparaciones en Shadow Mode, pero la reparación en vivo sigue prohibida.",
}

ES_LIST_MAP = {
    "Observe first and repair later.": "Observar primero y reparar después.",
    "Diagnose drift before proposing any repair.": "Diagnosticar deriva antes de proponer cualquier reparación.",
    "Prefer targeted repair over blind retraining.": "Preferir reparación dirigida en vez de reentrenamiento ciego.",
    "Conserve repair energy by changing only what evidence supports.": "Conservar energía de reparación cambiando solo lo que la evidencia respalda.",
    "Evaluate pattern candidates in Shadow Mode before promotion.": "Evaluar candidatos de patrón en Shadow Mode antes de promoción.",
    "Treat RYE readiness as readiness only, not live activation.": "Tratar la preparación RYE solo como preparación, no como activación en vivo.",
    "Treat Shadow Mode as counterfactual evaluation only.": "Tratar Shadow Mode solo como evaluación contrafactual.",
    "Phase 3B enables Shadow Mode evaluation only.": "La Fase 3B habilita solo evaluación Shadow Mode.",
    "Learning means observation, diagnostics, shadow evaluation, readiness checks, and saved reports only.": "Aprendizaje significa solo observación, diagnósticos, evaluación shadow, revisiones de preparación y reportes guardados.",
    "No live repair activates during Phase 3B.": "Ninguna reparación en vivo se activa durante la Fase 3B.",
    "No repair survives without proof.": "Ninguna reparación sobrevive sin prueba.",
    "The system does not chase losses.": "El sistema no persigue pérdidas.",
    "The system does not panic after variance.": "El sistema no entra en pánico después de la varianza.",
    "The system does not blindly retrain.": "El sistema no se reentrena a ciegas.",
    "The system does not inflate confidence.": "El sistema no infla la confianza.",
    "live repairs": "reparaciones en vivo",
    "TGRM repair activation": "activación de reparación TGRM",
    "full RYE repair activation": "activación completa de reparación RYE",
    "Hidden Value Score activation": "activación de Hidden Value Score",
    "confidence calibration activation": "activación de calibración de confianza",
    "live pick filtering": "filtrado de picks en vivo",
    "live model mutation": "mutación del modelo en vivo",
    "Learning Page live model updates": "actualizaciones del modelo en vivo desde Learning Page",
    "automatic confidence adjustment": "ajuste automático de confianza",
    "automatic bet-tier changes": "cambios automáticos de nivel de apuesta",
    "production repair candidates": "candidatos de reparación de producción",
    "automatic bankroll changes": "cambios automáticos de bankroll",
    "automatic sportsbook recommendation changes": "cambios automáticos de recomendación de sportsbook",
}

ES_AUDIT_FIELD_MAP = {
    "Last Reparodynamics Run": "Última ejecución Reparodynamics",
    "Source": "Fuente",
    "Rows scanned": "Filas escaneadas",
    "Unique events scanned": "Eventos únicos escaneados",
    "Duplicates detected": "Duplicados detectados",
    "New patterns detected": "Patrones nuevos detectados",
    "Drift detected": "Deriva detectada",
    "Repair candidates generated": "Candidatos de reparación generados",
    "Shadow Mode": "Shadow Mode",
    "Live Mutation": "Mutación en vivo",
    "Reason": "Razón",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def value_text(value: str) -> str:
    return ES_VALUE_MAP.get(value, value) if LANG == "es" else value


def list_text(values: list[str]) -> list[str]:
    if LANG != "es":
        return values
    return [ES_LIST_MAP.get(value, value) for value in values]


def audit_rows_for_language(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if LANG != "es":
        return rows
    translated = []
    for row in rows:
        translated.append({"field": ES_AUDIT_FIELD_MAP.get(row["field"], row["field"]), "value": value_text(row["value"])})
    return translated


doctrine = get_reparodynamics_doctrine()

st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))

status_cols = st.columns(6)
status_cols[0].metric(t("phase"), value_text(str(doctrine.get("current_phase", ""))))
status_cols[1].metric(t("mode"), value_text(str(doctrine.get("operating_mode", ""))))
status_cols[2].metric(t("repair"), value_text(str(doctrine.get("repair_activation", ""))))
status_cols[3].metric(t("shadow"), value_text(str(doctrine.get("shadow_mode_activation", ""))))
status_cols[4].metric(t("tgrm"), value_text(str(doctrine.get("tgrm_activation", ""))))
status_cols[5].metric(t("rye"), value_text(str(doctrine.get("rye_activation", ""))))

st.subheader(t("controls"))
include_system = st.checkbox(t("include_system"), value=True)
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_observation_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    try:
        uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
        st.success(f"{t('upload_loaded')} {len(uploaded_rows)}")
        st.dataframe(pd.DataFrame(uploaded_rows).head(50), use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not parse uploaded CSV: {exc}")
        uploaded_rows = None

if st.button(t("run_now"), type="primary"):
    report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    audit_event = write_reparodynamics_audit_event_from_runner_report(report, source="Reparodynamics page Shadow Mode scan")
    st.success(t("run_success"))
    with st.expander(t("scan_summary"), expanded=True):
        st.json({
            "run_id": report.run_id,
            "sources": report.source_summary,
            "safety_state": report.safety_state,
            "readiness": report.readiness,
            "activation_gate": report.activation_gate,
            "production_repairs_active": report.production_repairs_active,
            "shadow_mode_active": report.shadow_mode_active,
            "live_pick_changes": report.live_pick_changes,
        })
else:
    audit_event = latest_reparodynamics_audit_event()

st.subheader(t("audit"))
st.info(t("phase3b_explanation"))
if audit_event is None:
    st.info(t("no_run"))
else:
    st.dataframe(
        pd.DataFrame(audit_rows_for_language(audit_event_display_rows(audit_event))),
        use_container_width=True,
        hide_index=True,
    )

st.subheader(t("motive"))
if LANG == "es":
    st.write("Reparodynamics es la doctrina operativa de autorreparación medida. ABA observa primero, diagnostica con cuidado, preserva la integridad de los datos, conserva energía de reparación y evalúa candidatos en Shadow Mode antes de cualquier aprobación manual. La reparación en vivo sigue prohibida.")
else:
    st.write(doctrine.get("motive", ""))

left, right = st.columns(2)
with left:
    st.subheader(t("principles"))
    for item in list_text(list(doctrine.get("repair_principles", []))):
        st.markdown(f"- {item}")
with right:
    st.subheader(t("safety"))
    for item in list_text(list(doctrine.get("safety_principles", []))):
        st.markdown(f"- {item}")

st.subheader(t("forbidden"))
st.dataframe(
    pd.DataFrame({t("forbidden"): list_text(list(doctrine.get("forbidden_actions", [])))}),
    use_container_width=True,
    hide_index=True,
)

st.subheader(t("status"))
st.dataframe(
    pd.DataFrame(
        [
            {"control": "live_mutation", "status": value_text(str(doctrine.get("live_mutation", "")))},
            {"control": "repair_activation", "status": value_text(str(doctrine.get("repair_activation", "")))},
            {"control": "shadow_mode_activation", "status": value_text(str(doctrine.get("shadow_mode_activation", "")))},
            {"control": "tgrm_activation", "status": value_text(str(doctrine.get("tgrm_activation", "")))},
            {"control": "rye_activation", "status": value_text(str(doctrine.get("rye_activation", "")))},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.success(value_text(str(doctrine.get("final_rule", ""))))
