from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from autonomous_betting_agent.dynamic_odds_display import (
    dynamic_odds_feature_influence_rows,
    dynamic_odds_shadow_learning_summary,
    resolved_dynamic_odds_shadow_model,
)
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    clear_dynamic_odds_shadow_model,
    export_dynamic_odds_shadow_model_json,
    import_dynamic_odds_shadow_model_json,
    load_dynamic_odds_shadow_model,
    model_path_string,
    runtime_lr_model,
    shadow_model_status,
    train_and_save_dynamic_odds_shadow_model,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe

TEXT = {
    "en": {
        "status_title": "Dynamic Odds Shadow Model Status",
        "trainer": "Train Dynamic Odds Shadow Model from Graded CSV",
        "trainer_upload": "Upload graded CSV for Shadow Math training",
        "train_button": "Train Dynamic Odds Shadow Model from Graded CSV",
        "download": "Download Shadow Model JSON",
        "upload_json": "Upload Shadow Model JSON",
        "replace": "Replace Current Workspace Model",
        "clear": "Clear Shadow Model",
        "cleared": "Shadow model cleared for this workspace only.",
        "imported": "Shadow model imported and safety-validated.",
        "trained": "Shadow model trained and saved. Live application remains OFF.",
        "feature_influence": "Feature influence",
        "comparison": "Current vs Dynamic Comparison Summary",
        "no_model": "No saved Shadow model for this workspace yet.",
        "import_error": "Shadow model import rejected",
    },
    "es": {
        "status_title": "Estado del Modelo Shadow de Dynamic Odds",
        "trainer": "Entrenar Modelo Shadow de Dynamic Odds desde CSV Calificado",
        "trainer_upload": "Subir CSV calificado para entrenar Shadow Math",
        "train_button": "Entrenar Modelo Shadow de Dynamic Odds desde CSV Calificado",
        "download": "Descargar JSON del Modelo Shadow",
        "upload_json": "Subir JSON del Modelo Shadow",
        "replace": "Reemplazar Modelo del Espacio de Trabajo Actual",
        "clear": "Borrar Modelo Shadow",
        "cleared": "Modelo Shadow borrado solo para este espacio de trabajo.",
        "imported": "Modelo Shadow importado y validado por seguridad.",
        "trained": "Modelo Shadow entrenado y guardado. La aplicacion en vivo sigue OFF.",
        "feature_influence": "Influencia de features",
        "comparison": "Resumen Actual vs Dinamico",
        "no_model": "Aun no hay modelo Shadow guardado para este espacio de trabajo.",
        "import_error": "Importacion de modelo Shadow rechazada",
    },
}


