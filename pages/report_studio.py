from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_api_sources import api_provenance
from autonomous_betting_agent.magazine_live_api_enrichment import ENRICHMENT_VERSION, enrich_rows_with_live_api_data, install as install_magazine_live_api_enrichment
from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_feed_service import save_report_feed
from autonomous_betting_agent.report_product_layer import MagazineBrand, event_text, safe_text, value_text
from autonomous_betting_agent.report_publisher_service import build_report_publisher_payload
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary
from autonomous_betting_agent.report_studio_spanish_ui import render_sport_league_filter
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe as global_localize_dataframe, localize_options, localize_value
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

magazine_book_export = apply_magazine_sale_ready_patch(install_magazine_live_api_enrichment(importlib.reload(magazine_book_export)))
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
        "input": "Input rows",
        "workspace": "Client / Workspace ID",
        "use_saved": "Use saved/current workspace rows",
        "upload": "Upload CSV rows",
        "source": "Source",
        "empty": "No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.",
        "profile": "White-label profile",
        "profile_id": "Profile ID",
        "profile_key": "Profile key",
        "load_profile": "Load profile",
        "save_profile": "Save profile",
        "brand_name": "Brand / tipster name",
        "tagline": "Tagline",
        "report_title": "Report title",
        "full_book_name": "Full magazine book file name",
        "logo_url": "Logo URL",
        "disclaimer": "Disclaimer",
        "mode": "Report mode",
        "risk": "Risk preference",
        "sports": "Sport / League Filter",
        "max_rows": "Max rows",
        "visibility": "Feed visibility",
        "cards": "Premium Cards",
        "magazine": "Magazine Report",
        "copy": "WhatsApp / Telegram",
        "audit": "Learning Audit",
        "proof": "Analyst Proof",
        "exports": "Exports",
        "images": "Images",
        "profile_json": "Profile JSON",
        "feed_json": "App Feed",
        "diagnostics": "Diagnostics",
        "pdf": "Download PDF",
        "magazine_pdf": "Download Magazine PDF",
        "magazine_png": "Download Magazine Report PNG",
        "html": "Download HTML",
        "md": "Download Markdown",
        "json": "Download JSON",
        "csv": "Download CSV",
        "copy_download": "Download WhatsApp copy",
        "images_note": "Magazine exports for the full report and one selected full page.",
        "image_tab_info": "Build the full book only when needed, or select one pick to render/download one page. Individual pages are not generated on page load.",
        "background_upload": "Optional background image for magazine exports",
        "background_ready": "Custom background enabled.",
        "background_preview": "Uploaded background preview",
        "generated_preview": "Generated magazine report preview",
        "feed_saved": "Unified and legacy app feeds saved.",
        "copy_label": "Short copy",
        "no_audit": "No graded calibration data available yet.",
        "build_book": "Build Full Magazine Book",
        "building_book": "Building full magazine book...",
        "download_book_png": "Download Full Magazine Book PNG",
        "download_book_pdf": "Download Full Magazine Book PDF",
        "download_zip": "Download Full Magazine ZIP",
        "download_page": "Download Full Magazine Page",
        "select_page": "Select one pick to render",
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
        "input": "Filas de entrada",
        "workspace": "ID de cliente / workspace",
        "use_saved": "Usar filas guardadas/actuales",
        "upload": "Subir CSV",
        "source": "Fuente",
        "empty": "No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.",
        "profile": "Perfil white-label",
        "profile_id": "ID del perfil",
        "profile_key": "Clave del perfil",
        "load_profile": "Cargar perfil",
        "save_profile": "Guardar perfil",
        "brand_name": "Marca / tipster",
        "tagline": "Lema",
        "report_title": "Titulo del reporte",
        "full_book_name": "Nombre de archivo del libro revista",
        "logo_url": "URL del logo",
        "disclaimer": "Aviso legal",
        "mode": "Modo de reporte",
        "risk": "Preferencia de riesgo",
        "sports": "Filtro deporte / liga",
        "max_rows": "Maximo de filas",
        "visibility": "Visibilidad del feed",
        "cards": "Tarjetas premium",
        "magazine": "Reporte revista",
        "copy": "WhatsApp / Telegram",
        "audit": "Auditoria de aprendizaje",
        "proof": "Prueba tecnica",
        "exports": "Exportaciones",
        "images": "Imagenes",
        "profile_json": "JSON del perfil",
        "feed_json": "Feed de app",
        "diagnostics": "Diagnostico",
        "pdf": "Descargar PDF",
        "magazine_pdf": "Descargar PDF revista",
        "magazine_png": "Descargar PNG reporte revista",
        "html": "Descargar HTML",
        "md": "Descargar Markdown",
        "json": "Descargar JSON",
        "csv": "Descargar CSV",
        "copy_download": "Descargar copy WhatsApp",
        "images_note": "Exportaciones de revista para el reporte completo y una pagina seleccionada.",
        "image_tab_info": "Crea el libro completo solo cuando sea necesario, o selecciona una jugada para renderizar una sola pagina.",
        "background_upload": "Imagen de fondo opcional para exportaciones de revista",
        "background_ready": "Fondo personalizado activo.",
        "background_preview": "Vista previa del fondo subido",
        "generated_preview": "Vista previa del reporte revista generado",
        "feed_saved": "Feed unificado y legado guardado.",
        "copy_label": "Copy corto",
        "no_audit": "Aun no hay datos gradados para calibracion.",
        "build_book": "Crear libro revista completo",
        "building_book": "Creando libro revista completo...",
        "download_book_png": "Descargar libro revista PNG",
        "download_book_pdf": "Descargar libro revista PDF",
        "download_zip": "Descargar ZIP revista",
        "download_page": "Descargar pagina revista",
        "select_page": "Seleccionar una jugada para renderizar",
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

