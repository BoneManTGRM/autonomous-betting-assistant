from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.proof_archive_service import (
    PROOF_ARCHIVE_PACKAGE_TYPES,
    PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES,
    build_proof_archive_index,
    build_proof_archive_snapshot,
    compare_proof_archive_snapshots,
    export_proof_archive_index_json,
    export_proof_archive_snapshot_json,
    validate_proof_archive_snapshot,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Proof Archive", layout="wide")
LANG = render_app_sidebar("proof_archive_viewer", language_key="proof_archive_language")

PROOF_ARCHIVE_VIEWER_SNAPSHOT_KEY = "proof_archive_viewer_snapshot"
PROOF_ARCHIVE_VIEWER_INDEX_KEY = "proof_archive_viewer_index"
PROOF_ARCHIVE_VIEWER_PREVIOUS_KEY = "proof_archive_viewer_previous_snapshot"

TEXT = {
    "en": {
        "title": "Proof Archive + Version History",
        "caption": "Read-only archive/version view for proof packages, package hashes, QA hashes, and export hashes.",
        "workspace_id": "Workspace ID",
        "package_type": "package_type",
        "build_snapshot": "Build archive snapshot",
        "build_index": "Build archive index",
        "snapshot_ready": "Archive snapshot built in memory. No files were written.",
        "index_ready": "Archive index built in memory. No files were written.",
        "archive_summary": "Archive summary",
        "archive_index": "Archive index",
        "version_compare": "Version comparison",
        "private_internal_only": "PRIVATE/INTERNAL ONLY",
        "public_client_safe": "PUBLIC/CLIENT SAFE",
        "archive_ready": "ARCHIVE READY",
        "archive_failed": "ARCHIVE QA FAILED",
        "validation": "Archive validation",
        "download_snapshot": "Download archive snapshot JSON",
        "download_index": "Download archive index JSON",
        "store_previous": "Use current snapshot as comparison baseline",
        "no_snapshot": "Build an archive snapshot to view version history fields.",
    },
    "es": {
        "title": "Archivo de Prueba + Historial de Versiones",
        "caption": "Vista solo lectura para archivo/versiones de paquetes de prueba, package hashes, QA hashes y export hashes.",
        "workspace_id": "ID de workspace",
        "package_type": "package_type",
        "build_snapshot": "Crear snapshot de archivo",
        "build_index": "Crear índice de archivo",
        "snapshot_ready": "Snapshot de archivo creado en memoria. No se escribieron archivos.",
        "index_ready": "Índice de archivo creado en memoria. No se escribieron archivos.",
        "archive_summary": "Resumen del archivo",
        "archive_index": "Índice del archivo",
        "version_compare": "Comparación de versiones",
        "private_internal_only": "PRIVATE/INTERNAL ONLY",
        "public_client_safe": "PUBLIC/CLIENT SAFE",
        "archive_ready": "ARCHIVE READY",
        "archive_failed": "ARCHIVE QA FAILED",
        "validation": "Validación del archivo",
        "download_snapshot": "Descargar JSON del snapshot de archivo",
        "download_index": "Descargar JSON del índice de archivo",
        "store_previous": "Usar snapshot actual como baseline de comparación",
        "no_snapshot": "Crea un snapshot de archivo para ver campos de historial de versiones.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _snapshot_filename(snapshot: dict) -> str:
    return f"aba_proof_archive_{safe_text(snapshot.get('workspace_id'))}_{safe_text(snapshot.get('package_type'))}_{_hash_fragment(snapshot.get('archive_hash'))}.json"


def _index_filename(index: dict) -> str:
    return f"aba_proof_archive_index_{safe_text(index.get('workspace_id'))}_{_hash_fragment(index.get('archive_index_hash'))}.json"


def _snapshot_table(snapshot: dict) -> pd.DataFrame:
    fields = (
        "schema_version",
        "archive_id",
        "archive_hash",
        "created_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "private_export_hash",
        "qa_report_id",
        "qa_report_hash",
        "proof_ready",
        "proof_grade",
        "overall_passed",
        "archive_status",
        "redaction_passed",
        "row_count",
        "unique_events",
        "ROI",
        "profit_units",
        "average_CLV",
    )
    return pd.DataFrame([{"field": field, "value": snapshot.get(field, "")} for field in fields if field in snapshot])


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="proof_archive_workspace_id"))
package_type = st.selectbox(t("package_type"), PROOF_ARCHIVE_PACKAGE_TYPES, index=0, key="proof_archive_package_type")

left, right = st.columns(2)
with left:
    if st.button(t("build_snapshot"), key="proof_archive_build_snapshot"):
        snapshot = build_proof_archive_snapshot(workspace_id, package_type)
        st.session_state[PROOF_ARCHIVE_VIEWER_SNAPSHOT_KEY] = snapshot
        st.info(t("snapshot_ready"))
with right:
    if st.button(t("build_index"), key="proof_archive_build_index"):
        index = build_proof_archive_index(workspace_id)
        st.session_state[PROOF_ARCHIVE_VIEWER_INDEX_KEY] = index
        st.info(t("index_ready"))

snapshot = st.session_state.get(PROOF_ARCHIVE_VIEWER_SNAPSHOT_KEY, {})
index = st.session_state.get(PROOF_ARCHIVE_VIEWER_INDEX_KEY, {})
previous = st.session_state.get(PROOF_ARCHIVE_VIEWER_PREVIOUS_KEY, {})

if snapshot:
    validation = validate_proof_archive_snapshot(snapshot)
    is_private = safe_text(snapshot.get("package_type")) in PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES
    status_cols = st.columns(4)
    status_cols[0].metric("archive_hash", safe_text(snapshot.get("archive_hash"))[:24])
    status_cols[1].metric("package_hash", safe_text(snapshot.get("package_hash"))[:24])
    status_cols[2].metric("qa_report_hash", safe_text(snapshot.get("qa_report_hash"))[:24])
    status_cols[3].metric("overall_passed", str(bool(snapshot.get("overall_passed"))))
    st.write({
        t("private_internal_only") if is_private else t("public_client_safe"): True,
        t("archive_ready") if snapshot.get("overall_passed") else t("archive_failed"): True,
    })
    st.markdown(f"### {t('archive_summary')}")
    st.dataframe(_snapshot_table(snapshot), use_container_width=True, hide_index=True)
    with st.expander(t("validation"), expanded=False):
        st.json(validation)
    if previous:
        st.markdown(f"### {t('version_compare')}")
        st.json(compare_proof_archive_snapshots(previous, snapshot))
    if st.button(t("store_previous"), key="proof_archive_store_previous"):
        st.session_state[PROOF_ARCHIVE_VIEWER_PREVIOUS_KEY] = snapshot
    st.download_button(
        t("download_snapshot"),
        export_proof_archive_snapshot_json(snapshot, public_safe=True).encode("utf-8"),
        file_name=_snapshot_filename(snapshot),
        mime="application/json",
        key=f"proof_archive_snapshot_json_{safe_text(snapshot.get('archive_hash'))}",
    )
else:
    st.info(t("no_snapshot"))

if index:
    st.markdown(f"### {t('archive_index')}")
    rows = []
    for item in index.get("snapshots") or []:
        rows.append({
            "package_type": item.get("package_type"),
            "archive_id": item.get("archive_id"),
            "archive_hash": item.get("archive_hash"),
            "package_hash": item.get("package_hash"),
            "qa_report_hash": item.get("qa_report_hash"),
            "proof_ready": item.get("proof_ready"),
            "overall_passed": item.get("overall_passed"),
            "archive_status": item.get("archive_status"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.download_button(
        t("download_index"),
        export_proof_archive_index_json(index, public_safe=True).encode("utf-8"),
        file_name=_index_filename(index),
        mime="application/json",
        key=f"proof_archive_index_json_{safe_text(index.get('archive_index_hash'))}",
    )
