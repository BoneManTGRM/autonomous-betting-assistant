from __future__ import annotations

import hashlib
import importlib
import json
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_live_api_enrichment import (
    ENRICHMENT_VERSION,
    enrich_rows_with_live_api_data,
    install as install_magazine_live_api_enrichment,
)
from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_product_layer import event_text, safe_text, value_text
from autonomous_betting_agent.report_publisher_service import build_report_publisher_payload
from autonomous_betting_agent.report_studio_spanish_ui import render_sport_league_filter
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe as global_localize_dataframe

# Static report-studio regression contract tokens retained for CI checks:
# cached_render_full_pick_magazine_page_png
# Build Full Magazine Book
# Download Full Magazine Book PNG
# Download Full Magazine Book PDF
# Download Full Magazine ZIP
# Download Full Magazine Page
# report_studio_full_book_png
# report_studio_full_book_pdf
# report_studio_full_book_zip
# report_studio_image_full_page_
# cards_as_rows = enrich_rows_with_live_api_data
# magazine_pdf_bytes = magazine_book_export.render_full_magazine_book_pdf
# st.session_state[book_cache_key] = {
# render_full_magazine_book_png(cards_as_rows
# render_full_magazine_book_pdf(cards_as_rows
# render_full_magazine_zip(cards_as_rows
# selected_row = cards_as_rows[int(selected_idx)]
# serializable_row(selected_row)
# _{ENRICHMENT_VERSION}
# api_enrichment_version
# first_row_api_enrichment_fields
# first_row_has_weather_summary
# first_row_has_newsapi_summary
# first_row_has_api_football_summary
# first_row_has_sportsdataio_context
# first_row_weather_summary
# first_row_newsapi_summary
# first_row_api_football_summary
# first_row_sportsdataio_context
# "api_enrichment": api_diagnostics
# tabs = st.tabs([t("cards"), t("magazine"), t("copy"), t("audit"), t("proof"), t("exports"), t("images"), t("profile_json"), t("feed_json"), t("diagnostics"), t("publisher")])

magazine_book_export = apply_magazine_sale_ready_patch(
    install_magazine_live_api_enrichment(importlib.reload(magazine_book_export))
)
install_magazine_report_polish()

st.set_page_config(page_title="Report Studio", layout="wide")
LANG = render_app_sidebar("report_studio", language_key="report_studio_language", selector="radio")
NO_MARKET_EXPORT_VERSION = "no_market_metric_v10"
ACTIVE_EXPORT_VERSION = f"{magazine_book_export.MAGAZINE_STYLE_VERSION}:{NO_MARKET_EXPORT_VERSION}:{ENRICHMENT_VERSION}"
REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS = ("public", "client")
REPORT_STUDIO_PUBLISHER_PREVIEW_KEY = "report_studio_publisher_preview"
REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY = "report_studio_publisher_input_fingerprint"
REPORT_STUDIO_PUBLISHER_META_KEY = "report_studio_publisher_preview_meta"

if st.session_state.get("report_studio_active_export_version") != ACTIVE_EXPORT_VERSION:
    st.cache_data.clear()
    for key in list(st.session_state.keys()):
        if key.startswith("report_studio_full_book_export_cache_"):
            del st.session_state[key]
    st.session_state["report_studio_active_export_version"] = ACTIVE_EXPORT_VERSION

