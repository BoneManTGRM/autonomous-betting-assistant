from __future__ import annotations

import hashlib
import io

import pandas as pd
import streamlit as st

from autonomous_betting_agent import proof_center_control_service
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.event_list_dedupe import collapse_to_event_rows, event_duplicate_summary
from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.ledger_sync_service import SYNC_SOURCE_REGISTRY
from autonomous_betting_agent.ledger_types import classify_ledger_type, is_future_locked, public_metric_allowed
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_value

st.set_page_config(page_title="Proof Center", layout="wide")
LANG = render_app_sidebar("proof_center", language_key="proof_center_language")
require_streamlit_access(st, allow_roles={"admin", "client", "demo"})

PROOF_CENTER_SOURCE_KEY_OPTIONS = tuple(SYNC_SOURCE_REGISTRY.keys())
PROOF_CENTER_IMPORT_PREVIEW_KEY = "proof_center_import_preview"
PROOF_CENTER_APPROVAL_KEY = "proof_center_import_approval"
PROOF_CENTER_INPUT_FINGERPRINT_KEY = "proof_center_import_input_fingerprint"
PROOF_CENTER_UPLOAD_SNAPSHOT_KEY = "proof_center_upload_snapshot_rows"
PROOF_CENTER_REQUIRED_UPLOAD_FIELDS = ("event", "pick", "market_type", "sportsbook", "result")
PROOF_CENTER_ODDS_FIELDS = ("odds", "decimal_odds")