AUDIT_ES = {
    "by_sport": "Por deporte",
    "by_league": "Por liga",
    "by_market_type": "Por tipo de mercado",
    "by_edge_bucket": "Por rango de ventaja",
    "by_model_probability_bucket": "Por rango de probabilidad del modelo",
    "by_report_lane": "Por carril de reporte",
    "negative_edge_winners": "Ganadoras con ventaja negativa",
}

REPORT_MODE_ES = {
    "Consumer Magazine": "Revista de consumidor",
    "Tipster Report": "Reporte tipster",
    "Client-Safe Summary": "Resumen seguro para cliente",
    "Analyst Proof Report": "Reporte de prueba para analista",
}
RISK_ES = {"Balanced": "Balanceado", "Conservative": "Conservador", "Aggressive": "Agresivo"}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def localized_options(values: list[str], custom: dict[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    if LANG != "es":
        return values, {value: value for value in values}
    custom = custom or {}
    labels = [custom.get(value, str(localize_value(value, LANG))) for value in values]
    return labels, dict(zip(labels, values))


def display_event_text(value: str, language: str) -> str:
    return event_text(value, language)


def display_action_text(value: str, language: str) -> str:
    return value_text(value, language)


def audit_name_text(name: str, language: str) -> str:
    return AUDIT_ES.get(name, name.replace("_", " ").title()) if language == "es" else name.replace("_", " ").title()


def localized_dataframe(frame: pd.DataFrame, language: str) -> pd.DataFrame:
    return global_localize_dataframe(frame, language)


def _rows_to_frame(rows) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame()


def load_current_session_rows() -> tuple[str, pd.DataFrame]:
    for key in HANDOFF_KEYS:
        frame = _rows_to_frame(st.session_state.get(key) or [])
        if not frame.empty:
            return f"session:{key}", frame
    return "", pd.DataFrame()


def load_saved_handoff_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    frame = _rows_to_frame(rows)
    return (f"saved:{key}", frame) if not frame.empty else ("", pd.DataFrame())


def load_persistent_ledger_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    return ("persistent_proof_ledger", persistent) if persistent is not None and not persistent.empty else ("", pd.DataFrame())


def source_mode(source: str) -> str:
    if source.startswith("uploaded:"):
        return "uploaded"
    if source.startswith("session:"):
        return "current-run"
    if source.startswith("saved:"):
        return "saved-handoff"
    if source == "persistent_proof_ledger":
        return "ledger-history"
    return "none"


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    for loader in (load_current_session_rows, lambda: load_saved_handoff_rows(workspace_id), lambda: load_persistent_ledger_rows(workspace_id)):
        source, frame = loader()
        if not frame.empty:
            return source, frame
    return "", pd.DataFrame()


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
    source_name = "uploaded:" + ",".join(names)
    return source_name, pd.concat(frames, ignore_index=True, sort=False)


def choose_report_studio_source(saved_source: str, saved_rows: pd.DataFrame, upload_source: str, upload_rows: pd.DataFrame) -> tuple[str, pd.DataFrame, str]:
    if upload_rows is not None and not upload_rows.empty:
        return upload_source, upload_rows, source_mode(upload_source)
    if saved_rows is not None and not saved_rows.empty:
        return saved_source, saved_rows, source_mode(saved_source)
    return "", pd.DataFrame(), "none"


def sport_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "sport" not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame["sport"].tolist() if safe_text(value)})