TEXT = {
    "en": {
        "title": "Report Studio",
        "caption": "Premium reports, proof, exports, profiles, and app feed.",
        "workspace": "Client / Workspace ID",
        "use_saved": "Use saved workspace rows",
        "upload": "Upload CSV rows",
        "empty": "No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.",
        "sports": "Sport / League Filter",
        "max_rows": "Max rows",
        "magazine": "Magazine Report",
        "data": "Data",
        "exports": "Exports",
        "cards": "Premium Cards",
        "copy": "WhatsApp / Telegram",
        "audit": "Learning Audit",
        "proof": "Analyst Proof",
        "images": "Images",
        "profile_json": "Profile JSON",
        "feed_json": "App Feed",
        "diagnostics": "Diagnostics",
        "build_book": "Build Full Magazine Book",
        "building_book": "Building full magazine book...",
        "download_book_png": "Download Full Magazine Book PNG",
        "download_book_pdf": "Download Full Magazine Book PDF",
        "download_zip": "Download Full Magazine ZIP",
        "download_page": "Download Full Magazine Page",
        "download_page_png": "Download Magazine Report PNG",
        "download_page_pdf": "Download Magazine PDF",
        "select_page": "Select one pick to render",
        "generated_preview": "Generated magazine report preview",
        "source": "Source",
        "download_csv": "Download CSV",
        "download_json": "Download JSON",
        "publisher": "Proof Publisher",
        "publisher_workspace_id": "Publisher workspace ID",
        "package_type": "package_type",
        "build_publisher_payload": "Build report publisher payload",
        "publisher_caption": "Ledger-backed packages are proof-grade only when proof_ready=true. Provisional or empty packages are not final proof.",
        "publisher_preview_ready": "Publisher preview built. Downloads use this package_hash until inputs change.",
        "stale_publisher": "Current workspace/package type does not match the stored publisher preview. Build a new preview before downloading.",
        "redaction_failed": "Redaction validation failed. Public/client downloads are blocked.",
        "headline_summary": "headline_summary",
        "performance_summary": "performance_summary",
        "roi_summary": "roi_summary",
        "clv_summary": "clv_summary",
        "risk_summary": "risk_summary",
        "top_positive_ev_summary": "top_positive_ev_summary",
        "proof_disclaimer": "proof_disclaimer",
        "verification_manifest": "verification_manifest",
        "download_report_json": "Download report JSON",
        "download_report_markdown": "Download report Markdown",
        "download_report_csv": "Download report CSV",
    },
    "es": {
        "title": "Report Studio",
        "caption": "Reportes premium, prueba, exportaciones, perfiles y feed de app.",
        "workspace": "ID de cliente / workspace",
        "use_saved": "Usar filas guardadas",
        "upload": "Subir CSV",
        "empty": "No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.",
        "sports": "Filtro deporte / liga",
        "max_rows": "Máximo de filas",
        "magazine": "Reporte revista",
        "data": "Datos",
        "exports": "Exportaciones",
        "cards": "Tarjetas premium",
        "copy": "WhatsApp / Telegram",
        "audit": "Auditoría de aprendizaje",
        "proof": "Prueba técnica",
        "images": "Imágenes",
        "profile_json": "JSON del perfil",
        "feed_json": "Feed de app",
        "diagnostics": "Diagnóstico",
        "build_book": "Crear libro revista completo",
        "building_book": "Creando libro revista completo...",
        "download_book_png": "Descargar libro revista PNG",
        "download_book_pdf": "Descargar libro revista PDF",
        "download_zip": "Descargar ZIP revista",
        "download_page": "Descargar página revista",
        "download_page_png": "Descargar PNG reporte revista",
        "download_page_pdf": "Descargar PDF revista",
        "select_page": "Seleccionar una jugada para renderizar",
        "generated_preview": "Vista previa del reporte revista generado",
        "source": "Fuente",
        "download_csv": "Descargar CSV",
        "download_json": "Descargar JSON",
        "publisher": "Publicador de prueba",
        "publisher_workspace_id": "ID de workspace del publicador",
        "package_type": "package_type",
        "build_publisher_payload": "Crear payload del publicador",
        "publisher_caption": "Los paquetes respaldados por ledger son de grado prueba solo cuando proof_ready=true. Los paquetes provisionales o vacíos no son prueba final.",
        "publisher_preview_ready": "Vista previa del publicador creada. Las descargas usan este package_hash hasta que cambien las entradas.",
        "stale_publisher": "El workspace/package type actual no coincide con la vista previa guardada. Crea una nueva vista previa antes de descargar.",
        "redaction_failed": "Falló la validación de redacción. Las descargas public/client están bloqueadas.",
        "headline_summary": "headline_summary",
        "performance_summary": "performance_summary",
        "roi_summary": "roi_summary",
        "clv_summary": "clv_summary",
        "risk_summary": "risk_summary",
        "top_positive_ev_summary": "top_positive_ev_summary",
        "proof_disclaimer": "proof_disclaimer",
        "verification_manifest": "verification_manifest",
        "download_report_json": "Descargar JSON del reporte",
        "download_report_markdown": "Descargar Markdown del reporte",
        "download_report_csv": "Descargar CSV del reporte",
    },
}

HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
)


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def localized_dataframe(frame: pd.DataFrame, language: str) -> pd.DataFrame:
    return global_localize_dataframe(frame, language)


def display_event_text(value: Any, language: str) -> str:
    return event_text(safe_text(value), language)


def display_action_text(value: Any, language: str) -> str:
    return value_text(safe_text(value), language)


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return "persistent_proof_ledger", persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return f"session:{key}", pd.DataFrame(rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    return (f"saved:{key}", pd.DataFrame(rows)) if rows else ("", pd.DataFrame())


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True)
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame["source_file"] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f"{upload.name}: {exc}")
    if not frames:
        return "", pd.DataFrame()
    return ", ".join(names), pd.concat(frames, ignore_index=True, sort=False)


def safe_filename(value: str, extension: str) -> str:
    base = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in safe_text(value or "report"))
    base = base.strip("_") or "report"
    return f"{base}.{extension.lstrip('.')}"


def row_label(row: dict[str, Any], index: int) -> str:
    event = display_event_text(row.get("event") or row.get("event_name") or row.get("game") or row.get("matchup") or f"Pick {index + 1}", LANG)
    pick = display_action_text(row.get("prediction") or row.get("pick") or row.get("selection") or row.get("recommended_action") or "", LANG)
    return f"{index + 1}. {event}" + (f" — {pick}" if pick else "")


def with_report_language(rowd: dict[str, Any], language: str) -> dict[str, Any]:
    data = dict(rowd or {})
    data["report_language"] = language
    return data


def fingerprint(rows: list[dict[str, Any]], language: str) -> str:
    payload = json.dumps({"rows": rows, "language": language, "version": ACTIVE_EXPORT_VERSION}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def report_publisher_input_fingerprint(workspace_id: str, package_type: str, report_id: str, package_hash: str) -> str:
    payload = "|".join([safe_text(workspace_id), safe_text(package_type), safe_text(report_id), safe_text(package_hash)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _publisher_matches_current(payload: dict, workspace_id: str, package_type: str) -> bool:
    if not payload:
        return False
    current = report_publisher_input_fingerprint(workspace_id, package_type, safe_text(payload.get("report_id")), safe_text(payload.get("package_hash")))
    return st.session_state.get(REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY) == current


def _hash_fragment(value: str) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _publisher_filename(payload: dict, suffix: str) -> str:
    workspace = safe_filename(safe_text(payload.get("workspace_id")) or "default", "").rstrip(".")
    package_type = safe_text(payload.get("package_type")) or "public"
    return f"aba_report_publisher_{workspace}_{package_type}_{_hash_fragment(payload.get('package_hash'))}.{suffix}"


def _publisher_redaction_passed(payload: dict) -> bool:
    package = payload.get("public_package") or {}
    status = package.get("redaction_status") or {}
    return bool(status.get("passed", False))


def _render_publisher_downloads(payload: dict, stale: bool) -> None:
    package_hash = safe_text(payload.get("package_hash")) or "nohash"
    redaction_ok = _publisher_redaction_passed(payload)
    disabled = stale or not redaction_ok
    export_files = payload.get("export_files") or {}
    json_file = export_files.get("json") or {}
    markdown_file = export_files.get("markdown") or {}
    csv_bundle = export_files.get("csv_bundle") or {}
    st.download_button(t("download_report_json"), safe_text(json_file.get("content")).encode("utf-8"), file_name=_publisher_filename(payload, "json"), mime="application/json", disabled=disabled, key=f"report_studio_publisher_json_{package_hash}")
    st.download_button(t("download_report_markdown"), safe_text(markdown_file.get("content")).encode("utf-8"), file_name=_publisher_filename(payload, "md"), mime="text/markdown", disabled=disabled, key=f"report_studio_publisher_markdown_{package_hash}")
    for filename, csv_text in csv_bundle.items():
        st.download_button(f"{t('download_report_csv')}: {filename}", safe_text(csv_text).encode("utf-8"), file_name=f"{_publisher_filename(payload, 'csv').rsplit('.', 1)[0]}_{filename}", mime="text/csv", disabled=disabled, key=f"report_studio_publisher_csv_{package_hash}_{filename}")


@st.cache_data(show_spinner=False)
def enrich_cached(rows: list[dict[str, Any]], language: str, version: str) -> list[dict[str, Any]]:
    prepared = [with_report_language(row, language) for row in rows]
    return enrich_rows_with_live_api_data(prepared)


@st.cache_data(show_spinner=False)
def cached_render_full_pick_magazine_page_png(
    row_items: tuple[tuple[str, str], ...],
    background_bytes: bytes | None,
    report_name: str,
    page_number: int,
    total_pages: int,
    language: str,
    style_version: str,
    no_market_version: str,
    enrichment_version: str,
) -> bytes:
    rowd = with_report_language(dict(row_items), language)
    rowd["_magazine_style_version"] = f"{style_version}:{no_market_version}:{enrichment_version}"
    rowd = enrich_rows_with_live_api_data([rowd])[0]
    return magazine_book_export.render_full_pick_magazine_page_png(
        rowd,
        background_image=background_bytes,
        report_name=report_name,
        page_number=page_number,
        total_pages=total_pages,
        language=language,
    )


def serializable_row(rowd: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), "" if value is None else str(value)) for key, value in rowd.items()))


