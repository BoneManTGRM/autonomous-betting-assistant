from __future__ import annotations

import base64
import html
from typing import Any

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
        'title': 'Consumer Report Studio',
        'caption': 'Turn ABA rows into high-level consumer cards, magazine reports, app feeds, and tipster-ready copy.',
        'workspace': 'Client / Workspace ID',
        'workspace_help': 'Use a separate ID per client, tipster, app, or report brand.',
        'input': 'Input rows',
        'use_saved': 'Use saved workspace rows',
        'upload': 'Upload CSV rows',
        'source': 'Source',
        'no_rows': 'No rows found. Use Odds Lock Pro first or upload a CSV.',
        'brand': 'White-label brand',
        'brand_name': 'Brand / tipster name',
        'tagline': 'Tagline',
        'report_title': 'Report title',
        'logo_url': 'Logo URL',
        'disclaimer': 'Disclaimer',
        'filters': 'Report filters',
        'max_rows': 'Max picks/cards',
        'min_probability': 'Minimum model probability',
        'official_only': 'Official/proof-ready only',
        'pending_only': 'Pending/upcoming only',
        'sport_filter': 'Sports',
        'market_filter': 'Markets',
        'cards_tab': 'High-level cards',
        'magazine_tab': 'Magazine report',
        'copy_tab': 'WhatsApp / Telegram copy',
        'feed_tab': 'CSV / JSON feed',
        'settings_tab': 'Brand settings',
        'diagnostics_tab': 'Diagnostics',
        'cards': 'Cards',
        'avg_prob': 'Avg probability',
        'proof_rows': 'Proof rows',
        'publish_ready': 'Publish-ready',
        'warnings': 'Warnings',
        'download_cards_csv': 'Download cards CSV',
        'download_json': 'Download full JSON',
        'download_app_json': 'Download app feed JSON',
        'download_md': 'Download Markdown report',
        'download_html': 'Download HTML report',
        'download_copy': 'Download copy text',
        'markdown': 'Copy/paste report',
        'short_copy': 'Short copy',
        'json_feed': 'JSON feed',
        'app_feed': 'App feed',
        'settings_json': 'Current brand payload',
        'preview_cols': 'Preview columns',
        'quality_summary': 'Quality summary',
    },
    'es': {
        'title': 'Estudio de Reportes para Consumidores',
        'caption': 'Convierte filas ABA en tarjetas premium, reportes tipo revista, feeds para app y copy para tipsters.',
        'workspace': 'ID de cliente / workspace',
        'workspace_help': 'Usa un ID separado para cada cliente, tipster, app o marca de reporte.',
        'input': 'Filas de entrada',
        'use_saved': 'Usar filas guardadas del workspace',
        'upload': 'Subir CSV',
        'source': 'Fuente',
        'no_rows': 'No hay filas. Usa Odds Lock Pro primero o sube un CSV.',
        'brand': 'Marca white-label',
        'brand_name': 'Marca / tipster',
        'tagline': 'Lema',
        'report_title': 'Título del reporte',
        'logo_url': 'URL del logo',
        'disclaimer': 'Aviso legal',
        'filters': 'Filtros del reporte',
        'max_rows': 'Máximo de picks/tarjetas',
        'min_probability': 'Probabilidad mínima del modelo',
        'official_only': 'Solo oficiales/listos para prueba',
        'pending_only': 'Solo pendientes/próximos',
        'sport_filter': 'Deportes',
        'market_filter': 'Mercados',
        'cards_tab': 'Tarjetas premium',
        'magazine_tab': 'Reporte revista',
        'copy_tab': 'Copy WhatsApp / Telegram',
        'feed_tab': 'Feed CSV / JSON',
        'settings_tab': 'Configuración de marca',
        'diagnostics_tab': 'Diagnóstico',
        'cards': 'Tarjetas',
        'avg_prob': 'Probabilidad media',
        'proof_rows': 'Filas con prueba',
        'publish_ready': 'Listas para publicar',
        'warnings': 'Alertas',
        'download_cards_csv': 'Descargar CSV de tarjetas',
        'download_json': 'Descargar JSON completo',
        'download_app_json': 'Descargar JSON para app',
        'download_md': 'Descargar reporte Markdown',
        'download_html': 'Descargar reporte HTML',
        'download_copy': 'Descargar copy',
        'markdown': 'Reporte para copiar/pegar',
        'short_copy': 'Copy corto',
        'json_feed': 'Feed JSON',
        'app_feed': 'Feed para app',
        'settings_json': 'Payload actual de marca',
        'preview_cols': 'Columnas de vista previa',
        'quality_summary': 'Resumen de calidad',
    },
}