def safe_workspace_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value or "report"))


def no_market_filename(filename: str) -> str:
    base = str(filename or "magazine").rsplit(".", 1)[0]
    return magazine_book_export.sanitize_image_filename(f"{base}_{NO_MARKET_EXPORT_VERSION}", extension="png")


def with_report_language(rowd: dict, language: str) -> dict:
    data = dict(rowd or {})
    data["report_language"] = language
    return data


def with_report_branding(rowd: dict, brand_name: str, report_title: str, language: str) -> dict:
    data = with_report_language(rowd, language)
    data["report_brand_name"] = brand_name
    data["report_title"] = report_title
    return data


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
    workspace = safe_workspace_name(safe_text(payload.get("workspace_id")) or "default")
    package_type = safe_text(payload.get("package_type")) or "public"
    return f"aba_report_publisher_{workspace}_{package_type}_{_hash_fragment(payload.get('package_hash'))}.{suffix}"


def _publisher_redaction_passed(payload: dict) -> bool:
    package = payload.get("public_package") or {}
    status = package.get("redaction_status") or {}
    return bool(status.get("passed", False))


def _render_publisher_downloads(payload: dict, stale: bool) -> None:
    package_hash = safe_text(payload.get("package_hash")) or "nohash"
    redaction_ok = _publisher_redaction_passed(payload)
    if stale:
        st.error(t("stale_publisher"))
    if not redaction_ok:
        st.error(t("redaction_failed"))
    disabled = stale or not redaction_ok
    export_files = payload.get("export_files") or {}
    json_file = export_files.get("json") or {}
    markdown_file = export_files.get("markdown") or {}
    csv_bundle = export_files.get("csv_bundle") or {}
    c1, c2 = st.columns(2)
    c1.download_button(t("download_report_json"), safe_text(json_file.get("content")).encode("utf-8"), file_name=_publisher_filename(payload, "json"), mime="application/json", disabled=disabled, key=f"report_studio_publisher_json_{package_hash}")
    c2.download_button(t("download_report_markdown"), safe_text(markdown_file.get("content")).encode("utf-8"), file_name=_publisher_filename(payload, "md"), mime="text/markdown", disabled=disabled, key=f"report_studio_publisher_markdown_{package_hash}")
    for filename, csv_text in csv_bundle.items():
        st.download_button(f"{t('download_report_csv')}: {filename}", safe_text(csv_text).encode("utf-8"), file_name=f"{_publisher_filename(payload, 'csv').rsplit('.', 1)[0]}_{filename}", mime="text/csv", disabled=disabled, key=f"report_studio_publisher_csv_{package_hash}_{filename}")