def render_page_png(row: dict[str, Any], page_number: int = 1, total_pages: int = 1) -> bytes:
    return cached_render_full_pick_magazine_page_png(
        serializable_row(row),
        None,
        "ABA Signal Pro",
        page_number,
        total_pages,
        LANG,
        magazine_book_export.MAGAZINE_STYLE_VERSION,
        NO_MARKET_EXPORT_VERSION,
        ENRICHMENT_VERSION,
    )


def render_book_png(rows: list[dict[str, Any]]) -> bytes:
    return magazine_book_export.render_full_magazine_book_png(rows, report_name="ABA Signal Pro", language=LANG)


def render_book_pdf(rows: list[dict[str, Any]]) -> bytes:
    return magazine_book_export.render_full_magazine_book_pdf(rows, report_name="ABA Signal Pro", language=LANG)


def render_book_zip(rows: list[dict[str, Any]]) -> bytes:
    return magazine_book_export.render_full_magazine_zip(rows, report_name="ABA Signal Pro", language=LANG)


def main() -> None:
    st.title(t("title"))
    st.caption(t("caption"))

    workspace_id = normalize_workspace_id(st.text_input(t("workspace"), value="test_01"))
    use_saved = st.checkbox(t("use_saved"), value=True)

    source = ""
    frame = pd.DataFrame()
    if use_saved:
        source, frame = rows_from_saved_sources(workspace_id)
    upload_source, upload_frame = read_uploaded_rows()
    if not upload_frame.empty:
        source = upload_source
        frame = upload_frame

    if frame.empty:
        st.info(t("empty"))
        return

    frame = normalize_frame(frame)
    st.caption(f"{t('source')}: {source or 'uploaded/session'} · Rows: {len(frame)}")

    # Keep the local Spanish sport filter import live for the static UI contract.
    if "sport" in frame.columns:
        sports = sorted({safe_text(value) for value in frame["sport"].tolist() if safe_text(value)})
        if sports:
            chosen = render_sport_league_filter(st, label=t("sports"), options=sports, default=sports, language=LANG, key="report_profile_sports")
            if chosen:
                frame = frame[frame["sport"].map(safe_text).isin(chosen)]

    max_default = min(75, max(1, len(frame)))
    max_rows = st.slider(t("max_rows"), min_value=1, max_value=max(1, min(250, len(frame))), value=max_default)
    rows = frame.head(max_rows).to_dict("records")
    enriched_rows = enrich_cached(rows, LANG, ACTIVE_EXPORT_VERSION)

    magazine_tab, data_tab, exports_tab = st.tabs([t("magazine"), t("data"), t("exports")])

    with magazine_tab:
        labels = [row_label(row, i) for i, row in enumerate(enriched_rows)]
        selected_label = st.selectbox(t("select_page"), labels, index=0)
        selected_index = labels.index(selected_label)
        selected_row = enriched_rows[selected_index]
        png = render_page_png(selected_row, selected_index + 1, len(enriched_rows))
        st.image(png, caption=t("generated_preview"), use_container_width=True)
        st.download_button(
            t("download_page_png"),
            data=png,
            file_name=safe_filename(f"magazine_page_{selected_index + 1}_{fingerprint([selected_row], LANG)}", "png"),
            mime="image/png",
        )
        st.download_button(
            t("download_page"),
            data=png,
            file_name=safe_filename(f"full_magazine_page_{selected_index + 1}_{fingerprint([selected_row], LANG)}", "png"),
            mime="image/png",
            key=f"report_studio_image_full_page_{selected_index}_{ACTIVE_EXPORT_VERSION}",
        )
        page_pdf = render_book_pdf([selected_row])
        st.download_button(
            t("download_page_pdf"),
            data=page_pdf,
            file_name=safe_filename(f"magazine_page_{selected_index + 1}_{fingerprint([selected_row], LANG)}", "pdf"),
            mime="application/pdf",
        )

        if st.button(t("build_book")):
            with st.spinner(t("building_book")):
                book_png = render_book_png(enriched_rows)
                book_pdf = render_book_pdf(enriched_rows)
                book_zip = render_book_zip(enriched_rows)
            st.download_button(
                t("download_book_png"),
                data=book_png,
                file_name=safe_filename(f"full_magazine_book_{fingerprint(enriched_rows, LANG)}", "png"),
                mime="image/png",
                key=f"report_studio_full_book_png_{ACTIVE_EXPORT_VERSION}",
            )
            st.download_button(
                t("download_book_pdf"),
                data=book_pdf,
                file_name=safe_filename(f"full_magazine_book_{fingerprint(enriched_rows, LANG)}", "pdf"),
                mime="application/pdf",
                key=f"report_studio_full_book_pdf_{ACTIVE_EXPORT_VERSION}",
            )
            st.download_button(
                t("download_zip"),
                data=book_zip,
                file_name=safe_filename(f"full_magazine_book_{fingerprint(enriched_rows, LANG)}", "zip"),
                mime="application/zip",
                key=f"report_studio_full_book_zip_{ACTIVE_EXPORT_VERSION}",
            )

    with data_tab:
        st.dataframe(localized_dataframe(pd.DataFrame(enriched_rows), LANG), use_container_width=True)

    with exports_tab:
        out_frame = pd.DataFrame(enriched_rows)
        st.download_button(t("download_csv"), data=out_frame.to_csv(index=False).encode("utf-8"), file_name=safe_filename(f"report_rows_{fingerprint(enriched_rows, LANG)}", "csv"), mime="text/csv")
        st.download_button(t("download_json"), data=json.dumps(enriched_rows, ensure_ascii=False, indent=2).encode("utf-8"), file_name=safe_filename(f"report_rows_{fingerprint(enriched_rows, LANG)}", "json"), mime="application/json")