HANDOFF_KEYS = (
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
    'pro_predictor_high_confidence_rows',
    'pro_predictor_latest_rows',
    'what_are_the_odds_latest_rows',
    'ara_latest_predictions',
)


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def download_link(label: str, payload: str | bytes, filename: str, mime: str) -> None:
    data = payload if isinstance(payload, bytes) else payload.encode('utf-8')
    encoded = base64.b64encode(data).decode('ascii')
    st.markdown(
        f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:{html.escape(mime)};base64,{encoded}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return 'persistent_proof_ledger', persistent
    for key in HANDOFF_KEYS:
        session_rows = st.session_state.get(key) or []
        if session_rows:
            return f'session:{key}', pd.DataFrame(session_rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    if rows:
        return f'saved:{key}', pd.DataFrame(rows)
    return '', pd.DataFrame()


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame['source_file'] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f'{upload.name}: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


def probability_metric(cards: pd.DataFrame) -> str:
    if cards.empty or 'model_probability' not in cards.columns:
        return 'N/A'
    values = pd.to_numeric(cards['model_probability'], errors='coerce').dropna()
    if values.empty:
        return 'N/A'
    return f'{float(values.mean()) * 100:.1f}%'


def unique_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame[column].tolist() if safe_text(value)})


def filter_by_multiselect(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    if frame.empty or not selected or column not in frame.columns:
        return frame
    return frame[frame[column].map(safe_text).isin(selected)].copy()


def status_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=str)
    return frame.apply(lambda row: result_status(row.to_dict()), axis=1)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _probability_float(value: Any) -> float | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed /= 100.0
    return parsed if 0.0 <= parsed <= 1.0 else None


