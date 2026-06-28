from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import rows_from_csv_bytes, run_adaptive_repair_scan
from autonomous_betting_agent.local_storage_import import save_reparodynamics_rows_to_research
from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_runner_report,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.reparodynamics_shadow_results import shadow_result_rows, shadow_summary
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "Measured self-repair doctrine and Phase 3B Shadow Mode control panel.",
        "warning": "Phase 3B can evaluate repair candidates in Shadow Mode. It writes audit records and comparison tables, but live predictions remain unchanged.",
        "storage_warning": "Local storage may not persist across redeploys unless persistent storage is configured. Use exports for long-term proof backup.",
        "save_warning": "Saving scan rows here only stores research rows locally. It does not train the model, change live picks, or activate Reparodynamics repairs.",
        "phase": "Current phase",
        "mode": "Operating mode",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "controls": "Phase 3B scan controls",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for this scan",
        "loaded": "Loaded uploaded rows",
        "save_scan": "Also save scanned rows to Local Control Center research ledger",
        "save_confirm": "I understand this saves scan rows locally only and does not train or mutate the model",
        "run": "Run Phase 3B Shadow Mode scan",
        "success": "Shadow Mode scan completed. Audit event written.",
        "saved": "Rows saved to research ledger",
        "not_saved": "No scan rows were saved to local storage.",
        "audit": "Latest audit event",
        "summary": "Shadow Mode summary",
        "candidates": "Shadow Mode candidates",
        "no_run": "No audit event recorded yet.",
        "no_candidates": "No Shadow Mode candidates generated.",
        "forbidden": "Forbidden in Phase 3B",
        "status": "Activation status",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Doctrina de autorreparacion medida y panel de Shadow Mode de Fase 3B.",
        "warning": "La Fase 3B puede evaluar candidatos de reparacion dentro de Shadow Mode. Escribe auditoria y tablas de comparacion, pero las predicciones en vivo no cambian.",
        "storage_warning": "El almacenamiento local puede no persistir entre redeploys si no hay almacenamiento persistente configurado. Usa exportaciones como respaldo de prueba a largo plazo.",
        "save_warning": "Guardar filas aqui solo almacena filas de investigacion localmente. No entrena el modelo, no cambia picks en vivo ni activa reparaciones Reparodynamics.",
        "phase": "Fase actual",
        "mode": "Modo operativo",
        "repair": "Activacion de reparacion",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "controls": "Controles de escaneo Fase 3B",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para este escaneo",
        "loaded": "Filas subidas cargadas",
        "save_scan": "Tambien guardar filas escaneadas en el ledger de investigacion de Local Control Center",
        "save_confirm": "Entiendo que esto solo guarda filas localmente y no entrena ni muta el modelo",
        "run": "Ejecutar escaneo de Shadow Mode Fase 3B",
        "success": "Escaneo de Shadow Mode completado. Evento de auditoria escrito.",
        "saved": "Filas guardadas en ledger de investigacion",
        "not_saved": "No se guardaron filas de escaneo en almacenamiento local.",
        "audit": "Ultimo evento de auditoria",
        "summary": "Resumen de Shadow Mode",
        "candidates": "Candidatos de Shadow Mode",
        "no_run": "Todavia no hay evento de auditoria registrado.",
        "no_candidates": "No se generaron candidatos de Shadow Mode.",
        "forbidden": "Prohibido en Fase 3B",
        "status": "Estado de activacion",
    },
}

ES = {
    "Phase 3B": "Fase 3B",
    "Shadow Mode evaluation": "Evaluacion en Shadow Mode",
    "Forbidden": "Prohibido",
    "ON": "ENCENDIDO",
    "OFF": "APAGADO",
    "NO DATA": "SIN DATOS",
    "YES": "SI",
    "NO": "NO",
    "Phase 3B Shadow Mode; live mutation forbidden": "Fase 3B con Shadow Mode; mutacion en vivo prohibida",
    "ABA may test repairs in Shadow Mode, but live repair remains forbidden.": "ABA puede probar reparaciones en Shadow Mode, pero la reparacion en vivo sigue prohibida.",
}

