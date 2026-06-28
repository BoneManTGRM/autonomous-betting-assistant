from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from autonomous_betting_agent.dynamic_odds_display import (
    dynamic_odds_feature_influence_rows,
    dynamic_odds_shadow_learning_summary,
)
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    clear_dynamic_odds_shadow_model,
    import_dynamic_odds_shadow_model_json,
    load_dynamic_odds_shadow_model,
    runtime_lr_model,
    shadow_model_status,
    train_and_save_dynamic_odds_shadow_model,
    training_result_stats,
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
        "audit": "Shadow training audit summary",
        "no_model": "No saved Shadow model for this workspace yet.",
        "import_error": "Shadow model import rejected",
        "empty_upload": "Upload a non-empty graded CSV before training.",
        "safe_empty": "No saved Shadow model or audit summary is available yet.",
        "live_status": "Live application",
        "applied_live": "Applied-live count",
        "advisory": "Dynamic odds math",
        "off": "OFF",
        "advisory_only": "Advisory only",
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
        "audit": "Resumen de auditoria de entrenamiento Shadow",
        "no_model": "Aun no hay modelo Shadow guardado para este espacio de trabajo.",
        "import_error": "Importacion de modelo Shadow rechazada",
        "empty_upload": "Sube un CSV calificado no vacio antes de entrenar.",
        "safe_empty": "Aun no hay modelo Shadow guardado ni resumen de auditoria disponible.",
        "live_status": "Aplicacion en vivo",
        "applied_live": "Conteo aplicado en vivo",
        "advisory": "Matematica Dynamic Odds",
        "off": "OFF",
        "advisory_only": "Solo asesoria",
    },
}

PRIVATE_EXPORT_KEYS = {"model_path"}