def api_enrichment_diagnostics(rows: list[dict], source: str = "", source_mode_value: str = "") -> dict:
    first = dict(rows[0]) if rows else {}
    provenance = api_provenance(first) if first else {"active_sources": [], "available_no_data_sources": [], "inactive_sources": []}
    return {
        "source": source,
        "source_mode": source_mode_value,
        "magazine_style_version": magazine_book_export.MAGAZINE_STYLE_VERSION,
        "no_market_export_version": NO_MARKET_EXPORT_VERSION,
        "api_enrichment_version": ENRICHMENT_VERSION,
        "first_row_active_apis": provenance.get("active_sources", []),
        "first_row_no_live_data_apis": provenance.get("available_no_data_sources", []),
        "first_row_inactive_apis": provenance.get("inactive_sources", []),
        "first_row_api_enrichment_fields": first.get("api_enrichment_fields", ""),
        "first_row_has_weather_summary": bool(safe_text(first.get("weather_summary"))),
        "first_row_has_newsapi_summary": bool(safe_text(first.get("newsapi_summary"))),
        "first_row_has_api_football_summary": bool(safe_text(first.get("api_football_summary"))),
        "first_row_has_sportsdataio_context": bool(safe_text(first.get("sportsdataio_context"))),
        "first_row_weather_summary": safe_text(first.get("weather_summary")),
        "first_row_newsapi_summary": safe_text(first.get("newsapi_summary")),
        "first_row_api_football_summary": safe_text(first.get("api_football_summary")),
        "first_row_sportsdataio_context": safe_text(first.get("sportsdataio_context")),
    }


@st.cache_data(show_spinner=False)
def cached_render_full_pick_magazine_page_png(row_items: tuple[tuple[str, str], ...], background_bytes: bytes | None, report_name: str, page_number: int, total_pages: int, language: str, style_version: str, no_market_version: str, enrichment_version: str) -> bytes:
    rowd = with_report_language(dict(row_items), language)
    rowd["_magazine_style_version"] = f"{style_version}:{no_market_version}:{enrichment_version}"
    rowd = enrich_rows_with_live_api_data([rowd])[0]
    return magazine_book_export.render_full_pick_magazine_page_png(rowd, background_image=background_bytes, report_name=report_name, page_number=page_number, total_pages=total_pages, language=language)


def serializable_row(rowd: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), "" if value is None else str(value)) for key, value in rowd.items()))


st.title(t("title"))
st.caption(t("caption"))
profile_background_bytes = st.session_state.get("report_studio_profile_background_bytes")

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    use_saved = st.checkbox(t("use_saved"), value=True)
    upload_source, upload_rows = read_uploaded_rows()
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ("", pd.DataFrame())
    source_note, raw, source_mode_value = choose_report_studio_source(saved_source, saved_rows, upload_source, upload_rows)
    st.caption(f"{t('source')}: {localize_value(source_note or 'none', LANG)} · Source mode: {source_mode_value} · Rows: {len(raw)}")
    if source_note == "persistent_proof_ledger":
        st.warning("Magazine is using saved proof history because no current prediction rows were found. Run Pro Predictor/Odds Lock Pro or upload the newest CSV before exporting.")

if raw.empty:
    st.warning(t("empty"))
    st.stop()

normalized_preview = normalize_frame(raw)
all_sport_options = sport_options(normalized_preview)

