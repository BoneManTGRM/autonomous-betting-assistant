from __future__ import annotations

import base64
import html
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.consumer_report_engine import (
    BrandSettings,
    brand_payload,
    cards_to_app_feed,
    cards_to_json,
    consumer_cards,
    prepare_report_frame,
    render_magazine_html,
    render_magazine_markdown,
    render_short_copy,
    report_quality_summary,
)
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.row_normalizer import normalize_frame, result_status, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Consumer Report Studio', layout='wide')
LANG = render_app_sidebar('consumer_report_studio', language_key='consumer_report_studio_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Consumer Report Studio', 'caption': 'Turn ABA rows into consumer cards, reports, feeds, and copy.',
        'workspace': 'Client / Workspace ID', 'workspace_help': 'Use a separate ID per client, tipster, app, or report brand.',
        'input': 'Input rows', 'use_saved': 'Use saved workspace rows', 'upload': 'Upload CSV rows', 'source': 'Source',
        'no_rows': 'No rows found. Use Odds Lock Pro first or upload a CSV.', 'brand': 'White-label brand',
        'brand_name': 'Brand / tipster name', 'tagline': 'Tagline', 'report_title': 'Report title', 'logo_url': 'Logo URL',
        'disclaimer': 'Disclaimer', 'filters': 'Report filters', 'max_rows': 'Max picks/cards',
        'min_probability': 'Minimum model probability', 'official_only': 'Official/proof-ready only', 'pending_only': 'Pending/upcoming only',
        'sport_filter': 'Sports', 'market_filter': 'Markets', 'cards_tab': 'High-level cards', 'magazine_tab': 'Magazine report',
        'copy_tab': 'WhatsApp / Telegram copy', 'feed_tab': 'CSV / JSON feed', 'settings_tab': 'Brand settings', 'diagnostics_tab': 'Diagnostics',
        'cards': 'Cards', 'avg_prob': 'Avg probability', 'proof_rows': 'Proof rows', 'publish_ready': 'Publish-ready', 'warnings': 'Warnings',
        'download_cards_csv': 'Download cards CSV', 'download_json': 'Download full JSON', 'download_app_json': 'Download app feed JSON',
        'download_md': 'Download Markdown report', 'download_html': 'Download HTML report', 'download_copy': 'Download copy text',
        'markdown': 'Copy/paste report', 'short_copy': 'Short copy', 'json_feed': 'JSON feed', 'app_feed': 'App feed',
        'settings_json': 'Current brand payload', 'preview_cols': 'Preview columns', 'quality_summary': 'Quality summary',
        'require_odds': 'Require verified sportsbook odds for publish-ready status',
        'odds_warning': 'Odds are unavailable or not verified on {count} selected row(s). These rows are model-only, edge is N/A, and they are not publish-ready.',
        'edge_note': 'Edge requires verified sportsbook odds. Missing or API-limited odds display as N/A and block publish-ready status.',
    },
    'es': {
        'title': 'Estudio de Reportes para Consumidores', 'caption': 'Convierte filas ABA en tarjetas, reportes, feeds y copy.',
        'workspace': 'ID de cliente / workspace', 'workspace_help': 'Usa un ID separado para cada cliente, tipster, app o marca de reporte.',
        'input': 'Filas de entrada', 'use_saved': 'Usar filas guardadas del workspace', 'upload': 'Subir CSV', 'source': 'Fuente',
        'no_rows': 'No hay filas. Usa Odds Lock Pro primero o sube un CSV.', 'brand': 'Marca white-label',
        'brand_name': 'Marca / tipster', 'tagline': 'Lema', 'report_title': 'Título del reporte', 'logo_url': 'URL del logo',
        'disclaimer': 'Aviso legal', 'filters': 'Filtros del reporte', 'max_rows': 'Máximo de picks/tarjetas',
        'min_probability': 'Probabilidad mínima del modelo', 'official_only': 'Solo oficiales/listos para prueba', 'pending_only': 'Solo pendientes/próximos',
        'sport_filter': 'Deportes', 'market_filter': 'Mercados', 'cards_tab': 'Tarjetas premium', 'magazine_tab': 'Reporte revista',
        'copy_tab': 'Copy WhatsApp / Telegram', 'feed_tab': 'Feed CSV / JSON', 'settings_tab': 'Configuración de marca', 'diagnostics_tab': 'Diagnóstico',
        'cards': 'Tarjetas', 'avg_prob': 'Probabilidad media', 'proof_rows': 'Filas con prueba', 'publish_ready': 'Listas para publicar', 'warnings': 'Alertas',
        'download_cards_csv': 'Descargar CSV de tarjetas', 'download_json': 'Descargar JSON completo', 'download_app_json': 'Descargar JSON para app',
        'download_md': 'Descargar reporte Markdown', 'download_html': 'Descargar reporte HTML', 'download_copy': 'Descargar copy',
        'markdown': 'Reporte para copiar/pegar', 'short_copy': 'Copy corto', 'json_feed': 'Feed JSON', 'app_feed': 'Feed para app',
        'settings_json': 'Payload actual de marca', 'preview_cols': 'Columnas de vista previa', 'quality_summary': 'Resumen de calidad',
        'require_odds': 'Requerir cuotas verificadas para marcar listo para publicar',
        'odds_warning': 'No hay cuotas verificadas en {count} fila(s). Estas filas son solo modelo, el edge es N/A y no están listas para publicar.',
        'edge_note': 'El edge requiere cuotas verificadas. Si faltan cuotas o la API está limitada, se muestra N/A y no se puede publicar.',
    },
}

