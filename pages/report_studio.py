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
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe as global_localize_dataframe, localize_value

magazine_book_export = apply_magazine_sale_ready_patch(
    install_magazine_live_api_enrichment(importlib.reload(magazine_book_export))
)
install_magazine_report_polish()

st.set_page_config(page_title="Report Studio", layout="wide")
LANG = render_app_sidebar("report_studio", language_key="report_studio_language", selector="radio")
NO_MARKET_EXPORT_VERSION = "no_market_metric_v10"
DISPLAY_POLISH_VERSION = "display_polish_v1"
ACTIVE_EXPORT_VERSION = f"{magazine_book_export.MAGAZINE_STYLE_VERSION}:{NO_MARKET_EXPORT_VERSION}:{ENRICHMENT_VERSION}:{DISPLAY_POLISH_VERSION}"

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
        "build_book": "Build Full Magazine Book",
        "building_book": "Building full magazine book...",
        "download_book_png": "Download Full Magazine Book PNG",
        "download_book_pdf": "Download Full Magazine Book PDF",
        "download_page_png": "Download Magazine Report PNG",
        "download_page_pdf": "Download Magazine PDF",
        "select_page": "Select one pick to render",
        "generated_preview": "Generated magazine report preview",
        "source": "Source",
        "download_csv": "Download CSV",
        "download_json": "Download JSON",
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
        "build_book": "Crear libro revista completo",
        "building_book": "Creando libro revista completo...",
        "download_book_png": "Descargar libro revista PNG",
        "download_book_pdf": "Descargar libro revista PDF",
        "download_page_png": "Descargar PNG reporte revista",
        "download_page_pdf": "Descargar PDF revista",
        "select_page": "Seleccionar una jugada para renderizar",
        "generated_preview": "Vista previa del reporte revista generado",
        "source": "Fuente",
        "download_csv": "Descargar CSV",
        "download_json": "Descargar JSON",
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


@st.cache_data(show_spinner=False)
def enrich_cached(rows: list[dict[str, Any]], language: str, version: str) -> list[dict[str, Any]]:
    prepared = [with_report_language(row, language) for row in rows]
    return enrich_rows_with_live_api_data(prepared)


def render_page_png(row: dict[str, Any], page_number: int = 1, total_pages: int = 1) -> bytes:
    return magazine_book_export.render_full_pick_magazine_page_png(
        row,
        report_name="ABA Signal Pro",
        page_number=page_number,
        total_pages=total_pages,
        language=LANG,
    )


def render_book_png(rows: list[dict[str, Any]]) -> bytes:
    return magazine_book_export.render_full_magazine_book_png(rows, report_name="ABA Signal Pro", language=LANG)


def render_book_pdf(rows: list[dict[str, Any]]) -> bytes:
    return magazine_book_export.render_full_magazine_book_pdf(rows, report_name="ABA Signal Pro", language=LANG)


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

    if "sport" in frame.columns:
        sports = sorted({safe_text(value) for value in frame["sport"].tolist() if safe_text(value)})
        if sports:
            chosen = st.multiselect(t("sports"), sports, default=sports)
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
            st.download_button(t("download_book_png"), data=book_png, file_name=safe_filename(f"full_magazine_book_{fingerprint(enriched_rows, LANG)}", "png"), mime="image/png")
            st.download_button(t("download_book_pdf"), data=book_pdf, file_name=safe_filename(f"full_magazine_book_{fingerprint(enriched_rows, LANG)}", "pdf"), mime="application/pdf")

    with data_tab:
        st.dataframe(localized_dataframe(pd.DataFrame(enriched_rows), LANG), use_container_width=True)

    with exports_tab:
        out_frame = pd.DataFrame(enriched_rows)
        st.download_button(t("download_csv"), data=out_frame.to_csv(index=False).encode("utf-8"), file_name=safe_filename(f"report_rows_{fingerprint(enriched_rows, LANG)}", "csv"), mime="text/csv")
        st.download_button(t("download_json"), data=json.dumps(enriched_rows, ensure_ascii=False, indent=2).encode("utf-8"), file_name=safe_filename(f"report_rows_{fingerprint(enriched_rows, LANG)}", "json"), mime="application/json")


main()