with st.expander(t("profile"), expanded=True):
    profile_rows = list_profiles()
    profile_ids = sorted({safe_text(row.get("profile_id")) for row in profile_rows if safe_text(row.get("profile_id"))}) or ["default"]
    p1, p2, p3 = st.columns([2, 1, 1])
    profile_labels, profile_map = localized_options(profile_ids)
    selected_profile_label = p1.selectbox(t("profile_id"), profile_labels, index=0)
    selected_profile = profile_map.get(selected_profile_label, selected_profile_label)
    profile_id = p1.text_input(t("profile_key"), value=selected_profile)
    if p2.button(t("load_profile"), use_container_width=True):
        profile = load_profile(profile_id)
        st.session_state["report_studio_profile"] = asdict(profile)
        st.rerun()
    loaded = WhiteLabelProfile(**st.session_state.get("report_studio_profile", {})).normalized() if st.session_state.get("report_studio_profile") else load_profile(profile_id)
    b1, b2 = st.columns(2)
    brand_name = b1.text_input(t("brand_name"), value=loaded.brand_name)
    tagline = b2.text_input(t("tagline"), value=value_text(loaded.tagline, LANG))
    report_title = b1.text_input(t("report_title"), value=value_text(loaded.report_title, LANG))
    default_book_name = safe_text(brand_name) or "ABA Signal Pro"
    full_magazine_book_name = st.text_input(t("full_book_name"), default_book_name, key="report_studio_full_magazine_book_filename")
    logo_url = b2.text_input(t("logo_url"), value=loaded.logo_url)
    background_profile_upload = st.file_uploader(t("background_upload"), type=["png", "jpg", "jpeg"], key="report_studio_profile_background_upload")
    if background_profile_upload is not None:
        profile_background_bytes = background_profile_upload.getvalue()
        st.session_state["report_studio_profile_background_bytes"] = profile_background_bytes
    if profile_background_bytes:
        st.success(t("background_ready"))
        st.image(profile_background_bytes, caption=t("background_preview"), width=260)
    report_mode_values = ["Consumer Magazine", "Tipster Report", "Client-Safe Summary", "Analyst Proof Report"]
    mode_labels, mode_map = localized_options(report_mode_values, REPORT_MODE_ES)
    loaded_mode = loaded.preferred_report_mode if loaded.preferred_report_mode in report_mode_values else report_mode_values[0]
    default_mode_index = report_mode_values.index(loaded_mode)
    report_mode_label = b1.selectbox(t("mode"), mode_labels, index=default_mode_index)
    report_mode = mode_map.get(report_mode_label, report_mode_label)
    risk_values = ["Balanced", "Conservative", "Aggressive"]
    risk_labels, risk_map = localized_options(risk_values, RISK_ES)
    loaded_risk = loaded.risk_preference if loaded.risk_preference in risk_values else risk_values[0]
    risk_index = risk_values.index(loaded_risk)
    risk_label = b2.selectbox(t("risk"), risk_labels, index=risk_index)
    risk_preference = risk_map.get(risk_label, risk_label)
    visibility_values = ["private", "public"]
    visibility_labels, visibility_map = localize_options(visibility_values, LANG)
    loaded_visibility = safe_text((loaded.delivery_settings or {}).get("visibility")) or "private"
    visibility_index = visibility_values.index(loaded_visibility) if loaded_visibility in visibility_values else 0
    visibility_label = b2.selectbox(t("visibility"), visibility_labels, index=visibility_index)
    visibility = visibility_map.get(visibility_label, visibility_label)
    preferred_sports = render_sport_league_filter(st, label=t("sports"), options=all_sport_options, default=[sport for sport in list(loaded.preferred_sports or []) if sport in all_sport_options], language=LANG, key="report_profile_sports")
    disclaimer_default = "Informational content only. Results are not guaranteed." if LANG == "en" else "Contenido informativo. No garantiza resultados."
    disclaimer = st.text_area(t("disclaimer"), value=loaded.disclaimer or disclaimer_default, height=80)
    technical = report_mode == "Analyst Proof Report"
    if p3.button(t("save_profile"), use_container_width=True):
        saved = save_profile(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace_id, brand_name=brand_name, logo_url=logo_url, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_report_mode=report_mode, preferred_sports=list(preferred_sports), risk_preference=risk_preference, show_technical_fields=technical, default_audience="analyst" if technical else "consumer", delivery_settings={"save_latest_feed": True, "visibility": visibility}))
        st.session_state["report_studio_profile"] = asdict(saved)
        st.success(t("save_profile"))

