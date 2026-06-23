from __future__ import annotations

import base64
import html

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_product_layer import (
    MagazineBrand,
    cards_to_json,
    enrich_rows,
    grouped_report,
    render_consumer_magazine_html,
    render_markdown_summary,
)
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Consumer Magazine Builder", layout="wide")
LANG = render_app_sidebar("consumer_magazine_builder", language_key="consumer_magazine_builder_language", selector="radio")

TEXT = {
    "en": {
        "title": "Consumer Magazine Builder",
        "caption": "High-level consumer, tipster, client-safe, and analyst-proof reports from the same ABA rows.",
        "input": "Input rows",
        "workspace": "Client / Workspace ID",
        "use_saved": "Use saved workspace rows",
        "upload": "Upload CSV rows",
        "source": "Source",
        "empty": "No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.",
        "brand": "Brand and delivery profile",
        "brand_name": "Brand / tipster name",
        "tagline": "Tagline",
        "report_title": "Report title",
        "logo_url": "Logo URL",
        "disclaimer": "Disclaimer",
        "mode": "Report mode",
        "risk": "Risk preference",
        "sports": "Sports",
        "max_rows": "Max rows",
        "best": "Best Plays",
        "watch": "Watchlist",
        "no_play": "No Play",
        "avg": "Avg model probability",
        "publish": "Publish-ready",
        "warnings": "Warnings",
        "html": "Magazine HTML",
        "markdown": "Markdown / WhatsApp summary",
        "json": "JSON app feed",
        "csv": "CSV export",
        "proof": "Analyst proof table",
    },
    "es": {
        "title": "Constructor de Revista para Consumidor",
        "caption": "Reportes de consumidor, tipster, cliente y prueba técnica desde las mismas filas ABA.",
        "input": "Filas de entrada",
        "workspace": "ID de cliente / workspace",
        "use_saved": "Usar filas guardadas",
        "upload": "Subir CSV",
        "source": "Fuente",
        "empty": "No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.",
        "brand": "Marca y perfil de entrega",
        "brand_name": "Marca / tipster",
        "tagline": "Lema",
        "report_title": "Título del reporte",
        "logo_url": "URL del logo",
        "disclaimer": "Aviso legal",
        "mode": "Modo de reporte",
        "risk": "Preferencia de riesgo",
        "sports": "Deportes",
        "max_rows": "Máximo de filas",
        "best": "Mejores jugadas",
        "watch": "Seguimiento",
        "no_play": "No jugar",
        "avg": "Probabilidad media del modelo",
        "publish": "Listas para publicar",
        "warnings": "Alertas",
        "html": "HTML de revista",
        "markdown": "Resumen Markdown / WhatsApp",
        "json": "Feed JSON para app",
        "csv": "Exportar CSV",
        "proof": "Tabla técnica de prueba",
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


def download_link(label: str, payload: str | bytes, filename: str, mime: str) -> None:
    data = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    encoded = base64.b64encode(data).decode("ascii")
    st.markdown(
        f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:{html.escape(mime)};base64,{encoded}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


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


def avg_model_probability(cards: pd.DataFrame) -> str:
    if cards.empty or "model_probability" not in cards.columns:
        return "N/A"
    values = pd.to_numeric(cards["model_probability"], errors="coerce").dropna()
    return "N/A" if values.empty else f"{float(values.mean()) * 100:.1f}%"


def sport_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "sport" not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame["sport"].tolist() if safe_text(value)})


st.title(t("title"))
st.caption(t("caption"))

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    use_saved = st.checkbox(t("use_saved"), value=True)
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ("", pd.DataFrame())
    upload_source, upload_rows = read_uploaded_rows()
    sources = ", ".join([name for name in (saved_source, upload_source) if name]) or "none"
    raw = pd.concat([frame for frame in (saved_rows, upload_rows) if frame is not None and not frame.empty], ignore_index=True, sort=False) if (not saved_rows.empty or not upload_rows.empty) else pd.DataFrame()
    st.caption(f"{t('source')}: {sources}")

if raw.empty:
    st.warning(t("empty"))
    st.stop()

normalized = normalize_frame(raw)

with st.expander(t("brand"), expanded=True):
    b1, b2 = st.columns(2)
    default_title = "Daily Sports Analysis" if LANG == "en" else "Reporte Diario de Análisis Deportivo"
    brand_name = b1.text_input(t("brand_name"), value=st.session_state.get("consumer_mag_brand_name", "ABA Signal Pro"))
    tagline = b2.text_input(t("tagline"), value=st.session_state.get("consumer_mag_tagline", "Powered by Reparodynamics"))
    report_title = b1.text_input(t("report_title"), value=st.session_state.get("consumer_mag_title", default_title))
    logo_url = b2.text_input(t("logo_url"), value=st.session_state.get("consumer_mag_logo_url", ""))
    mode_options = ["Consumer Magazine", "Tipster Report", "Analyst Proof Report", "Client-Safe Summary"] if LANG == "en" else ["Revista consumidor", "Reporte tipster", "Reporte técnico", "Resumen cliente"]
    report_mode = b1.selectbox(t("mode"), mode_options, index=0)
    b2.selectbox(t("risk"), ["Balanced", "Conservative", "Aggressive"] if LANG == "en" else ["Balanceado", "Conservador", "Agresivo"], index=0)
    disclaimer_default = "Informational content only. Results are not guaranteed." if LANG == "en" else "Contenido informativo. No garantiza resultados."
    disclaimer = st.text_area(t("disclaimer"), value=st.session_state.get("consumer_mag_disclaimer", disclaimer_default), height=80)

for key, value in {
    "consumer_mag_brand_name": brand_name,
    "consumer_mag_tagline": tagline,
    "consumer_mag_title": report_title,
    "consumer_mag_logo_url": logo_url,
    "consumer_mag_disclaimer": disclaimer,
}.items():
    st.session_state[key] = value

f1, f2 = st.columns(2)
sports = f1.multiselect(t("sports"), sport_options(normalized))
max_rows = f2.number_input(t("max_rows"), min_value=1, max_value=250, value=50, step=1)

filtered = normalized.copy()
if sports and "sport" in filtered.columns:
    filtered = filtered[filtered["sport"].map(safe_text).isin(sports)].copy()
filtered = filtered.head(int(max_rows)).copy()

brand = MagazineBrand(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace_id, language=LANG, logo_url=logo_url, disclaimer=disclaimer)
cards = enrich_rows(filtered, language=LANG)
groups = grouped_report(cards)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric(t("best"), len(groups["best_plays"]))
m2.metric(t("watch"), len(groups["watchlist"]))
m3.metric(t("no_play"), len(groups["no_play"]))
m4.metric(t("avg"), avg_model_probability(cards))
m5.metric(t("publish"), int(cards.get("publish_ready", pd.Series(dtype=bool)).astype(bool).sum()) if not cards.empty else 0)
m6.metric(t("warnings"), int((~cards.get("publish_ready", pd.Series(dtype=bool)).astype(bool)).sum()) if not cards.empty else 0)

technical = "Analyst" in report_mode or "técnico" in report_mode.lower()
html_report = render_consumer_magazine_html(cards, brand, mode="analyst" if technical else "consumer")
markdown_report = render_markdown_summary(cards, brand)
json_feed = cards_to_json(cards)
csv_payload = cards.to_csv(index=False)
safe_workspace = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in workspace_id)