def _t(language: str, key: str) -> str:
    return TEXT.get(language, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def _display_frame(frame: pd.DataFrame, language: str) -> pd.DataFrame:
    return localize_dataframe(frame, language)


def _rows_from_upload(upload: Any) -> list[dict[str, Any]]:
    if upload is None:
        return []
    frame = pd.read_csv(upload)
    frame["source_file"] = getattr(upload, "name", "graded_shadow_upload.csv")
    return frame.to_dict("records")


def render_dynamic_odds_control_panel(rows: Sequence[Mapping[str, Any]] | None, workspace_id: str, language: str = "en") -> dict[str, Any]:
    """Render a read-only Dynamic Odds Shadow control panel and return the runtime LR model."""

    source_rows = [dict(row) for row in rows or [] if isinstance(row, Mapping)]
    saved_payload = load_dynamic_odds_shadow_model(workspace_id)
    if not saved_payload and source_rows:
        try:
            resolved_dynamic_odds_shadow_model(source_rows)
            saved_payload = load_dynamic_odds_shadow_model(workspace_id)
        except Exception:
            saved_payload = {}
    status = shadow_model_status(saved_payload, source="saved_shadow_model" if saved_payload else "no_model")

    st.subheader(_t(language, "status_title"))
    cols = st.columns(8)
    cols[0].metric("Model loaded" if language == "en" else "Modelo cargado", "YES" if status["model_loaded"] else "NO")
    cols[1].metric("Model source" if language == "en" else "Fuente", status.get("model_source", "no_model"))
    cols[2].metric("Training rows" if language == "en" else "Filas LR", int(status.get("training_rows_used") or 0))
    cols[3].metric("Features" if language == "en" else "Features", int(status.get("feature_count") or 0))
    cols[4].metric("Global baseline" if language == "en" else "Base global", f"{float(status.get('global_baseline') or 0):.0%}")
    protected = status.get("protected_baseline")
    cols[5].metric("Protected baseline" if language == "en" else "Base protegida", "N/A" if protected is None else f"{float(protected):.0%}")
    cols[6].metric("Quality" if language == "en" else "Calidad", status.get("model_quality_label", "DATA BLOCKED"))
    cols[7].metric("Applied live" if language == "en" else "Aplicado vivo", int(status.get("dynamic_odds_applied_live_count") or 0))

    status_frame = pd.DataFrame([status])
    st.dataframe(_display_frame(status_frame, language), use_container_width=True, hide_index=True)

    comparison = dynamic_odds_shadow_learning_summary(source_rows, lr_model=runtime_lr_model(saved_payload) if saved_payload else None)
    st.caption(_t(language, "comparison"))
    st.dataframe(_display_frame(pd.DataFrame([comparison]), language), use_container_width=True, hide_index=True)

    with st.expander(_t(language, "trainer"), expanded=False):
        train_upload = st.file_uploader(_t(language, "trainer_upload"), type=["csv"], key=f"dynamic_odds_shadow_train_{workspace_id}")
        if st.button(_t(language, "train_button"), key=f"dynamic_odds_shadow_train_button_{workspace_id}", use_container_width=True):
            try:
                uploaded_rows = _rows_from_upload(train_upload)
                saved_payload = train_and_save_dynamic_odds_shadow_model(uploaded_rows, workspace_id=workspace_id, source="graded_upload_shadow_trainer")
                st.success(_t(language, "trained"))
                st.dataframe(_display_frame(pd.DataFrame([shadow_model_status(saved_payload, source="saved_shadow_model")]), language), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"{_t(language, 'import_error')}: {exc}")

    model_json = export_dynamic_odds_shadow_model_json(workspace_id)
    c1, c2, c3 = st.columns(3)
    c1.download_button(_t(language, "download"), data=model_json or "{}\n", file_name=f"dynamic_odds_shadow_model_{workspace_id}.json", mime="application/json", disabled=not bool(model_json), use_container_width=True)
    import_upload = c2.file_uploader(_t(language, "upload_json"), type=["json"], key=f"dynamic_odds_shadow_import_{workspace_id}")
    if c2.button(_t(language, "replace"), key=f"dynamic_odds_shadow_replace_{workspace_id}", use_container_width=True):
        try:
            if import_upload is None:
                raise ValueError("missing_json_upload")
            text = import_upload.getvalue().decode("utf-8")
            saved_payload = import_dynamic_odds_shadow_model_json(text, workspace_id=workspace_id)
            st.success(_t(language, "imported"))
        except Exception as exc:
            st.error(f"{_t(language, 'import_error')}: {exc}")
    if c3.button(_t(language, "clear"), key=f"dynamic_odds_shadow_clear_{workspace_id}", use_container_width=True):
        clear_dynamic_odds_shadow_model(workspace_id)
        saved_payload = {}
        st.info(_t(language, "cleared"))

    active_payload = saved_payload or load_dynamic_odds_shadow_model(workspace_id)
    influence = dynamic_odds_feature_influence_rows(runtime_lr_model(active_payload) if active_payload else {})
    with st.expander(_t(language, "feature_influence"), expanded=False):
        if influence:
            frame = pd.DataFrame(influence)
            sort_choice = st.selectbox("Sort" if language == "en" else "Orden", ["largest boost first", "largest downgrade first", "largest sample first"], key=f"dynamic_odds_shadow_sort_{workspace_id}")
            if sort_choice == "largest boost first":
                frame = frame.sort_values("LR", ascending=False)
            elif sort_choice == "largest downgrade first":
                frame = frame.sort_values("LR", ascending=True)
            else:
                frame = frame.sort_values("sample_size", ascending=False)
            st.dataframe(_display_frame(frame, language), use_container_width=True, hide_index=True)
        else:
            st.info(_t(language, "no_model"))

    return runtime_lr_model(active_payload) if active_payload else {}


def control_panel_static_markers() -> dict[str, str]:
    return {
        "status": "Dynamic Odds Shadow Model Status",
        "trainer": "Train Dynamic Odds Shadow Model from Graded CSV",
        "download": "Download Shadow Model JSON",
        "upload": "Upload Shadow Model JSON",
        "replace": "Replace Current Workspace Model",
        "clear": "Clear Shadow Model",
    }