HANDOFF_KEYS = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows', 'pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'what_are_the_odds_latest_rows', 'ara_latest_predictions')
UNVERIFIED_SOURCE_TOKENS = ('.csv', 'session:', 'saved:', 'persistent', 'ledger', 'storage', 'upload', 'export', 'model_only', 'high_confidence', 'pro_predictor', 'fallback', 'unavailable', 'missing', 'no odds', 'no_odds', 'api limit', 'limit reached', 'quota', 'maxed', 'rate limit', 'offline', 'simulated', 'research', 'test')
INTERNAL_BULLET_TOKENS = ('internal decision', 'decisión interna', 'decision interna', 'play small', 'play_small', 'play strong', 'play_strong', 'watch only', 'watch_only', 'play_', 'watch_')
ODDS_BLOCKER_TEXT = 'Missing valid odds'
ODDS_BLOCKER_TEXT_ES = 'Falta cuota válida'


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def download_link(label: str, payload: str | bytes, filename: str, mime: str) -> None:
    data = payload if isinstance(payload, bytes) else payload.encode('utf-8')
    encoded = base64.b64encode(data).decode('ascii')
    st.markdown(f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:{html.escape(mime)};base64,{encoded}">{html.escape(label)}</a>', unsafe_allow_html=True)


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return 'persistent_proof_ledger', persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return f'session:{key}', pd.DataFrame(rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    return (f'saved:{key}', pd.DataFrame(rows)) if rows else ('', pd.DataFrame())


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames, names = [], []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame['source_file'] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f'{upload.name}: {exc}')
    return (', '.join(names), pd.concat(frames, ignore_index=True, sort=False)) if frames else ('', pd.DataFrame())


def probability_metric(cards: pd.DataFrame) -> str:
    if cards.empty or 'model_probability' not in cards.columns:
        return 'N/A'
    values = pd.to_numeric(cards['model_probability'], errors='coerce').dropna()
    return 'N/A' if values.empty else f'{float(values.mean()) * 100:.1f}%'


def unique_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame[column].tolist() if safe_text(value)})