tabs = st.tabs([t("html"), t("markdown"), t("proof"), t("json"), t("csv")])
with tabs[0]:
    st.markdown(html_report, unsafe_allow_html=True)
    download_link("Download HTML" if LANG == "en" else "Descargar HTML", html_report, f"consumer_magazine_{safe_workspace}.html", "text/html")
with tabs[1]:
    st.text_area(t("markdown"), value=markdown_report, height=380)
    download_link("Download Markdown" if LANG == "en" else "Descargar Markdown", markdown_report, f"consumer_magazine_{safe_workspace}.md", "text/markdown")
with tabs[2]:
    proof_cols = ["event", "sport", "prediction", "decimal_price", "model_probability", "market_probability", "model_market_edge", "expected_value_per_unit", "odds_verified", "report_lane", "publish_ready", "proof_id", "locked_at_utc", "odds_source", "bookmaker", "model_probability_source"]
    cols = [col for col in proof_cols if col in cards.columns]
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
with tabs[3]:
    st.text_area(t("json"), value=json_feed, height=360)
    download_link("Download JSON" if LANG == "en" else "Descargar JSON", json_feed, f"consumer_magazine_{safe_workspace}.json", "application/json")
with tabs[4]:
    st.dataframe(cards, use_container_width=True, hide_index=True)
    download_link(t("csv"), csv_payload, f"consumer_magazine_{safe_workspace}.csv", "text/csv")