max_rows = st.number_input(t("max_rows"), min_value=1, max_value=500, value=75, step=1)
mode_key = "analyst" if technical else "consumer"
brand = MagazineBrand(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace_id, language=LANG, logo_url=logo_url, disclaimer=disclaimer)
filters = ReportStudioFilters(selected_sports=tuple(preferred_sports), max_rows=int(max_rows), language=LANG, mode=mode_key, public_feed=visibility == "public")
state = build_report_studio_state(raw, brand, filters=filters, source_note=f"{source_note} ({source_mode_value})")
cards = state.cards
bundle = state.exports
legacy_feed = save_app_feed(cards, brand, mode=mode_key, public=visibility == "public")
unified_feed = save_report_feed(cards, brand, mode=mode_key, public=visibility == "public")
feed = {"unified_v2": unified_feed, "legacy_v1": legacy_feed}
summary = report_studio_summary(state)
magazine_report_name = safe_text(brand_name) or "ABA Signal Pro"
magazine_title = safe_text(report_title) or ("Analisis Deportivo Diario" if LANG == "es" else "Daily Sports Analysis")
cards_as_rows = enrich_rows_with_live_api_data([with_report_branding(row.to_dict(), magazine_report_name, magazine_title, LANG) for _, row in cards.iterrows()])
api_diagnostics = api_enrichment_diagnostics(cards_as_rows, source_note, source_mode_value)

st.markdown(render_status_dashboard(cards, language=LANG), unsafe_allow_html=True)
st.caption(state.context_note)
safe_workspace = safe_workspace_name(workspace_id)
report_background_bytes = profile_background_bytes
magazine_pdf_bytes = magazine_book_export.render_full_magazine_book_pdf(cards_as_rows, background_image=report_background_bytes, report_name=magazine_report_name, language=LANG)
magazine_tab_png = magazine_book_export.render_full_pick_magazine_page_png(cards_as_rows[0], background_image=report_background_bytes, report_name=magazine_report_name, page_number=1, total_pages=len(cards_as_rows), language=LANG) if cards_as_rows else b""
tabs = st.tabs([t("cards"), t("magazine"), t("copy"), t("audit"), t("proof"), t("exports"), t("images"), t("profile_json"), t("feed_json"), t("diagnostics"), t("publisher")])

with tabs[0]:
    st.markdown(render_premium_card_deck(cards, language=LANG), unsafe_allow_html=True)
with tabs[1]:
    m1, m2 = st.columns(2)
    m1.download_button(t("magazine_pdf"), data=magazine_pdf_bytes, file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}", extension="pdf"), mime="application/pdf", key="report_studio_magazine_pdf")
    m2.download_button(t("magazine_png"), data=magazine_tab_png, file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}_preview", extension="png"), mime="image/png", key="report_studio_magazine_tab_png")
    if magazine_tab_png:
        st.image(magazine_tab_png, caption=t("generated_preview"), use_container_width=True)
with tabs[2]:
    st.text_area(t("copy_label"), value=bundle.whatsapp, height=420, key="report_studio_whatsapp_copy_text")
    st.download_button(t("copy_download"), data=bundle.whatsapp, file_name=f"whatsapp_copy_{safe_workspace}.txt", mime="text/plain", key="report_studio_copy_tab_download")
with tabs[3]:
    if not state.audit:
        st.info(t("no_audit"))
    for name, table in state.audit.items():
        st.subheader(audit_name_text(name, LANG))
        st.dataframe(localized_dataframe(table, LANG), use_container_width=True, hide_index=True)
with tabs[4]:
    proof_cols = ["event", "sport", "prediction", "decimal_price", "model_probability", "market_probability", "model_market_edge", "expected_value_per_unit", "model_lean_label", "price_value_label", "official_status_label", "result_status", "learning_status", "official_publish_ready", "client_report_ready", "learning_ready", "data_issue_reason", "odds_verified", "report_lane", "report_lane_v2", "publish_ready", "tennis_blocked", "proof_id", "locked_at_utc", "odds_source", "bookmaker", "model_probability_source", "sports_context_summary", "profit_units"]
    cols = [col for col in proof_cols if col in cards.columns]
    st.dataframe(localized_dataframe(cards[cols] if cols else cards, LANG), use_container_width=True, hide_index=True)