TEXT = {
    "en": {
        "title": "Proof Center",
        "caption": "Unified proof review, proof ID verification, row-level/event-level records, and local proof rows.",
        "warning": "Proof Center is for analytics and proof tracking only. It does not guarantee outcomes or returns.",
        "workspace": "Workspace",
        "source_counts": "Rows loaded: {total} total, {local} local, {ledger} ledger.",
        "local_rows": "Rows",
        "row_record": "Row record",
        "events": "Events",
        "event_record": "Event record",
        "tabs": ["Summary", "Proof ID Verification", "Proof Audit", "Row vs Event Record", "Local Proof Rows", "Ledger Control"],
        "public_summary": "Public proof summary",
        "no_rows": "No local or ledger proof rows found yet.",
        "public_safe_rows": "Public-safe rows",
        "research_review_rows": "Research/review rows",
        "legacy_dashboard": "Open legacy Public Proof Dashboard",
        "legacy_control": "Open legacy Proof Control Center",
        "proof_id": "Proof ID",
        "enter_proof_id": "Enter a proof ID to verify a local row.",
        "no_proof_id": "No local row found for that proof ID.",
        "ledger_type": "Ledger type",
        "forward_locked": "Forward locked",
        "public_safe": "Public-safe",
        "grade": "Grade",
        "yes": "Yes",
        "no": "No",
        "proof_audit": "Proof audit",
        "no_audit_rows": "No rows available for audit.",
        "row_vs_event": "Row-level vs event-level record",
        "row_summary": "Row-level summary",
        "event_summary": "Event-level summary",
        "event_caption": "Use event-level counts when multiple rows belong to the same matchup/game.",
        "local_proof_rows": "Proof rows",
        "event_level_rows": "Event-level proof rows",
        "row_level_rows": "Row-level market rows",
        "show_row_level": "Show row-level market rows",
        "duplicate_events": "Events with multiple rows",
        "duplicate_event_rows": "Extra row-level market rows",
        "download_rows": "Download proof rows",
        "ledger_control": "Ledger Control",
        "ledger_workspace_id": "Ledger workspace ID",
        "source_key": "Source key",
        "upload_csv": "Upload proof/performance CSV",
        "upload_status": "Upload status",
        "rows_detected": "Rows detected",
        "columns_detected": "Columns detected",
        "missing_fields": "Missing recommended fields",
        "empty_upload": "Uploaded CSV is empty. Approval is blocked.",
        "malformed_upload": "Malformed CSV. Approval is blocked.",
        "no_upload": "Upload a CSV to preview or approve an import.",
        "dry_run_preview": "Dry-run preview",
        "approve_import": "Approve import",
        "approval_confirmation": "I understand this writes rows to the append-only ledger.",
        "approval_reason": "Approval reason",
        "preview_summary": "Preview summary",
        "approval_metadata": "Approval metadata",
        "ledger_health": "Ledger health",
        "dashboard_readiness": "Dashboard readiness",
        "duplicate_review": "Duplicate review",
        "correction_review": "Correction review",
        "public_exports": "Public-safe exports",
        "private_exports": "Private exports",
        "download_public_csv": "Download public-safe CSV",
        "download_public_json": "Download public-safe JSON",
        "download_private_csv": "Download private CSV",
        "download_private_json": "Download private JSON",
        "approval_blocked": "Approval blocked until a valid preview exists and confirmation is checked.",
        "stale_preview": "Current upload/input does not match the stored preview. Run a new preview before approval.",
        "preview_ready": "Preview stored. Approval uses this preview_hash until inputs change.",
        "writes_warning": "Approval writes new non-duplicate rows to the append-only ledger.",
    },
    "es": {
        "title": "Centro de Prueba",
        "caption": "Revisión unificada de prueba, verificación de ID, récord por fila/evento y filas locales.",
        "warning": "El Centro de Prueba es solo para analítica y seguimiento de prueba. No garantiza resultados ni ganancias.",
        "workspace": "Workspace",
        "source_counts": "Filas cargadas: {total} total, {local} locales, {ledger} ledger.",
        "local_rows": "Filas",
        "row_record": "Récord por fila",
        "events": "Eventos",
        "event_record": "Récord por evento",
        "tabs": ["Resumen", "Verificación de ID", "Auditoría de prueba", "Fila vs evento", "Filas locales", "Control de ledger"],
        "public_summary": "Resumen de prueba pública",
        "no_rows": "Todavía no hay filas locales ni de ledger.",
        "public_safe_rows": "Filas seguras para público",
        "research_review_rows": "Filas investigación/revisión",
        "legacy_dashboard": "Abrir Panel Público de Prueba anterior",
        "legacy_control": "Abrir Centro de Control de Prueba anterior",
        "proof_id": "ID de prueba",
        "enter_proof_id": "Ingresa un ID de prueba para verificar una fila local.",
        "no_proof_id": "No se encontró una fila local con ese ID de prueba.",
        "ledger_type": "Tipo de ledger",
        "forward_locked": "Bloqueada antes del inicio",
        "public_safe": "Segura para público",
        "grade": "Calificación",
        "yes": "Sí",
        "no": "No",
        "proof_audit": "Auditoría de prueba",
        "no_audit_rows": "No hay filas disponibles para auditoría.",
        "row_vs_event": "Récord por fila vs evento",
        "row_summary": "Resumen por fila",
        "event_summary": "Resumen por evento",
        "event_caption": "Usa conteos por evento cuando varias filas pertenecen al mismo partido/juego.",
        "local_proof_rows": "Filas de prueba",
        "event_level_rows": "Filas de prueba por evento",
        "row_level_rows": "Filas por mercado",
        "show_row_level": "Mostrar filas individuales por mercado",
        "duplicate_events": "Eventos con varias filas",
        "duplicate_event_rows": "Filas extra por mercado",
        "download_rows": "Descargar filas de prueba",
        "ledger_control": "Control de ledger",
        "ledger_workspace_id": "ID de workspace del ledger",
        "source_key": "source_key",
        "upload_csv": "Subir CSV de prueba/rendimiento",
        "upload_status": "Estado de carga",
        "rows_detected": "Filas detectadas",
        "columns_detected": "Columnas detectadas",
        "missing_fields": "Campos recomendados faltantes",
        "empty_upload": "El CSV subido está vacío. La aprobación está bloqueada.",
        "malformed_upload": "CSV malformado. La aprobación está bloqueada.",
        "no_upload": "Sube un CSV para previsualizar o aprobar una importación.",
        "dry_run_preview": "Vista previa dry-run",
        "approve_import": "Aprobar importación",
        "approval_confirmation": "Entiendo que esto escribe filas al ledger append-only.",
        "approval_reason": "Motivo de aprobación",
        "preview_summary": "Resumen de vista previa",
        "approval_metadata": "Metadatos de aprobación",
        "ledger_health": "Salud del ledger",
        "dashboard_readiness": "Preparación del dashboard",
        "duplicate_review": "Revisión de duplicados",
        "correction_review": "Revisión de correcciones",
        "public_exports": "Exportaciones seguras para público",
        "private_exports": "Exportaciones privadas",
        "download_public_csv": "Descargar CSV público seguro",
        "download_public_json": "Descargar JSON público seguro",
        "download_private_csv": "Descargar CSV privado",
        "download_private_json": "Descargar JSON privado",
        "approval_blocked": "Aprobación bloqueada hasta que exista una vista previa válida y la confirmación esté marcada.",
        "stale_preview": "La carga/entrada actual no coincide con la vista previa guardada. Ejecuta una nueva vista previa antes de aprobar.",
        "preview_ready": "Vista previa guardada. La aprobación usa este preview_hash hasta que cambien las entradas.",
        "writes_warning": "La aprobación escribe filas nuevas no duplicadas al ledger append-only.",
    },
}