def _pct_label(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return '-'
    return f'{value * 100:+.1f}%' if signed else f'{value * 100:.1f}%'


def _market_probability_from_odds(odds: Any) -> float | None:
    decimal_odds = _safe_float(odds)
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    return 1.0 / decimal_odds


def _consumer_status(row: pd.Series, language: str) -> str:
    status = safe_text(row.get('publish_status')).lower()
    confidence = safe_text(row.get('confidence')).lower()
    proof_id = safe_text(row.get('proof_id'))
    spanish = language == 'es'

    if 'official' in status or 'oficial' in status:
        return 'Pick oficial' if spanish else 'Official Pick'
    if 'research' in status or 'investigación' in status or 'investigacion' in status:
        return 'Lean del modelo' if spanish else 'Research Lean'
    if proof_id or 'locked' in status or 'bloqueado' in status:
        return 'Pick trackeado' if spanish else 'Tracked Pick'
    if 'high' in confidence or 'alta' in confidence:
        return 'Señal alta' if spanish else 'High Signal'
    return 'Sin prueba' if spanish else 'Unverified'


def _premium_verdict(row: pd.Series, language: str) -> str:
    return _consumer_status(row, language)


def _consumer_bullets(row: pd.Series, language: str) -> list[str]:
    spanish = language == 'es'
    pick = safe_text(row.get('tendency') or row.get('prediction'))
    market = safe_text(row.get('market'))
    odds = safe_text(row.get('decimal_price')) or '-'
    probability = safe_text(row.get('probability_label'))
    market_probability = safe_text(row.get('market_probability_label'))
    edge = safe_text(row.get('edge_label'))
    proof_id = safe_text(row.get('proof_id'))
    status = safe_text(row.get('consumer_status'))
    raw_bullets = [safe_text(row.get(f'bullet_{index}')) for index in range(1, 5)]
    banned_terms = (
        'no clear price edge', 'estimated ev per unit: -0.0', 'estimated ev per unit: 0.0',
        'review before publishing', 'internal decision', 'decisión interna', 'decision interna',
        'señal sin ventaja de cuota clara', 'ev estimado por unidad: -0.0', 'ev estimado por unidad: 0.0',
        'logged price', 'cuota registrada', 'consensus_average',
    )
    clean: list[str] = []
    for bullet in raw_bullets:
        lower = bullet.lower()
        if not bullet or any(term in lower for term in banned_terms):
            continue
        if bullet not in clean:
            clean.append(bullet)

    already_has_probability = any(('probability' in item.lower() or 'probabilidad' in item.lower()) for item in clean)
    fallback: list[str] = []
    if probability and not already_has_probability:
        fallback.append(f'El modelo estima {probability} para {pick}.' if spanish else f'Model probability is {probability} for {pick}.')
    if market_probability and edge:
        fallback.append(f'Prob. mercado: {market_probability} | Edge: {edge}.' if spanish else f'Market probability: {market_probability} | Edge: {edge}.')
    elif market or odds:
        fallback.append(f'Mercado: {market} | Cuota: {odds}.' if spanish else f'Market: {market} | Odds: {odds}.')
    if proof_id:
        fallback.append(f'Registrado con Proof ID {proof_id}.' if spanish else f'Tracked with Proof ID {proof_id}.')
    elif status:
        fallback.append(f'Estado: {status}.' if spanish else f'Status: {status}.')

    for item in fallback:
        if len(clean) >= 3:
            break
        if item not in clean:
            clean.append(item)
    return clean[:3]


def enrich_value_columns(cards: pd.DataFrame, language: str) -> pd.DataFrame:
    if cards is None or cards.empty:
        return pd.DataFrame() if cards is None else cards
    out = cards.copy()

    model_probs: list[float | None] = []
    market_probs: list[float | None] = []
    edges: list[float | None] = []
    statuses: list[str] = []

    for _, row in out.iterrows():
        model_prob = _probability_float(row.get('model_probability'))
        market_prob = _market_probability_from_odds(row.get('decimal_price'))
        edge = model_prob - market_prob if model_prob is not None and market_prob is not None else None
        model_probs.append(model_prob)
        market_probs.append(market_prob)
        edges.append(edge)
        statuses.append(_consumer_status(row, language))

    out['model_probability'] = model_probs
    out['probability_label'] = [_pct_label(value) for value in model_probs]
    out['market_probability'] = market_probs
    out['market_probability_label'] = [_pct_label(value) for value in market_probs]
    out['edge'] = edges
    out['edge_label'] = [_pct_label(value, signed=True) for value in edges]
    out['consumer_status'] = statuses
    return out


def render_premium_cards_html(cards: pd.DataFrame, brand: BrandSettings) -> str:
    brand = brand.normalized()
    language = brand.language
    spanish = language == 'es'
    if cards is None or cards.empty:
        return '<p>No hay picks disponibles.</p>' if spanish else '<p>No picks available.</p>'

    title = brand.report_title or ('Reporte de Tendencias' if spanish else 'Trend Report')
    subtitle = 'Vista ejecutiva para consumidores' if spanish else 'Executive consumer view'
    labels = {
        'recommendation': 'Recomendación' if spanish else 'Recommendation',
        'odds': 'Cuota' if spanish else 'Odds',
        'model_prob': 'Prob. modelo' if spanish else 'Model Prob.',
        'market_prob': 'Prob. mercado' if spanish else 'Market Prob.',
        'edge': 'Edge',
        'status': 'Estado' if spanish else 'Status',
        'match': 'Partido' if spanish else 'Match',
        'source': 'Fuente' if spanish else 'Source',
        'proof_pending': 'Proof pendiente' if spanish else 'Proof pending',
    }

    css = '''
    <style>
    .aba-premium-wrap{margin:1rem 0 1.5rem 0}
    .aba-premium-hero{border:1px solid rgba(125,125,125,.35);border-radius:24px;padding:1.1rem 1.25rem;margin-bottom:1rem;background:linear-gradient(135deg,rgba(255,255,255,.10),rgba(255,255,255,.035))}
    .aba-premium-hero h2{margin:.1rem 0 .25rem 0;font-size:1.55rem}
    .aba-premium-hero p{margin:.15rem 0;opacity:.82}
    .aba-premium-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:1.05rem}
    .aba-premium-card{position:relative;overflow:hidden;border:1px solid rgba(125,125,125,.38);border-radius:24px;padding:1.05rem 1.08rem;background:radial-gradient(circle at top right,rgba(255,255,255,.12),rgba(255,255,255,.035) 38%,rgba(255,255,255,.025));box-shadow:0 10px 28px rgba(0,0,0,.18)}
    .aba-premium-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:rgba(255,255,255,.42)}
    .aba-card-top{display:flex;justify-content:space-between;gap:.75rem;align-items:flex-start}
    .aba-card-league{font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;opacity:.68;font-weight:750}
    .aba-verdict{display:inline-block;border:1px solid rgba(125,125,125,.45);border-radius:999px;padding:.22rem .55rem;font-size:.76rem;font-weight:800;white-space:nowrap}
    .aba-premium-card h3{font-size:1.55rem;line-height:1.08;margin:.52rem 0 .7rem 0}
    .aba-recommendation{border-radius:18px;padding:.82rem .9rem;background:rgba(255,255,255,.07);margin:.4rem 0 .85rem 0}
    .aba-recommendation .label{font-size:.75rem;text-transform:uppercase;letter-spacing:.07em;opacity:.67;font-weight:850}
    .aba-recommendation .pick{font-size:1.22rem;font-weight:900;margin:.2rem 0 0 0}
    .aba-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.45rem;margin:.7rem 0}
    .aba-metric{border:1px solid rgba(125,125,125,.33);border-radius:16px;padding:.48rem .55rem}
    .aba-metric .k{font-size:.66rem;text-transform:uppercase;letter-spacing:.055em;opacity:.62;font-weight:800}
    .aba-metric .v{font-size:.9rem;font-weight:850;margin-top:.08rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .aba-meter{height:8px;border-radius:999px;background:rgba(125,125,125,.25);overflow:hidden;margin:.65rem 0 .75rem 0}
    .aba-meter span{display:block;height:100%;border-radius:999px;background:rgba(255,255,255,.58)}
    .aba-proof{font-size:.83rem;opacity:.82;margin:.35rem 0 .2rem 0}
    .aba-why{margin:.72rem 0 0 0;padding-left:1.15rem}
    .aba-why li{margin:.35rem 0;line-height:1.35}
    .aba-card-foot{font-size:.78rem;opacity:.62;margin-top:.65rem}
    @media(max-width:760px){.aba-premium-grid{grid-template-columns:1fr}.aba-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.aba-premium-card h3{font-size:1.35rem}}
    </style>
    '''
    parts = [
        css,
        '<div class="aba-premium-wrap">',
        '<section class="aba-premium-hero">',
        f'<h2>{html.escape(title)}</h2>',
        f'<p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p>',
        f'<p>{html.escape(subtitle)} · {html.escape(brand.workspace_id)}</p>',
        '</section>',
        '<div class="aba-premium-grid">',
    ]

    for _, row in cards.fillna('').iterrows():
        probability = _probability_float(row.get('model_probability'))
        width = 0 if probability is None else max(0, min(100, int(round(probability * 100))))
        league = ' · '.join(part for part in [safe_text(row.get('sport')), safe_text(row.get('market'))] if part)
        event = safe_text(row.get('event'))
        pick = safe_text(row.get('tendency') or row.get('prediction'))
        odds = safe_text(row.get('decimal_price')) or '-'
        model_probability = safe_text(row.get('probability_label')) or '-'
        market_probability = safe_text(row.get('market_probability_label')) or '-'
        edge = safe_text(row.get('edge_label')) or '-'
        status = safe_text(row.get('consumer_status')) or _consumer_status(row, language)
        proof_id = safe_text(row.get('proof_id'))
        bullets = _consumer_bullets(row, language)
        proof_line = f'Proof ID: {proof_id}' if proof_id else labels['proof_pending']

        parts += [
            '<article class="aba-premium-card">',
            '<div class="aba-card-top">',
            f'<div class="aba-card-league">{html.escape(league or labels["match"])}</div>',
            f'<div class="aba-verdict">{html.escape(status)}</div>',
            '</div>',
            f'<h3>{html.escape(event)}</h3>',
            '<div class="aba-recommendation">',
            f'<div class="label">{html.escape(labels["recommendation"])}</div>',
            f'<div class="pick">{html.escape(pick)}</div>',
            '</div>',
            '<div class="aba-metrics">',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["odds"])}</div><div class="v">{html.escape(odds)}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["model_prob"])}</div><div class="v">{html.escape(model_probability)}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["market_prob"])}</div><div class="v">{html.escape(market_probability)}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["edge"])}</div><div class="v">{html.escape(edge)}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["status"])}</div><div class="v">{html.escape(status)}</div></div>',
            '</div>',
            f'<div class="aba-meter"><span style="width:{width}%"></span></div>',
            f'<div class="aba-proof">{html.escape(proof_line)}</div>',
        ]

        if bullets:
            parts.append('<ul class="aba-why">')
            for bullet in bullets:
                parts.append(f'<li>{html.escape(bullet)}</li>')
            parts.append('</ul>')

        source = safe_text(row.get('source'))
        if source:
            parts.append(f'<div class="aba-card-foot">{html.escape(labels["source"])}: {html.escape(source)}</div>')
        parts.append('</article>')

    parts += ['</div>', '</div>']
    disclaimer = brand.disclaimer or ('Contenido informativo. No garantiza resultados.' if spanish else 'Informational content only. Results are not guaranteed.')
    if disclaimer:
        parts.append(f'<p style="opacity:.72;font-size:.88rem">{html.escape(disclaimer)}</p>')
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
    parts = [frame for frame in [saved_rows, upload_rows] if frame is not None and not frame.empty]
    raw = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    sources = ', '.join([name for name in [saved_source, upload_source] if name]) or 'none'
    st.caption(f'{t("source")}: {sources}')

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

