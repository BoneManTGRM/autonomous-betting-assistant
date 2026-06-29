from __future__ import annotations

import base64
import html

import pandas as pd
import streamlit as st

from autonomous_betting_agent.csv_schema_mapper import (
    map_and_repair_frame,
    schema_mapper_report_section,
    schema_mapper_summary,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="CSV Schema Mapper", layout="wide")
LANG = render_app_sidebar("csv_schema_mapper_repair", language_key="csv_schema_mapper_language", selector="radio")

TEXT = {
    "en": {
        "title": "CSV Schema Mapper + Upload Repair Assistant",
        "caption": "Phase 3E.6.4 local/session-only CSV mapping, normalization, diagnostics, and repaired CSV export.",
        "safety": "Safety",
        "upload": "Upload CSV files",
        "summary": "Schema Mapper Summary",
        "preview": "Repaired CSV Preview",
        "missing": "Rows or schema still missing required fields",
        "duplicates": "Duplicate row/event diagnostics",
        "download": "Download repaired CSV",
        "send": "Send repaired rows to advisory session rows",
        "sent": "Repaired rows were copied into session rows for advisory review.",
        "report": "Copy/paste schema mapper report",
        "no_rows": "Upload one or more CSV files to inspect and repair the schema.",
    },
    "es": {
        "title": "Mapeador de Esquema CSV + Asistente de Reparación de Subida",
        "caption": "Fase 3E.6.4 mapeo local/sesion, normalizacion, diagnosticos y exportacion CSV reparada.",
        "safety": "Seguridad",
        "upload": "Subir archivos CSV",
        "summary": "Resumen del mapeador de esquema",
        "preview": "Vista previa del CSV reparado",
        "missing": "Filas o esquema con campos requeridos faltantes",
        "duplicates": "Diagnostico de filas/eventos duplicados",
        "download": "Descargar CSV reparado",
        "send": "Enviar filas reparadas a sesion asesoría",
        "sent": "Las filas reparadas fueron copiadas a la sesion para revision asesoría.",
        "report": "Reporte de mapeo para copiar/pegar",
        "no_rows": "Sube uno o mas CSV para inspeccionar y reparar el esquema.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    st.markdown(
        f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" '
        f'style="display:block;text-align:center;background:#ef5350;color:white;'
        f'padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">'
        f'{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def show_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    if frame.empty:
        st.info("No rows.")
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


st.title(t("title"))
st.caption(t("caption"))

st.subheader(t("safety"))
st.warning(
    "CSV Schema Mapper is local/session-only. It does not alter the original upload in place. "
    "It does not add a server, database, persistent storage, proof mutation, grading mutation, "
    "official lock changes, bankroll/staking changes, live betting, or auto-betting."
)
st.json({
    "phase": "3E.6.4",
    "local_session_only": True,
    "original_upload_mutated": False,
    "server_added": False,
    "database_added": False,
    "proof_mutation": False,
    "grading_mutation": False,
    "official_lock_changes": False,
    "live_betting": False,
})

uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True)
frames: list[pd.DataFrame] = []
if uploads:
    for upload in uploads:
        try:
            frame = pd.read_csv(upload)
            frame["source_file"] = upload.name
            frames.append(frame)
        except Exception as exc:
            st.warning(f"{upload.name}: {type(exc).__name__}")

if not frames:
    st.warning(t("no_rows"))
    st.stop()

raw = pd.concat(frames, ignore_index=True, sort=False)
repaired = map_and_repair_frame(raw)
summary = schema_mapper_summary(raw)
st.session_state["csv_schema_mapper_repaired_rows"] = repaired.to_dict("records")

show_table(t("summary"), summary)
show_table(t("preview"), repaired)

missing_frame = repaired[repaired.get("schema_mapper_missing_required_fields", pd.Series(dtype=str)).fillna("").astype(str) != ""].copy()
duplicate_count = int(repaired.get("schema_mapper_duplicate_count", pd.Series([0])).iloc[0] or 0) if not repaired.empty else 0
duplicate_frame = repaired if duplicate_count else pd.DataFrame()
show_table(t("missing"), missing_frame)
show_table(t("duplicates"), duplicate_frame)

ready = bool(summary.iloc[0].get("ready_rows", 0)) if not summary.empty else False
if ready:
    if st.button(t("send")):
        rows = repaired.to_dict("records")
        st.session_state["pro_predictor_latest_rows"] = rows
        st.session_state["csv_schema_mapper_repaired_rows"] = rows
        st.success(t("sent"))
    csv_link(t("download"), repaired, "aba_repaired_advisory_upload.csv")

st.subheader(t("report"))
st.text_area(t("report"), value=schema_mapper_report_section(raw), height=280)