FIELD_ES = {
    "Last Reparodynamics Run": "Ultima ejecucion Reparodynamics",
    "Source": "Fuente",
    "Rows scanned": "Filas escaneadas",
    "Unique events scanned": "Eventos unicos escaneados",
    "Duplicates detected": "Duplicados detectados",
    "New patterns detected": "Patrones nuevos detectados",
    "Drift detected": "Deriva detectada",
    "Repair candidates generated": "Candidatos de reparacion generados",
    "Shadow Mode": "Shadow Mode",
    "Live Mutation": "Mutacion en vivo",
    "Reason": "Razon",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def v(value: object) -> str:
    text = str(value or "")
    return ES.get(text, text) if LANG == "es" else text


def audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if LANG != "es":
        return rows
    return [{"field": FIELD_ES.get(row["field"], row["field"]), "value": v(row["value"])} for row in rows]


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def table(items: object) -> pd.DataFrame:
    values = list(items or [])
    return pd.DataFrame({t("forbidden"): values})


doctrine = get_reparodynamics_doctrine()
st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.info(t("storage_warning"))
st.page_link("pages/shadow_mode_results.py", label=t("summary"))

cols = st.columns(6)
cols[0].metric(t("phase"), v(doctrine.get("current_phase", "")))
cols[1].metric(t("mode"), v(doctrine.get("operating_mode", "")))
cols[2].metric(t("repair"), v(doctrine.get("repair_activation", "")))
cols[3].metric(t("shadow"), v(doctrine.get("shadow_mode_activation", "")))
cols[4].metric(t("tgrm"), v(doctrine.get("tgrm_activation", "")))
cols[5].metric(t("rye"), v(doctrine.get("rye_activation", "")))

st.subheader(t("controls"))
st.caption(t("save_warning"))
include_system = st.checkbox(t("include_system"), value=True)
save_scan_rows = st.checkbox(t("save_scan"), value=False, key="reparodynamics_save_scan_rows")
save_confirmed = st.checkbox(t("save_confirm"), value=False, key="reparodynamics_save_confirmed")
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_phase3b_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('loaded')}: {len(uploaded_rows)}")
    st.dataframe(display_frame(pd.DataFrame(uploaded_rows).head(50)), use_container_width=True)

if st.button(t("run"), type="primary"):
    report = run_adaptive_repair_scan(uploaded_rows=uploaded_rows, uploaded_filename=uploaded_name, uploaded_bytes=uploaded_bytes, include_system_sources=include_system)
    st.session_state["shadow_mode_latest_report"] = report.to_dict()
    audit_event = write_reparodynamics_audit_event_from_runner_report(report, source="Reparodynamics Phase 3B scan")
    st.success(t("success"))
    if save_scan_rows:
        rows_to_save = uploaded_rows or []
        if rows_to_save and save_confirmed:
            save_result = save_reparodynamics_rows_to_research(rows_to_save, run_id=report.run_id, filename=uploaded_name, confirmed=True)
            st.success(f"{t('saved')}: {save_result['rows_imported']} ({save_result['rows_skipped_duplicate']} duplicate)")
        elif rows_to_save and not save_confirmed:
            st.warning(t("not_saved"))
        else:
            st.info(t("not_saved"))
    summary = shadow_summary(report)
    candidates = shadow_result_rows(report)
    st.subheader(t("summary"))
    st.json(summary)
    st.subheader(t("candidates"))
    if candidates:
        st.dataframe(display_frame(pd.DataFrame(candidates)), use_container_width=True, hide_index=True)
    else:
        st.info(t("no_candidates"))
else:
    audit_event = latest_reparodynamics_audit_event()

st.subheader(t("audit"))
if audit_event is None:
    st.info(t("no_run"))
else:
    st.dataframe(display_frame(pd.DataFrame(audit_rows(audit_event_display_rows(audit_event)))), use_container_width=True, hide_index=True)

st.subheader(t("forbidden"))
st.dataframe(display_frame(table(doctrine.get("forbidden_actions", []))), use_container_width=True, hide_index=True)

st.subheader(t("status"))
st.dataframe(
    display_frame(
        pd.DataFrame(
            [
                {"control": "live_mutation", "status": v(doctrine.get("live_mutation", ""))},
                {"control": "repair_activation", "status": v(doctrine.get("repair_activation", ""))},
                {"control": "shadow_mode_activation", "status": v(doctrine.get("shadow_mode_activation", ""))},
                {"control": "tgrm_activation", "status": v(doctrine.get("tgrm_activation", ""))},
                {"control": "rye_activation", "status": v(doctrine.get("rye_activation", ""))},
            ]
        )
    ),
    use_container_width=True,
    hide_index=True,
)

st.success(v(doctrine.get("final_rule", "")))