for key, value in {
    'consumer_report_brand_name': brand_name,
    'consumer_report_tagline': tagline,
    'consumer_report_title': report_title,
    'consumer_report_logo_url': logo_url,
    'consumer_report_disclaimer': disclaimer,
}.items():
    st.session_state[key] = value

brand = BrandSettings(
    brand_name=brand_name,
    tagline=tagline,
    report_title=report_title,
    workspace_id=workspace_id,
    language=LANG,
    logo_url=logo_url,
    disclaimer=disclaimer,
)

with st.expander(t('filters'), expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    max_rows = c1.number_input(t('max_rows'), min_value=1, max_value=100, value=12, step=1)
    min_probability = c2.number_input(t('min_probability'), min_value=0.0, max_value=0.99, value=0.0, step=0.01)
    official_only = c3.checkbox(t('official_only'), value=False)
    pending_only = c4.checkbox(t('pending_only'), value=False)

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
    statuses = status_series(filtered)
    filtered = filtered[statuses.isin(result_filter)].copy()

report_rows = prepare_report_frame(
    filtered,
    min_probability=float(min_probability),
    official_only=bool(official_only),
    pending_only=bool(pending_only),
    max_rows=int(max_rows),
)
cards = enrich_value_columns(consumer_cards(report_rows, brand), LANG)
st.session_state['consumer_report_latest_cards'] = cards.to_dict('records') if not cards.empty else []

proof_rows = int(cards.get('proof_id', pd.Series(dtype=str)).map(safe_text).ne('').sum()) if not cards.empty and 'proof_id' in cards.columns else 0
quality = report_quality_summary(cards)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(t('cards'), int(len(cards)))
m2.metric(t('avg_prob'), probability_metric(cards))
m3.metric(t('proof_rows'), proof_rows)
m4.metric(t('publish_ready'), quality['publish_ready'])
m5.metric(t('warnings'), quality['warnings'])

markdown_report = render_magazine_markdown(cards, brand)
html_cards = render_premium_cards_html(cards, brand)
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
    bullet_cols = [col for col in cards.columns if col.startswith('bullet_')]
    cols = [
        col for col in [
            'event', 'sport', 'market', 'prediction', 'decimal_price', 'probability_label',
            'market_probability_label', 'edge_label', 'consumer_status', 'confidence', 'risk',
            'publish_status', 'proof_id', 'quality_flags',
        ] + bullet_cols if col in cards.columns
    ]
    st.caption(t('preview_cols'))
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
