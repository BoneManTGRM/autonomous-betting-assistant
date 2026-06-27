from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.learning_memory_controls import reset_confirmation_matches, split_learning_safe_rows, version_placeholder_path
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.reparodynamics_audit import write_reparodynamics_audit_event_from_rows
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage
from autonomous_betting_agent.ui_i18n import tr, upload_helper

st.set_page_config(page_title="Learning Memory Safety", layout="wide")
LANG = render_app_sidebar("learning_memory_safety", language_key="learning_memory_safety_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title(tr(LANG, "Learning Memory Safety", "Seguridad de Memoria de Aprendizaje"))
st.caption(tr(LANG, "Review which local rows are safe for learning before updating memory.", "Revisa cuáles filas locales son seguras antes de actualizar la memoria."))

store = LocalStorage()
rows = store.load_rows()

if not rows:
    st.info(tr(LANG, "No local rows found yet.", "Todavía no hay filas locales."))
    st.stop()

safe_rows, blocked_rows = split_learning_safe_rows(rows)

col1, col2, col3 = st.columns(3)
col1.metric(tr(LANG, "Total local rows", "Filas locales totales"), len(rows))
col2.metric(tr(LANG, "Learning-safe rows", "Filas seguras para aprendizaje"), len(safe_rows))
col3.metric(tr(LANG, "Blocked/review rows", "Filas bloqueadas/revisión"), len(blocked_rows))

st.subheader(tr(LANG, "Learning-safe rows", "Filas seguras para aprendizaje"))
if safe_rows:
    df = pd.DataFrame(safe_rows)
    st.dataframe(df, use_container_width=True)
    st.download_button(tr(LANG, "Download learning-safe CSV", "Descargar CSV seguro para aprendizaje"), df.to_csv(index=False).encode("utf-8"), file_name="learning_safe_rows.csv", mime="text/csv")
else:
    st.info(tr(LANG, "No rows currently meet the local learning-safety requirements.", "Ninguna fila cumple los requisitos de seguridad para aprendizaje."))

st.subheader(tr(LANG, "Import preview only", "Solo vista previa de importación"))
st.caption(upload_helper(LANG))
upload = st.file_uploader(tr(LANG, "Preview a learning-safe CSV before using it elsewhere", "Previsualiza un CSV seguro antes de usarlo"), type=["csv"])
if upload is not None:
    try:
        preview = pd.read_csv(upload)
        st.dataframe(preview.head(100), use_container_width=True)
        audit_event = write_reparodynamics_audit_event_from_rows(
            preview.to_dict(orient="records"),
            source="Learning Page graded upload",
        )
        st.success(
            tr(
                LANG,
                f"Reparodynamics audit event written: {audit_event.timestamp}",
                f"Evento de auditoría Reparodynamics escrito: {audit_event.timestamp}",
            )
        )
        st.caption(tr(LANG, "Preview only. This page does not automatically update memory or activate repairs.", "Solo vista previa. Esta página no actualiza la memoria ni activa reparaciones automáticamente."))
    except Exception as exc:
        st.warning(f"{tr(LANG, 'Could not preview CSV', 'No se pudo previsualizar el CSV')}: {exc}")

st.subheader(tr(LANG, "Version and reset controls", "Controles de versión y reinicio"))
version_label = st.text_input(tr(LANG, "Version label placeholder", "Marcador de versión"), "manual")
st.code(str(version_placeholder_path(version_label)))
st.caption(tr(LANG, "Use this path as a future local version marker.", "Usa esta ruta como marcador futuro de versión local."))
confirmation = st.text_input(tr(LANG, "Reset confirmation placeholder", "Marcador de confirmación de reinicio"), "")
if reset_confirmation_matches(confirmation):
    st.error(tr(LANG, "Reset confirmation entered. This page still does not delete memory automatically.", "Confirmación ingresada. Esta página todavía no elimina memoria automáticamente."))
else:
    st.info(tr(LANG, "Reset disabled. Exact confirmation is required.", "Reinicio desactivado. Se requiere confirmación exacta."))

st.subheader(tr(LANG, "Before/after and pattern review placeholders", "Marcadores de antes/después y revisión de patrones"))
st.write({
    "before_after_comparison": tr(LANG, "Placeholder: compare performance before and after a memory update.", "Marcador: comparar rendimiento antes y después de una actualización."),
    "patterns_improved": tr(LANG, "Placeholder: list patterns that improved.", "Marcador: listar patrones que mejoraron."),
    "patterns_failed": tr(LANG, "Placeholder: list patterns that weakened.", "Marcador: listar patrones que se debilitaron."),
})

st.subheader(tr(LANG, "Blocked or review rows", "Filas bloqueadas o en revisión"))
if blocked_rows:
    st.dataframe(pd.DataFrame(blocked_rows), use_container_width=True)
else:
    st.success(tr(LANG, "No blocked rows in the current local set.", "No hay filas bloqueadas en el conjunto local actual."))

st.warning(tr(LANG, "Do not use quarantined, ungraded, result-only, missing-probability, or bad-price rows for learning.", "No uses filas en cuarentena, sin calificar, solo resultado, sin probabilidad o con precio malo para aprendizaje."))