def _t(language: str, key: str) -> str:
    return TEXT.get(language, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def _display_frame(frame: pd.DataFrame, language: str) -> pd.DataFrame:
    return localize_dataframe(frame, language)


def _key(panel_key_prefix: str, workspace_id: str, suffix: str) -> str:
    safe_prefix = str(panel_key_prefix or "dynamic_odds_shadow").strip().replace(" ", "_")
    safe_workspace = str(workspace_id or "test_01").strip().replace(" ", "_")
    return f"{safe_prefix}_{safe_workspace}_{suffix}"


def _rows_from_upload(upload: Any) -> list[dict[str, Any]]:
    if upload is None:
        return []
    frame = pd.read_csv(upload)
    if frame.empty:
        return []
    frame["source_file"] = getattr(upload, "name", "graded_shadow_upload.csv")
    return frame.to_dict("records")


def _safe_error(exc: Exception) -> str:
    return type(exc).__name__


def _public_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    for key in PRIVATE_EXPORT_KEYS:
        data.pop(key, None)
    lr_model = data.get("lr_model")
    if isinstance(lr_model, Mapping):
        data["lr_model"] = {key: value for key, value in dict(lr_model).items() if key not in PRIVATE_EXPORT_KEYS}
    return data


def _safe_model_json(workspace_id: str) -> str:
    payload = _public_payload(load_dynamic_odds_shadow_model(workspace_id))
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if payload else ""


def _audit_summary(saved_payload: Mapping[str, Any] | None, language: str) -> dict[str, Any]:
    payload = dict(saved_payload or {})
    if not payload:
        return {"status": _t(language, "safe_empty"), "dynamic_odds_live_activation": "OFF", "dynamic_odds_applied_live_count": 0}
    return {
        "status": "saved_shadow_model_audit_available",
        "workspace_id": payload.get("workspace_id", ""),
        "last_trained_at_utc": payload.get("last_trained_at_utc", ""),
        "uploaded_rows": int(payload.get("uploaded_rows") or 0),
        "completed_rows": int(payload.get("completed_rows_seen") or payload.get("completed_rows") or 0),
        "wins": int(payload.get("wins") or 0),
        "losses": int(payload.get("losses") or 0),
        "pushes_excluded": int(payload.get("pushes_excluded") or 0),
        "pending_rows": int(payload.get("pending_rows") or 0),
        "feature_count": int(payload.get("feature_count") or 0),
        "model_quality_label": payload.get("model_quality_label", "DATA BLOCKED"),
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live_count": 0,
    }


def render_dynamic_odds_control_panel(
    rows: Sequence[Mapping[str, Any]] | None,
    workspace_id: str,
    language: str = "en",
    panel_key_prefix: str = "dynamic_odds_shadow",
) -> dict[str, Any]:
    """Render the shared Dynamic Odds Shadow control panel.

    Rendering is idempotent: no training, import, export, clear, or disk mutation
    occurs unless the user clicks the explicit action button for that operation.
    """

    source_rows = [dict(row) for row in rows or [] if isinstance(row, Mapping)]
    saved_payload = load_dynamic_odds_shadow_model(workspace_id)
    status = shadow_model_status(saved_payload, source="saved_shadow_model" if saved_payload else "no_model")
    source_stats = training_result_stats(source_rows)

    st.subheader(_t(language, "status_title"))
    label_cols = st.columns(3)
    label_cols[0].metric(_t(language, "live_status"), _t(language, "off"))
    label_cols[1].metric(_t(language, "applied_live"), 0)
    label_cols[2].metric(_t(language, "advisory"), _t(language, "advisory_only"))

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

    status_frame = pd.DataFrame([{**status, **{f"uploaded_{key}": value for key, value in source_stats.items()}}])
    st.dataframe(_display_frame(status_frame, language), use_container_width=True, hide_index=True)

    comparison = dynamic_odds_shadow_learning_summary(source_rows, lr_model=runtime_lr_model(saved_payload) if saved_payload else None)
    st.caption(_t(language, "comparison"))
    st.dataframe(_display_frame(pd.DataFrame([comparison]), language), use_container_width=True, hide_index=True)

    with st.expander(_t(language, "trainer"), expanded=False):
        train_upload = st.file_uploader(_t(language, "trainer_upload"), type=["csv"], key=_key(panel_key_prefix, workspace_id, "train_upload"))
        if st.button(_t(language, "train_button"), key=_key(panel_key_prefix, workspace_id, "train_button"), use_container_width=True):
            try:
                uploaded_rows = _rows_from_upload(train_upload)
                if not uploaded_rows:
                    raise ValueError("empty_csv_upload")
                saved_payload = train_and_save_dynamic_odds_shadow_model(uploaded_rows, workspace_id=workspace_id, source="graded_upload_shadow_trainer")
                st.success(_t(language, "trained"))
                st.dataframe(_display_frame(pd.DataFrame([shadow_model_status(saved_payload, source="saved_shadow_model")]), language), use_container_width=True, hide_index=True)
            except ValueError as exc:
                if str(exc) == "empty_csv_upload":
                    st.warning(_t(language, "empty_upload"))
                else:
                    st.error(f"{_t(language, 'import_error')}: {_safe_error(exc)}")
            except Exception as exc:
                st.error(f"{_t(language, 'import_error')}: {_safe_error(exc)}")

    model_json = _safe_model_json(workspace_id)
    c1, c2, c3 = st.columns(3)
    c1.download_button(_t(language, "download"), data=model_json or "{}\n", file_name=f"dynamic_odds_shadow_model_{workspace_id}.json", mime="application/json", disabled=not bool(model_json), use_container_width=True)
    import_upload = c2.file_uploader(_t(language, "upload_json"), type=["json"], key=_key(panel_key_prefix, workspace_id, "import_upload"))
    if c2.button(_t(language, "replace"), key=_key(panel_key_prefix, workspace_id, "replace_button"), use_container_width=True):
        try:
            if import_upload is None:
                raise ValueError("missing_json_upload")
            text = import_upload.getvalue().decode("utf-8")
            saved_payload = import_dynamic_odds_shadow_model_json(text, workspace_id=workspace_id)
            st.success(_t(language, "imported"))
        except Exception as exc:
            st.error(f"{_t(language, 'import_error')}: {_safe_error(exc)}")
    if c3.button(_t(language, "clear"), key=_key(panel_key_prefix, workspace_id, "clear_button"), use_container_width=True):
        clear_dynamic_odds_shadow_model(workspace_id)
        saved_payload = {}
        st.info(_t(language, "cleared"))

    active_payload = saved_payload or load_dynamic_odds_shadow_model(workspace_id)
    influence = dynamic_odds_feature_influence_rows(runtime_lr_model(active_payload) if active_payload else {})
    with st.expander(_t(language, "feature_influence"), expanded=False):
        if influence:
            frame = pd.DataFrame(influence)
            sort_choice = st.selectbox("Sort" if language == "en" else "Orden", ["largest boost first", "largest downgrade first", "largest sample first"], key=_key(panel_key_prefix, workspace_id, "sort"))
            if sort_choice == "largest boost first":
                frame = frame.sort_values("LR", ascending=False)
            elif sort_choice == "largest downgrade first":
                frame = frame.sort_values("LR", ascending=True)
            else:
                frame = frame.sort_values("sample_size", ascending=False)
            st.dataframe(_display_frame(frame, language), use_container_width=True, hide_index=True)
        else:
            st.info(_t(language, "no_model"))

    with st.expander(_t(language, "audit"), expanded=False):
        st.json(_audit_summary(active_payload, language))

    return runtime_lr_model(active_payload) if active_payload else {}


def control_panel_static_markers() -> dict[str, str]:
    return {
        "status": "Dynamic Odds Shadow Model Status",
        "trainer": "Train Dynamic Odds Shadow Model from Graded CSV",
        "download": "Download Shadow Model JSON",
        "upload": "Upload Shadow Model JSON",
        "replace": "Replace Current Workspace Model",
        "clear": "Clear Shadow Model",
        "audit": "Shadow training audit summary",
        "live_off": "Live application: OFF",
        "advisory_only": "Dynamic odds math: Advisory only",
    }