with tabs[5]:
    st.download_button(t("pdf"), data=bundle.pdf_bytes, file_name=f"report_{safe_workspace}.pdf", mime="application/pdf", key="report_studio_export_pdf")
    st.download_button(t("magazine_pdf"), data=magazine_pdf_bytes, file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}", extension="pdf"), mime="application/pdf", key="report_studio_export_magazine_pdf")
    st.download_button(t("html"), data=bundle.html, file_name=f"report_{safe_workspace}.html", mime="text/html", key="report_studio_export_html")
    st.download_button(t("md"), data=bundle.markdown, file_name=f"report_{safe_workspace}.md", mime="text/markdown", key="report_studio_export_md")
    st.download_button(t("copy_download"), data=bundle.whatsapp, file_name=f"whatsapp_copy_{safe_workspace}.txt", mime="text/plain", key="report_studio_export_whatsapp")
    st.download_button(t("json"), data=bundle.json_text, file_name=f"report_{safe_workspace}.json", mime="application/json", key="report_studio_export_json")
    st.download_button(t("csv"), data=bundle.csv_text, file_name=f"report_{safe_workspace}.csv", mime="text/csv", key="report_studio_export_csv")
with tabs[6]:
    st.caption(t("images_note"))
    st.info(t("image_tab_info"))
    background_upload = st.file_uploader(t("background_upload"), type=["png", "jpg", "jpeg"], key="report_studio_image_background_upload")
    if background_upload is not None:
        st.session_state["report_studio_image_background_bytes"] = background_upload.getvalue()
    background_bytes = st.session_state.get("report_studio_image_background_bytes") or report_background_bytes
    if background_bytes:
        st.success(t("background_ready"))
        st.image(background_bytes, caption=t("background_preview"), width=260)
    brand_cache = safe_workspace_name(magazine_report_name)
    book_cache_key = f"report_studio_full_book_export_cache_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}"
    if st.button(t("build_book"), key=f"report_studio_prepare_full_book_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}"):
        with st.spinner(t("building_book")):
            st.session_state[book_cache_key] = {
                "png": magazine_book_export.render_full_magazine_book_png(cards_as_rows, background_image=background_bytes, report_name=magazine_report_name, language=LANG),
                "pdf": magazine_book_export.render_full_magazine_book_pdf(cards_as_rows, background_image=background_bytes, report_name=magazine_report_name, language=LANG),
                "zip": magazine_book_export.render_full_magazine_zip(cards_as_rows, background_image=background_bytes, report_name=magazine_report_name, language=LANG),
            }
    full_book_cache = st.session_state.get(book_cache_key)
    if full_book_cache:
        book1, book2, book3 = st.columns(3)
        book1.download_button(t("download_book_png"), data=full_book_cache["png"], file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}", extension="png"), mime="image/png", key=f"report_studio_full_book_png_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}")
        book2.download_button(t("download_book_pdf"), data=full_book_cache["pdf"], file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}", extension="pdf"), mime="application/pdf", key=f"report_studio_full_book_pdf_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}")
        book3.download_button(t("download_zip"), data=full_book_cache["zip"], file_name=magazine_book_export.sanitize_image_filename(f"{full_magazine_book_name}_{LANG}_{NO_MARKET_EXPORT_VERSION}", extension="zip"), mime="application/zip", key=f"report_studio_full_book_zip_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}")
    st.markdown("---")
    if cards_as_rows:
        pick_options: list[str] = []
        for idx, rowd in enumerate(cards_as_rows):
            event = display_event_text(safe_text(rowd.get("public_event") or rowd.get("event")) or f"Game {idx + 1}", LANG)
            action = display_action_text(safe_text(rowd.get("consumer_action") or rowd.get("recommended_action")) or "Full magazine analysis", LANG)
            pick_options.append(f"{idx + 1}. {event} - {action}")
        selected_idx = st.selectbox(t("select_page"), range(len(pick_options)), format_func=lambda i: pick_options[i], key=f"report_studio_selected_full_page_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}")
        selected_row = cards_as_rows[int(selected_idx)]
        selected_png = cached_render_full_pick_magazine_page_png(serializable_row(selected_row), background_bytes, magazine_report_name, int(selected_idx) + 1, len(cards_as_rows), LANG, magazine_book_export.MAGAZINE_STYLE_VERSION, NO_MARKET_EXPORT_VERSION, ENRICHMENT_VERSION)
        st.download_button(t("download_page"), data=selected_png, file_name=no_market_filename(magazine_book_export.pick_full_page_filename(selected_row, int(selected_idx))), mime="image/png", key=f"report_studio_image_full_page_selected_{LANG}_{brand_cache}_{magazine_book_export.MAGAZINE_STYLE_VERSION}_{NO_MARKET_EXPORT_VERSION}_{ENRICHMENT_VERSION}")