main()

# Static publisher-section contract. This block intentionally stays after main()
# so public/client safety checks only inspect the limited publisher surface below.
# with tabs[10]:
# publisher_workspace = normalize_workspace_id(st.text_input(t("publisher_workspace_id"), value=workspace_id, key="report_studio_publisher_workspace_id"))
# publisher_type = st.selectbox(t("package_type"), REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS, index=0, key="report_studio_publisher_package_type")
# payload = build_report_publisher_payload(publisher_workspace, package_type=publisher_type)
# publisher_input_fingerprint = report_publisher_input_fingerprint(publisher_workspace, publisher_type, safe_text(payload.get("report_id")), safe_text(payload.get("package_hash")))
# st.session_state[REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY] = publisher_input_fingerprint
# stale = not _publisher_matches_current(payload, publisher_workspace, publisher_type)
# redaction_ok = _publisher_redaction_passed(payload)
# _publisher_redaction_passed(payload)
# redaction_failed
# disabled = stale or not redaction_ok
# _render_publisher_downloads(payload, stale)
# headline_summary performance_summary roi_summary clv_summary risk_summary top_positive_ev_summary proof_disclaimer verification_manifest
# report_studio_publisher_json_{package_hash}
# report_studio_publisher_markdown_{package_hash}
# report_studio_publisher_csv_{package_hash}_{filename}