def t(key: str):
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def to_records(value) -> list[dict]:
    frame = pd.DataFrame(value) if value is not None else pd.DataFrame()
    if frame.empty:
        return []
    return frame.fillna("").to_dict("records")


def merge_rows(*parts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for part in parts:
        for row in part:
            proof_id = safe_text(row.get("proof_id"))
            event = safe_text(row.get("event") or row.get("event_name") or row.get("matchup"))
            pick = safe_text(row.get("prediction") or row.get("pick") or row.get("selection"))
            market = safe_text(row.get("market_type") or row.get("market"))
            line = safe_text(row.get("line_point") or row.get("line") or row.get("handicap") or row.get("total"))
            start = safe_text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time"))
            key = proof_id or "|".join([event.lower(), pick.lower(), market.lower(), line.lower(), start.lower()])
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(dict(row))
    return rows


def _uploaded_file_bytes(uploaded_file) -> bytes:
    if uploaded_file is None:
        return b""
    return uploaded_file.getvalue()


def proof_center_upload_fingerprint(uploaded_file, workspace_id: str, source_key: str, source_file: str) -> str:
    payload = "|".join([
        safe_text(getattr(uploaded_file, "name", source_file)),
        hashlib.sha256(_uploaded_file_bytes(uploaded_file)).hexdigest(),
        safe_text(workspace_id),
        safe_text(source_key),
        safe_text(source_file),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_uploaded_proof_csv(uploaded_file) -> tuple[pd.DataFrame, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    if uploaded_file is None:
        return pd.DataFrame(), warnings, errors
    try:
        data = _uploaded_file_bytes(uploaded_file)
        frame = pd.read_csv(io.BytesIO(data))
    except Exception as exc:
        return pd.DataFrame(), warnings, [f"{t('malformed_upload')}: {exc}"]
    if frame.empty:
        errors.append(t("empty_upload"))
        return frame, warnings, errors
    columns = {str(column).strip().lower() for column in frame.columns}
    missing = [field for field in PROOF_CENTER_REQUIRED_UPLOAD_FIELDS if field not in columns]
    if not any(field in columns for field in PROOF_CENTER_ODDS_FIELDS):
        missing.append("odds/decimal_odds")
    if missing:
        warnings.append(f"{t('missing_fields')}: {', '.join(missing)}")
    return frame, warnings, errors


def _preview_matches_current_input(current_fingerprint: str) -> bool:
    preview = st.session_state.get(PROOF_CENTER_IMPORT_PREVIEW_KEY) or {}
    return bool(preview) and st.session_state.get(PROOF_CENTER_INPUT_FINGERPRINT_KEY) == current_fingerprint


def _display_dict(title: str, value: dict):
    st.markdown(f"**{title}**")
    st.json(value or {})


def _approval_blocked(preview: dict, current_fingerprint: str, upload_errors: list[str], source_key: str, confirmed: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if source_key not in PROOF_CENTER_SOURCE_KEY_OPTIONS:
        reasons.append("unsupported source_key")
    if upload_errors:
        reasons.extend(upload_errors)
    if not preview:
        reasons.append("no preview exists")
    elif preview.get("errors"):
        reasons.append("preview has errors")
    elif int(preview.get("rows_to_add", 0) or 0) <= 0:
        reasons.append("preview rows_to_add is 0")
    elif not _preview_matches_current_input(current_fingerprint):
        reasons.append(t("stale_preview"))
    if not confirmed:
        reasons.append("approval confirmation is required")
    return bool(reasons), reasons


st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))

workspace_id = normalize_workspace_id(st.session_state.get("aba_test_window_id", "test_01"))
st.caption(f"{t('workspace')}: {workspace_id}")

store = LocalStorage()
local_rows = store.load_rows()
ledger_rows = to_records(load_persistent_ledger(workspace_id=workspace_id, active_only=False))
if not ledger_rows and workspace_id != "default":
    ledger_rows = to_records(load_persistent_ledger(active_only=False))
rows = merge_rows(local_rows, ledger_rows)
st.caption(t("source_counts").format(total=len(rows), local=len(local_rows), ledger=len(ledger_rows)))

row_summary = summarize_row_level(rows)
event_summary = summarize_event_level(rows)

col1, col2, col3, col4 = st.columns(4)
col1.metric(t("local_rows"), len(rows))
col2.metric(t("row_record"), f"{row_summary['wins']}-{row_summary['losses']}")
col3.metric(t("events"), event_summary.get("events", 0))
col4.metric(t("event_record"), f"{event_summary['wins']}-{event_summary['losses']}")

tabs = st.tabs(t("tabs"))

with tabs[0]:
    st.subheader(t("public_summary"))
    if not rows:
        st.info(t("no_rows"))
    else:
        public_rows = [row for row in rows if public_metric_allowed(row)]
        st.metric(t("public_safe_rows"), len(public_rows))
        st.metric(t("research_review_rows"), max(0, len(rows) - len(public_rows)))
        st.dataframe(localize_dataframe(pd.DataFrame([{"scope": "row_level", **row_summary}, {"scope": "event_level", **event_summary}]), LANG), use_container_width=True)
    st.page_link("pages/public_proof_dashboard.py", label=t("legacy_dashboard"))
    st.page_link("pages/proof_control_center.py", label=t("legacy_control"))

with tabs[1]:
    st.subheader(t("proof_id"))
    proof_id = st.text_input(t("proof_id"), "").strip()
    if not proof_id:
        st.info(t("enter_proof_id"))
    else:
        matches = [row for row in rows if str(row.get("proof_id") or "").strip() == proof_id]
        if not matches:
            st.error(t("no_proof_id"))
        else:
            row = matches[0]
            ledger_type = localize_value(classify_ledger_type(row), LANG)
            future_locked = is_future_locked(row)
            public_safe = public_metric_allowed(row)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("ledger_type"), ledger_type)
            c2.metric(t("forward_locked"), t("yes") if future_locked else t("no"))
            c3.metric(t("public_safe"), t("yes") if public_safe else t("no"))
            c4.metric(t("grade"), localize_value(str(row.get("grade") or row.get("result") or "pending"), LANG))
            st.write({
                t("proof_id"): row.get("proof_id"),
                "hash_prueba" if LANG == "es" else "proof_hash": row.get("proof_hash"),
                "bloqueado_utc" if LANG == "es" else "locked_at_utc": row.get("locked_at_utc"),
                "inicio_evento" if LANG == "es" else "event_start_time": row.get("event_start_time") or row.get("commence_time"),
                "evento" if LANG == "es" else "event_name": row.get("event_name") or row.get("event") or row.get("matchup"),
                "selección" if LANG == "es" else "prediction": row.get("prediction") or row.get("pick") or row.get("selection"),
                "mercado" if LANG == "es" else "market": row.get("market") or row.get("market_type"),
                "estado_auditoría_cuotas" if LANG == "es" else "odds_audit_status": row.get("odds_audit_status") or row.get("audit_status"),
            })
            st.info(build_client_safe_pick_summary(row))

with tabs[2]:
    st.subheader(t("proof_audit"))
    if not rows:
        st.info(t("no_audit_rows"))
    else:
        audit_rows = []
        for row in rows:
            audit_rows.append({
                "proof_id": row.get("proof_id", ""),
                "ledger_type": classify_ledger_type(row),
                "forward_locked": is_future_locked(row),
                "public_safe": public_metric_allowed(row),
                "has_proof_hash": bool(row.get("proof_hash")),
                "grade": row.get("grade") or row.get("result") or "pending",
                "event": row.get("event_name") or row.get("event") or row.get("matchup"),
            })
        st.dataframe(localize_dataframe(pd.DataFrame(audit_rows), LANG), use_container_width=True)

with tabs[3]:
    st.subheader(t("row_vs_event"))
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{t('row_summary')}**")
        st.dataframe(localize_dataframe(pd.DataFrame([row_summary]), LANG), use_container_width=True)
    with right:
        st.markdown(f"**{t('event_summary')}**")
        st.dataframe(localize_dataframe(pd.DataFrame([event_summary]), LANG), use_container_width=True)
    st.caption(t("event_caption"))

with tabs[4]:
    st.subheader(t("local_proof_rows"))
    if rows:
        duplicate_summary = event_duplicate_summary(rows)
        c1, c2, c3 = st.columns(3)
        c1.metric(t("events"), duplicate_summary["unique_events"])
        c2.metric(t("duplicate_events"), duplicate_summary["duplicate_events"])
        c3.metric(t("duplicate_event_rows"), duplicate_summary["duplicate_event_rows"])
        show_row_level = st.checkbox(t("show_row_level"), value=False)
        display_rows = rows if show_row_level else collapse_to_event_rows(rows)
        label = t("row_level_rows") if show_row_level else t("event_level_rows")
        st.markdown(f"**{label}**")
        df = pd.DataFrame(display_rows)
        st.dataframe(localize_dataframe(df, LANG), use_container_width=True)
        st.download_button(t("download_rows"), df.to_csv(index=False).encode("utf-8"), file_name="local_proof_rows.csv", mime="text/csv")
    else:
        st.info(t("no_rows"))

with tabs[5]:
    st.subheader(t("ledger_control"))
    control_workspace = normalize_workspace_id(st.text_input(t("ledger_workspace_id"), value=workspace_id, key="proof_center_ledger_workspace_id"))
    source_key = st.selectbox(t("source_key"), PROOF_CENTER_SOURCE_KEY_OPTIONS, index=PROOF_CENTER_SOURCE_KEY_OPTIONS.index("uploaded_csv"), key="proof_center_source_key")
    uploaded_csv = st.file_uploader(t("upload_csv"), type=["csv"], key="proof_center_import_upload")
    source_file = safe_text(getattr(uploaded_csv, "name", "uploaded.csv")) or "uploaded.csv"
    approval_reason = st.text_input(t("approval_reason"), value="", key="proof_center_approval_reason")
    upload_frame, upload_warnings, upload_errors = validate_uploaded_proof_csv(uploaded_csv)
    current_fingerprint = proof_center_upload_fingerprint(uploaded_csv, control_workspace, source_key, source_file) if uploaded_csv is not None else ""

    st.markdown(f"**{t('upload_status')}**")
    if uploaded_csv is None:
        st.info(t("no_upload"))
    else:
        c1, c2 = st.columns(2)
        c1.metric(t("rows_detected"), len(upload_frame))
        c2.metric(t("columns_detected"), len(upload_frame.columns) if not upload_frame.empty else 0)
        st.write(list(upload_frame.columns) if not upload_frame.empty else [])
        for warning in upload_warnings:
            st.warning(warning)
        for error in upload_errors:
            st.error(error)

    if st.button(t("dry_run_preview"), disabled=uploaded_csv is None or bool(upload_errors), key="proof_center_dry_run_preview"):
        preview = proof_center_control_service.preview_ledger_import(upload_frame, control_workspace, source_key, source_file=source_file)
        duplicate_review = proof_center_control_service.review_duplicate_rows(upload_frame, control_workspace, source_key, source_file=source_file)
        correction_review = proof_center_control_service.review_correction_rows(upload_frame, control_workspace, source_key, source_file=source_file)
        st.session_state[PROOF_CENTER_IMPORT_PREVIEW_KEY] = preview
        st.session_state[PROOF_CENTER_INPUT_FINGERPRINT_KEY] = current_fingerprint
        st.session_state[PROOF_CENTER_UPLOAD_SNAPSHOT_KEY] = upload_frame.to_dict("records")
        st.session_state["proof_center_duplicate_review"] = duplicate_review
        st.session_state["proof_center_correction_review"] = correction_review
        st.info(t("preview_ready"))

    preview = st.session_state.get(PROOF_CENTER_IMPORT_PREVIEW_KEY, {})
    duplicate_review = st.session_state.get("proof_center_duplicate_review", {})
    correction_review = st.session_state.get("proof_center_correction_review", {})
    approval_result = st.session_state.get(PROOF_CENTER_APPROVAL_KEY, {})

    if preview:
        _display_dict(t("preview_summary"), {
            "rows_seen": preview.get("rows_seen"),
            "rows_to_add": preview.get("rows_to_add"),
            "duplicates_detected": preview.get("duplicates_detected"),
            "rejected_rows": preview.get("rejected_rows"),
            "correction_rows_detected": preview.get("correction_rows_detected"),
            "preview_hash": preview.get("preview_hash"),
            "warnings": preview.get("warnings"),
            "errors": preview.get("errors"),
        })
    _display_dict(t("ledger_health"), proof_center_control_service.get_ledger_health(control_workspace))
    _display_dict(t("dashboard_readiness"), proof_center_control_service.get_dashboard_readiness(control_workspace))
    _display_dict(t("duplicate_review"), duplicate_review)
    _display_dict(t("correction_review"), correction_review)

    st.warning(t("writes_warning"))
    confirmed = st.checkbox(t("approval_confirmation"), value=False, key="proof_center_approval_confirmation")
    blocked, block_reasons = _approval_blocked(preview, current_fingerprint, upload_errors, source_key, confirmed)
    if block_reasons:
        st.info(f"{t('approval_blocked')}: {'; '.join(block_reasons)}")

    if st.button(t("approve_import"), disabled=blocked, key="proof_center_approve_import"):
        if not _preview_matches_current_input(current_fingerprint):
            st.error(t("stale_preview"))
        else:
            snapshot_rows = st.session_state.get(PROOF_CENTER_UPLOAD_SNAPSHOT_KEY, [])
            approval_result = proof_center_control_service.approve_ledger_import(
                snapshot_rows,
                control_workspace,
                source_key,
                source_file=source_file,
                approval_reason=approval_reason,
            )
            st.session_state[PROOF_CENTER_APPROVAL_KEY] = approval_result

    if approval_result:
        _display_dict(t("approval_metadata"), {
            "approved": approval_result.get("approved"),
            "approved_at_utc": approval_result.get("approved_at_utc"),
            "approval_reason": approval_result.get("approval_reason"),
            "blocked_reason": approval_result.get("blocked_reason"),
            "write_attempted": approval_result.get("write_attempted"),
            "write_successful": approval_result.get("write_successful"),
            "preview_hash": approval_result.get("preview_hash"),
            "rows_to_add": (approval_result.get("write_result") or {}).get("rows_to_add"),
            "duplicates_detected": (approval_result.get("write_result") or {}).get("duplicates_detected"),
            "rejected_rows": (approval_result.get("write_result") or {}).get("rejected_rows"),
        })

    public_exports = proof_center_control_service.get_public_proof_exports(control_workspace)
    private_exports = proof_center_control_service.get_private_proof_exports(control_workspace)
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{t('public_exports')}**")
        st.download_button(t("download_public_csv"), public_exports["csv"].encode("utf-8"), file_name="public_safe_proof_export.csv", mime="text/csv")
        st.download_button(t("download_public_json"), public_exports["json"].encode("utf-8"), file_name="public_safe_proof_export.json", mime="application/json")
    with right:
        st.markdown(f"**{t('private_exports')}**")
        st.download_button(t("download_private_csv"), private_exports["csv"].encode("utf-8"), file_name="private_proof_export.csv", mime="text/csv")
        st.download_button(t("download_private_json"), private_exports["json"].encode("utf-8"), file_name="private_proof_export.json", mime="application/json")