def filter_by_multiselect(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    if frame.empty or not selected or column not in frame.columns:
        return frame
    return frame[frame[column].map(safe_text).isin(selected)].copy()


def status_series(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(dtype=str) if frame.empty else frame.apply(lambda row: result_status(row.to_dict()), axis=1)


def _safe_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def _probability_float(value: Any) -> float | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    parsed = parsed / 100.0 if parsed > 1.0 else parsed
    return parsed if 0.0 <= parsed <= 1.0 else None


def _pct_label(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return 'N/A'
    return f'{value * 100:+.1f}%' if signed else f'{value * 100:.1f}%'


def _decimal_price(row: Mapping[str, Any]) -> float | None:
    for name in ('decimal_price', 'best_price', 'average_price', 'avg_price', 'sportsbook_odds', 'odds_decimal'):
        value = _safe_float(row.get(name))
        if value is not None and value > 1.0:
            return value
    return None


def _market_source(row: Mapping[str, Any]) -> str:
    # Prefer odds_source. A row can use bookmaker='consensus_average' while still having real Odds API prices.
    return safe_text(row.get('odds_source')) or safe_text(row.get('bookmaker')) or safe_text(row.get('sportsbook')) or safe_text(row.get('book'))


def has_verified_market_odds(row: Mapping[str, Any]) -> bool:
    source = _market_source(row).lower()
    if not source or any(token in source for token in UNVERIFIED_SOURCE_TOKENS):
        return False
    return _decimal_price(row) is not None


def _append_semicolon(value: Any, addition: str) -> str:
    items = [part.strip() for part in safe_text(value).split(';') if part.strip()]
    if addition not in items:
        items.append(addition)
    return '; '.join(items)


def _hide_internal_bullets(out: pd.DataFrame, idx: Any) -> None:
    bullet_cols = [f'bullet_{i}' for i in range(1, 5) if f'bullet_{i}' in out.columns]
    public_bullets: list[str] = []
    for col in bullet_cols:
        bullet = safe_text(out.at[idx, col])
        if not bullet:
            continue
        lower = bullet.lower()
        if any(token in lower for token in INTERNAL_BULLET_TOKENS):
            continue
        public_bullets.append(bullet)
    for pos, col in enumerate(bullet_cols):
        out.at[idx, col] = public_bullets[pos] if pos < len(public_bullets) else ''
    if 'short_summary' in out.columns and any(token in safe_text(out.at[idx, 'short_summary']).lower() for token in INTERNAL_BULLET_TOKENS):
        out.at[idx, 'short_summary'] = public_bullets[0] if public_bullets else ''


def sanitize_model_only_rows(frame: pd.DataFrame, *, require_verified_odds: bool) -> tuple[pd.DataFrame, int]:
    if frame is None or frame.empty or not require_verified_odds:
        return frame, 0
    out = frame.copy()
    invalid_mask = ~out.apply(lambda row: has_verified_market_odds(row.to_dict()), axis=1)
    invalid_count = int(invalid_mask.sum())
    if invalid_count == 0:
        return out, 0

    clear_cols = ['decimal_price', 'best_price', 'average_price', 'avg_price', 'sportsbook_odds', 'odds_decimal', 'model_edge', 'model_market_edge', 'edge_probability', 'edge', 'expected_value_per_unit', 'computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev', 'ev', '_robust_expected_value', 'robust_expected_value', '_robust_profit_at_80_percent', 'robust_profit_at_80_percent']
    for col in clear_cols + ['bookmaker', 'sportsbook', 'book', 'odds_source', 'odds_status', 'ledger_type', 'lock_blockers']:
        if col not in out.columns:
            out[col] = None
        out[col] = out[col].astype('object')

    out.loc[invalid_mask, clear_cols] = None
    out.loc[invalid_mask, ['bookmaker', 'sportsbook', 'book']] = ''
    out.loc[invalid_mask, 'odds_source'] = 'odds_unavailable_api_limit'
    out.loc[invalid_mask, 'odds_status'] = 'odds_unavailable'
    out.loc[invalid_mask, 'official_lock_ready'] = False
    out.loc[invalid_mask, 'official_ev_pick'] = False
    out.loc[invalid_mask, 'ledger_type'] = 'research_model_only'
    out.loc[invalid_mask, 'lock_blockers'] = out.loc[invalid_mask, 'lock_blockers'].map(lambda value: _append_semicolon(value, 'odds_unavailable'))
    return out, invalid_count


def enrich_card_values(cards: pd.DataFrame, source_rows: pd.DataFrame) -> pd.DataFrame:
    if cards is None or cards.empty:
        return pd.DataFrame() if cards is None else cards
    out = cards.copy()
    source_records = source_rows.to_dict('records') if source_rows is not None and not source_rows.empty else []
    for col in ['decimal_price', 'odds_label', 'market_probability', 'market_probability_label', 'edge', 'edge_label', 'value_rating', 'probability_audit', 'odds_status', 'consumer_status', 'quality_flags', 'short_summary'] + [f'bullet_{i}' for i in range(1, 5)]:
        if col not in out.columns:
            out[col] = None
        out[col] = out[col].astype('object')

    for pos, idx in enumerate(out.index):
        source_row = source_records[pos] if pos < len(source_records) else out.loc[idx].to_dict()
        model_prob = _probability_float(out.at[idx, 'model_probability'] if 'model_probability' in out.columns else None)
        odds_valid = has_verified_market_odds(source_row)
        price = _decimal_price(source_row) if odds_valid else None
        market_prob = None if price is None else 1.0 / price
        edge = None if model_prob is None or market_prob is None else model_prob - market_prob
        out.at[idx, 'model_probability'] = model_prob
        out.at[idx, 'probability_label'] = _pct_label(model_prob)
        out.at[idx, 'decimal_price'] = f'{price:.2f}' if price is not None else 'N/A'
        out.at[idx, 'odds_label'] = f'{price:.2f}' if price is not None else 'N/A'
        out.at[idx, 'market_probability'] = market_prob
        out.at[idx, 'market_probability_label'] = _pct_label(market_prob)
        out.at[idx, 'edge'] = edge
        out.at[idx, 'edge_label'] = _pct_label(edge, signed=True)
        out.at[idx, 'odds_status'] = 'verified' if odds_valid else 'unavailable'
        if odds_valid:
            out.at[idx, 'value_rating'] = 'Strong Value' if edge is not None and edge >= 0.05 else ('Positive Value' if edge is not None and edge >= 0.02 else 'Neutral')
            out.at[idx, 'probability_audit'] = 'Verified sportsbook odds loaded'
            out.at[idx, 'consumer_status'] = 'Official Pick' if safe_text(out.at[idx, 'proof_id'] if 'proof_id' in out.columns else '') else 'Tracked Pick'
        else:
            out.at[idx, 'publish_ready'] = False
            flag = ODDS_BLOCKER_TEXT if LANG == 'en' else ODDS_BLOCKER_TEXT_ES
            out.at[idx, 'quality_flags'] = _append_semicolon(out.at[idx, 'quality_flags'], flag)
            out.at[idx, 'value_rating'] = 'Odds unavailable' if LANG == 'en' else 'Cuotas no disponibles'
            out.at[idx, 'probability_audit'] = 'Odds unavailable/API limit; model-only, not publish-ready' if LANG == 'en' else 'Cuotas no disponibles/límite API; solo modelo, no publicar'
            if 'publish_status' in out.columns and 'official' in safe_text(out.at[idx, 'publish_status']).lower():
                out.at[idx, 'publish_status'] = 'Research / test' if LANG == 'en' else 'Investigación / prueba'
            out.at[idx, 'consumer_status'] = 'Model-only / odds unavailable' if LANG == 'en' else 'Solo modelo / sin cuotas'
        _hide_internal_bullets(out, idx)
    return out


def render_cards_html(cards: pd.DataFrame, brand: BrandSettings) -> str:
    if cards is None or cards.empty:
        return '<p>No picks available.</p>' if LANG == 'en' else '<p>No hay picks disponibles.</p>'
    css = '<style>.aba-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}.aba-card{border:1px solid rgba(125,125,125,.35);border-radius:18px;padding:1rem}.aba-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.4rem}.aba-box{border:1px solid rgba(125,125,125,.25);border-radius:12px;padding:.45rem}.aba-k{font-size:.7rem;opacity:.65;text-transform:uppercase}.aba-v{font-weight:800}</style>'
    parts = [css, '<div class="aba-grid">']
    for _, row in cards.fillna('').iterrows():
        bullets = [safe_text(row.get(f'bullet_{i}')) for i in range(1, 5) if safe_text(row.get(f'bullet_{i}'))]
        parts += [
            '<div class="aba-card">',
            f'<div style="opacity:.7;font-weight:700">{html.escape(safe_text(row.get("sport")) or "Match")}</div>',
            f'<h3>{html.escape(safe_text(row.get("event")))}</h3>',
            f'<p><b>Pick:</b> {html.escape(safe_text(row.get("prediction") or row.get("tendency")))}</p>',
            '<div class="aba-row">',
            f'<div class="aba-box"><div class="aba-k">Odds</div><div class="aba-v">{html.escape(safe_text(row.get("decimal_price")) or "N/A")}</div></div>',
            f'<div class="aba-box"><div class="aba-k">Model</div><div class="aba-v">{html.escape(safe_text(row.get("probability_label")) or "N/A")}</div></div>',
            f'<div class="aba-box"><div class="aba-k">Market</div><div class="aba-v">{html.escape(safe_text(row.get("market_probability_label")) or "N/A")}</div></div>',
            f'<div class="aba-box"><div class="aba-k">Edge</div><div class="aba-v">{html.escape(safe_text(row.get("edge_label")) or "N/A")}</div></div>',
            '</div>',
            f'<p><b>Status:</b> {html.escape(safe_text(row.get("consumer_status")) or safe_text(row.get("publish_status")))}</p>',
            f'<p><b>Data check:</b> {html.escape(safe_text(row.get("probability_audit")))}</p>',
        ]
        if bullets:
            parts.append('<ul>')
            parts.extend(f'<li>{html.escape(bullet)}</li>' for bullet in bullets[:3])
            parts.append('</ul>')
        parts.append('</div>')
    parts.append('</div>')
    return '\n'.join(parts)


st.title(t('title'))
st.caption(t('caption'))

with st.expander(t('input'), expanded=True):
    workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'), help=t('workspace_help'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    use_saved = st.checkbox(t('use_saved'), value=True)
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ('', pd.DataFrame())
    upload_source, upload_rows = read_uploaded_rows()
    raw = pd.concat([frame for frame in [saved_rows, upload_rows] if frame is not None and not frame.empty], ignore_index=True, sort=False) if (not saved_rows.empty or not upload_rows.empty) else pd.DataFrame()
    st.caption(f'{t("source")}: ' + (', '.join([name for name in [saved_source, upload_source] if name]) or 'none'))

if raw.empty:
    st.warning(t('no_rows'))
    st.stop()

normalized = normalize_frame(raw)

with st.expander(t('brand'), expanded=True):
    c1, c2 = st.columns(2)
    brand_name = c1.text_input(t('brand_name'), value=st.session_state.get('consumer_report_brand_name', 'ABA Signal Pro'))
    tagline = c2.text_input(t('tagline'), value=st.session_state.get('consumer_report_tagline', 'Powered by Reparodynamics'))
    report_title = c1.text_input(t('report_title'), value=st.session_state.get('consumer_report_title', 'Reporte de Tendencias' if LANG == 'es' else 'Trend Report'))
    logo_url = c2.text_input(t('logo_url'), value=st.session_state.get('consumer_report_logo_url', ''))
    disclaimer_default = 'Contenido informativo. No garantiza resultados.' if LANG == 'es' else 'Informational content only. Results are not guaranteed.'
    disclaimer = st.text_area(t('disclaimer'), value=st.session_state.get('consumer_report_disclaimer', disclaimer_default), height=80)
for key, value in {'consumer_report_brand_name': brand_name, 'consumer_report_tagline': tagline, 'consumer_report_title': report_title, 'consumer_report_logo_url': logo_url, 'consumer_report_disclaimer': disclaimer}.items():
    st.session_state[key] = value
brand = BrandSettings(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace_id, language=LANG, logo_url=logo_url, disclaimer=disclaimer)

with st.expander(t('filters'), expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    max_rows = c1.number_input(t('max_rows'), min_value=1, max_value=100, value=12, step=1)
    min_probability = c2.number_input(t('min_probability'), min_value=0.0, max_value=0.99, value=0.0, step=0.01)
    official_only = c3.checkbox(t('official_only'), value=False)
    pending_only = c4.checkbox(t('pending_only'), value=False)
    require_verified_odds = c5.checkbox(t('require_odds'), value=True)
    f1, f2, f3, f4 = st.columns(4)
    sport_filter = f1.multiselect(t('sport_filter'), unique_options(normalized, 'sport'))
    market_filter = f2.multiselect(t('market_filter'), unique_options(normalized, 'market_type'))
    status_values = sorted({safe_text(value) for value in status_series(normalized).tolist() if safe_text(value)})
    result_filter = f3.multiselect('Result status' if LANG == 'en' else 'Estado resultado', status_values)
    source_filter = f4.multiselect(t('source'), unique_options(normalized, 'source_file'))

filtered = normalized.copy()
filtered = filter_by_multiselect(filtered, 'sport', sport_filter)
filtered = filter_by_multiselect(filtered, 'market_type', market_filter)
filtered = filter_by_multiselect(filtered, 'source_file', source_filter)
if result_filter and not filtered.empty:
    filtered = filtered[status_series(filtered).isin(result_filter)].copy()

filtered, unavailable_count = sanitize_model_only_rows(filtered, require_verified_odds=require_verified_odds)
if unavailable_count:
    st.warning(t('odds_warning').format(count=unavailable_count))
report_rows = prepare_report_frame(filtered, min_probability=float(min_probability), official_only=bool(official_only), pending_only=bool(pending_only), max_rows=int(max_rows))
report_rows, _ = sanitize_model_only_rows(report_rows, require_verified_odds=require_verified_odds)
cards = enrich_card_values(consumer_cards(report_rows, brand), report_rows)
st.session_state['consumer_report_latest_cards'] = cards.to_dict('records') if not cards.empty else []

proof_rows = int(cards.get('proof_id', pd.Series(dtype=str)).map(safe_text).ne('').sum()) if not cards.empty and 'proof_id' in cards.columns else 0
quality = report_quality_summary(cards)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(t('cards'), int(len(cards)))
m2.metric(t('avg_prob'), probability_metric(cards))
m3.metric(t('proof_rows'), proof_rows)
m4.metric(t('publish_ready'), quality['publish_ready'])
m5.metric(t('warnings'), quality['warnings'])
st.caption(t('edge_note'))

markdown_report = render_magazine_markdown(cards, brand)
html_cards = render_cards_html(cards, brand)
html_report = render_magazine_html(cards, brand)
short_copy = render_short_copy(cards, brand)
json_feed = cards_to_json(cards, brand)
app_feed = cards_to_app_feed(cards, brand)
csv_payload = cards.to_csv(index=False) if not cards.empty else ''
safe_workspace = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in workspace_id)
tabs = st.tabs([t('cards_tab'), t('magazine_tab'), t('copy_tab'), t('feed_tab'), t('settings_tab'), t('diagnostics_tab')])
with tabs[0]:
    st.markdown(html_cards, unsafe_allow_html=True)
    download_link(t('download_cards_csv'), csv_payload, f'consumer_cards_{safe_workspace}.csv', 'text/csv')
with tabs[1]:
    st.markdown(html_report, unsafe_allow_html=True)
    st.text_area(t('markdown'), value=markdown_report, height=360)
    c1, c2 = st.columns(2)
    with c1:
        download_link(t('download_md'), markdown_report, f'magazine_report_{safe_workspace}.md', 'text/markdown')
    with c2:
        download_link(t('download_html'), html_report, f'magazine_report_{safe_workspace}.html', 'text/html')
with tabs[2]:
    st.text_area(t('short_copy'), value=short_copy, height=360)
    download_link(t('download_copy'), short_copy, f'report_copy_{safe_workspace}.txt', 'text/plain')
with tabs[3]:
    st.dataframe(cards, use_container_width=True, hide_index=True)
    st.text_area(t('json_feed'), value=json_feed, height=260)
    st.text_area(t('app_feed'), value=app_feed, height=260)
    c1, c2, c3 = st.columns(3)
    with c1:
        download_link(t('download_cards_csv'), csv_payload, f'consumer_cards_{safe_workspace}.csv', 'text/csv')
    with c2:
        download_link(t('download_json'), json_feed, f'consumer_feed_{safe_workspace}.json', 'application/json')
    with c3:
        download_link(t('download_app_json'), app_feed, f'app_feed_{safe_workspace}.json', 'application/json')
with tabs[4]:
    st.json(brand_payload(brand))
    st.caption(t('settings_json'))
with tabs[5]:
    st.json(quality)
    st.caption(t('quality_summary'))
    preview_cols = ['event', 'sport', 'market', 'prediction', 'decimal_price', 'odds_status', 'probability_label', 'market_probability_label', 'edge_label', 'value_rating', 'consumer_status', 'probability_audit', 'confidence', 'risk', 'publish_status', 'proof_id', 'quality_flags', 'lock_blockers']
    cols = [col for col in preview_cols if col in cards.columns]
    st.caption(t('preview_cols'))
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