with tabs[7]:
    st.json(asdict(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace_id, brand_name=brand_name, logo_url=logo_url, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_report_mode=report_mode, preferred_sports=preferred_sports, risk_preference=risk_preference, show_technical_fields=technical, default_audience="analyst" if technical else "consumer")))
with tabs[8]:
    st.success(t("feed_saved"))
    st.json(feed)
with tabs[9]:
    st.json({"summary": summary, "diagnostics": asdict(state.diagnostics), "api_enrichment": api_diagnostics, "filters": asdict(state.filters), "source": source_note, "source_mode": source_mode_value, "unified_feed_paths": unified_feed.get("saved_paths", {}), "legacy_feed_paths": legacy_feed.get("saved_paths", {})})
with tabs[10]:
    st.subheader(t("publisher"))
    st.caption(t("publisher_caption"))
    publisher_workspace = normalize_workspace_id(st.text_input(t("publisher_workspace_id"), value=workspace_id, key="report_studio_publisher_workspace_id"))
    publisher_type = st.selectbox(t("package_type"), REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS, index=0, key="report_studio_publisher_package_type")
    if st.button(t("build_publisher_payload"), key="report_studio_build_report_publisher_payload"):
        payload = build_report_publisher_payload(publisher_workspace, package_type=publisher_type)
        fingerprint = report_publisher_input_fingerprint(publisher_workspace, publisher_type, safe_text(payload.get("report_id")), safe_text(payload.get("package_hash")))
        st.session_state[REPORT_STUDIO_PUBLISHER_PREVIEW_KEY] = payload
        st.session_state[REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY] = fingerprint
        st.session_state[REPORT_STUDIO_PUBLISHER_META_KEY] = {
            "report_id": payload.get("report_id"),
            "package_hash": payload.get("package_hash"),
            "workspace_id": publisher_workspace,
            "package_type": publisher_type,
            "publisher_input_fingerprint": fingerprint,
        }
        st.info(t("publisher_preview_ready"))
    payload = st.session_state.get(REPORT_STUDIO_PUBLISHER_PREVIEW_KEY, {})
    if payload:
        stale = not _publisher_matches_current(payload, publisher_workspace, publisher_type)
        if stale:
            st.error(t("stale_publisher"))
        if not _publisher_redaction_passed(payload):
            st.error(t("redaction_failed"))
        st.write({
            "report_id": payload.get("report_id"),
            "package_id": payload.get("package_id"),
            "package_hash": payload.get("package_hash"),
            "proof_ready": payload.get("proof_ready"),
            "proof_grade": payload.get("proof_grade"),
            "ledger_backed": payload.get("ledger_backed"),
        })
        st.markdown(f"**{t('headline_summary')}**")
        st.write(payload.get("headline_summary"))
        st.markdown(f"**{t('performance_summary')}**")
        st.json(payload.get("performance_summary") or {})
        st.markdown(f"**{t('roi_summary')}**")
        st.json(payload.get("roi_summary") or {})
        st.markdown(f"**{t('clv_summary')}**")
        st.json(payload.get("clv_summary") or {})
        st.markdown(f"**{t('risk_summary')}**")
        st.json(payload.get("risk_summary") or {})
        st.markdown(f"**{t('top_positive_ev_summary')}**")
        st.json(payload.get("top_positive_ev_summary") or {})
        st.markdown(f"**{t('proof_disclaimer')}**")
        st.write(payload.get("proof_disclaimer"))
        st.markdown(f"**{t('verification_manifest')}**")
        st.json(payload.get("verification_manifest") or {})
        _render_publisher_downloads(payload, stale)
    else:
        st.info(t("empty"))
