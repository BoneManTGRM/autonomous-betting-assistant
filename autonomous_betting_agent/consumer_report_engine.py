from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import expected_value, model_edge, robust_expected_value
from .row_normalizer import normalize_frame, probability_value, result_status, safe_text


@dataclass(frozen=True)
class BrandSettings:
    brand_name: str = 'ABA Signal Pro'
    tagline: str = 'Powered by Reparodynamics'
    report_title: str = ''
    workspace_id: str = 'test_01'
    language: str = 'es'
    logo_url: str = ''
    disclaimer: str = ''
    powered_by: str = 'ABA Signal Pro'

    def normalized(self) -> 'BrandSettings':
        return BrandSettings(
            brand_name=safe_text(self.brand_name) or 'ABA Signal Pro',
            tagline=safe_text(self.tagline) or 'Powered by Reparodynamics',
            report_title=safe_text(self.report_title),
            workspace_id=safe_text(self.workspace_id) or 'test_01',
            language=normalize_language(self.language),
            logo_url=safe_text(self.logo_url),
            disclaimer=safe_text(self.disclaimer),
            powered_by=safe_text(self.powered_by) or 'ABA Signal Pro',
        )


def normalize_language(value: Any) -> str:
    text = safe_text(value).lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def labels(language: str) -> dict[str, str]:
    if normalize_language(language) == 'es':
        return {
            'report': 'Reporte de Tendencias', 'cards': 'Tarjetas para consumidores',
            'tendency': 'Tendencia', 'market': 'Mercado', 'odds': 'Cuota',
            'confidence': 'Confianza', 'risk': 'Riesgo', 'proof': 'Proof ID',
            'workspace': 'Workspace', 'no_rows': 'No hay picks disponibles.',
            'disclaimer': 'Contenido informativo. No garantiza resultados.',
        }
    return {
        'report': 'Trend Report', 'cards': 'Consumer Cards', 'tendency': 'Pick',
        'market': 'Market', 'odds': 'Odds', 'confidence': 'Confidence',
        'risk': 'Risk', 'proof': 'Proof ID', 'workspace': 'Workspace',
        'no_rows': 'No picks available.',
        'disclaimer': 'Informational content only. Results are not guaranteed.',
    }


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _first_float(row: Mapping[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _safe_float(row.get(name))
        if value is not None:
            return value
    return None


def _pct(value: float | None) -> str:
    return '' if value is None else f'{value * 100:.1f}%'


def _decimal(value: Any) -> str:
    parsed = _safe_float(value)
    return safe_text(value) if parsed is None else f'{parsed:.2f}'


def _source_text(row: Mapping[str, Any]) -> str:
    return safe_text(row.get('bookmaker')) or safe_text(row.get('odds_source')) or safe_text(row.get('source_file'))


def market_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    raw = safe_text(row.get('market_type') or row.get('market')).lower()
    line = safe_text(row.get('line_point') or row.get('point') or row.get('handicap'))
    if raw in {'h2h', 'moneyline', 'ml', 'winner', 'ganador'}:
        label = 'Ganador' if lang == 'es' else 'Moneyline'
    elif 'spread' in raw or 'handicap' in raw or 'hándicap' in raw:
        label = 'Hándicap' if lang == 'es' else 'Spread'
    elif 'total' in raw or 'over' in raw or 'under' in raw:
        label = 'Total'
    elif 'btts' in raw or 'ambos' in raw:
        label = 'Ambos anotan' if lang == 'es' else 'Both teams to score'
    elif raw:
        label = raw.replace('_', ' ').title()
    else:
        label = 'Mercado' if lang == 'es' else 'Market'
    return f'{label} {line}'.strip() if line else label


def confidence_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    explicit = safe_text(row.get('public_confidence') or row.get('confidence_tier') or row.get('confidence'))
    if explicit:
        if lang == 'es':
            lookup = {
                'premium': 'Alta', 'qualified': 'Calificada', 'watch': 'En revisión',
                'research/test': 'Investigación', 'strict ultra 80': 'Alta estricta',
            }
            return lookup.get(explicit.lower(), explicit)
        return explicit
    probability = probability_value(row, 'model_probability')
    if probability is None:
        return 'Sin dato' if lang == 'es' else 'Unrated'
    if probability >= 0.70:
        return 'Alta+' if lang == 'es' else 'High+'
    if probability >= 0.62:
        return 'Alta' if lang == 'es' else 'High'
    if probability >= 0.57:
        return 'Media' if lang == 'es' else 'Medium'
    return 'Revisión' if lang == 'es' else 'Review'


def risk_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    probability = probability_value(row, 'model_probability')
    price = _first_float(row, ['decimal_price', 'average_price', 'best_price'])
    range_risk = _first_float(row, ['_price_range_risk', 'price_range_risk', 'price_range']) or 0.0
    research = safe_text(row.get('ledger_type')).lower().startswith('research') or safe_text(row.get('official_ev_pick')).lower() in {'false', '0', 'no'}
    if research:
        return 'Investigación' if lang == 'es' else 'Research'
    if range_risk > 0.50 or (price is not None and price >= 3.0) or (probability is not None and probability < 0.55):
        return 'Alto' if lang == 'es' else 'High'
    if range_risk > 0.25 or (price is not None and price >= 2.25) or (probability is not None and probability < 0.60):
        return 'Medio' if lang == 'es' else 'Medium'
    return 'Bajo' if lang == 'es' else 'Low'


def _add_unique(items: list[str], value: str, limit: int) -> None:
    clean = ' '.join(safe_text(value).split())
    if clean and clean.lower() not in {item.lower() for item in items} and len(items) < limit:
        items.append(clean)


def _split_reason(value: Any) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [' '.join(chunk.strip(' .').split()) for chunk in text.replace(' | ', '; ').split(';') if chunk.strip()]


def explain_pick(row: Mapping[str, Any], language: str = 'en', max_bullets: int = 4) -> list[str]:
    lang = normalize_language(language)
    prediction = safe_text(row.get('prediction')) or ('la selección' if lang == 'es' else 'the selection')
    probability = probability_value(row, 'model_probability')
    edge = model_edge(row)
    ev = expected_value(row)
    robust_ev = robust_expected_value(row)
    price = _first_float(row, ['decimal_price', 'average_price', 'best_price'])
    source = _source_text(row)
    proof_id = safe_text(row.get('proof_id'))
    decision = safe_text(row.get('agent_decision') or row.get('decision')).replace('_', ' ')
    bullets: list[str] = []

    if lang == 'es':
        if probability is not None:
            _add_unique(bullets, f'El modelo favorece {prediction} con probabilidad estimada de {_pct(probability)}.', max_bullets)
        if edge is not None:
            _add_unique(bullets, f'Ventaja estimada frente a la cuota: {edge * 100:.1f}%.', max_bullets) if edge > 0 else _add_unique(bullets, 'Señal sin ventaja de cuota clara; revisar antes de publicar como oficial.', max_bullets)
        if ev is not None:
            _add_unique(bullets, f'EV estimado por unidad: {ev * 100:.1f}%.', max_bullets)
        if robust_ev is not None and robust_ev > 0:
            _add_unique(bullets, f'EV conservador positivo: {robust_ev * 100:.1f}%.', max_bullets)
        if price is not None:
            _add_unique(bullets, f'Cuota registrada: {_decimal(price)}' + (f' vía {source}.' if source else '.'), max_bullets)
        if decision:
            _add_unique(bullets, f'Decisión interna: {decision}.', max_bullets)
        if proof_id:
            _add_unique(bullets, f'Pick bloqueado con {proof_id}.', max_bullets)
    else:
        if probability is not None:
            _add_unique(bullets, f'The model favors {prediction} with an estimated probability of {_pct(probability)}.', max_bullets)
        if edge is not None:
            _add_unique(bullets, f'Estimated edge versus the listed price: {edge * 100:.1f}%.', max_bullets) if edge > 0 else _add_unique(bullets, 'No clear price edge; review before publishing as official.', max_bullets)
        if ev is not None:
            _add_unique(bullets, f'Estimated EV per unit: {ev * 100:.1f}%.', max_bullets)
        if robust_ev is not None and robust_ev > 0:
            _add_unique(bullets, f'Conservative EV is positive: {robust_ev * 100:.1f}%.', max_bullets)
        if price is not None:
            _add_unique(bullets, f'Logged price: {_decimal(price)}' + (f' via {source}.' if source else '.'), max_bullets)
        if decision:
            _add_unique(bullets, f'Internal decision: {decision}.', max_bullets)
        if proof_id:
            _add_unique(bullets, f'Pick locked with {proof_id}.', max_bullets)

    for reason in _split_reason(row.get('public_reason')):
        _add_unique(bullets, reason + '.', max_bullets)
    if not bullets:
        _add_unique(bullets, 'Revisión de modelo disponible; falta contexto público.' if lang == 'es' else 'Model review available; public context is limited.', max_bullets)
    return bullets[:max_bullets]


def _sort_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    probability = pd.to_numeric(out.get('model_probability', pd.Series(index=out.index, dtype=float)), errors='coerce')
    probability = probability.where(probability <= 1.0, probability / 100.0)
    agent = pd.to_numeric(out.get('agent_score', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0) / 100.0
    scanner = pd.to_numeric(out.get('scanner_strength_score', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0) / 100.0
    edge = pd.to_numeric(out.get('model_edge', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0)
    out['_consumer_sort_score'] = probability.fillna(0.0) * 0.55 + agent * 0.18 + scanner * 0.12 + edge.clip(-0.20, 0.30) * 0.15
    return out.sort_values('_consumer_sort_score', ascending=False).drop(columns=['_consumer_sort_score'], errors='ignore')


def prepare_report_frame(frame: pd.DataFrame | list[dict[str, Any]], *, min_probability: float = 0.0, official_only: bool = False, pending_only: bool = False, max_rows: int = 12) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    out = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if out.empty:
        return pd.DataFrame()
    probabilities = pd.to_numeric(out.get('model_probability', pd.Series(index=out.index, dtype=float)), errors='coerce')
    probabilities = probabilities.where(probabilities <= 1.0, probabilities / 100.0)
    if min_probability > 0:
        out = out[probabilities.reindex(out.index).fillna(0.0) >= float(min_probability)].copy()
    if official_only and not out.empty:
        official = out.get('official_ev_pick', pd.Series(False, index=out.index)).astype(str).str.lower().isin({'true', '1', 'yes', 'y'})
        ready = out.get('official_lock_ready', pd.Series(False, index=out.index)).astype(str).str.lower().isin({'true', '1', 'yes', 'y'})
        ledger = out.get('ledger_type', pd.Series('', index=out.index)).astype(str).str.lower().str.contains('official')
        out = out[official | ready | ledger].copy()
    if pending_only and not out.empty:
        statuses = out.apply(lambda row: result_status(row.to_dict()), axis=1)
        out = out[statuses.isin({'pending', 'scheduled', 'live', ''})].copy()
    out = _sort_frame(out)
    return out.head(int(max_rows)).copy() if max_rows > 0 else out


def consumer_cards(frame: pd.DataFrame | list[dict[str, Any]], brand: BrandSettings | None = None, *, max_bullets: int = 4) -> pd.DataFrame:
    brand = (brand or BrandSettings()).normalized()
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for item in normalized.to_dict('records'):
        bullets = explain_pick(item, language=brand.language, max_bullets=max_bullets)
        card = {
            'workspace_id': brand.workspace_id,
            'brand_name': brand.brand_name,
            'sport': safe_text(item.get('sport')),
            'event': safe_text(item.get('event')),
            'market': market_label(item, brand.language),
            'prediction': safe_text(item.get('prediction')),
            'tendency': safe_text(item.get('prediction')),
            'decimal_price': _decimal(item.get('decimal_price')),
            'confidence': confidence_label(item, brand.language),
            'risk': risk_label(item, brand.language),
            'model_probability': probability_value(item, 'model_probability'),
            'proof_id': safe_text(item.get('proof_id')),
            'proof_status': safe_text(item.get('proof_status')),
            'result_status': result_status(item),
            'report_language': normalize_language(brand.language),
        }
        for index in range(max_bullets):
            card[f'bullet_{index + 1}'] = bullets[index] if index < len(bullets) else ''
        rows.append(card)
    return pd.DataFrame(rows)


def brand_payload(brand: BrandSettings) -> dict[str, str]:
    return {key: str(value) for key, value in asdict(brand.normalized()).items()}


def cards_to_json(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    payload = {
        'brand': brand_payload(brand),
        'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'cards': cards.fillna('').to_dict('records') if cards is not None and not cards.empty else [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def render_magazine_markdown(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    if cards is None or cards.empty:
        return lab['no_rows']
    title = brand.report_title or lab['report']
    lines = [f'# {title}', f'**{brand.brand_name}** — {brand.tagline}', f"**{lab['workspace']}:** {brand.workspace_id}", '']
    for _, row in cards.fillna('').iterrows():
        heading = f"{safe_text(row.get('sport'))}: {safe_text(row.get('event'))}" if safe_text(row.get('sport')) else safe_text(row.get('event'))
        lines += [f'## {heading}', f"**{lab['tendency']}:** {safe_text(row.get('tendency') or row.get('prediction'))}", f"**{lab['market']}:** {safe_text(row.get('market'))} | **{lab['odds']}:** {safe_text(row.get('decimal_price')) or '-'} | **{lab['confidence']}:** {safe_text(row.get('confidence'))} | **{lab['risk']}:** {safe_text(row.get('risk'))}"]
        for index in range(1, 5):
            bullet = safe_text(row.get(f'bullet_{index}'))
            if bullet:
                lines.append(f'- {bullet}')
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            lines.append(f"**{lab['proof']}:** {proof_id}")
        lines.append('')
    disclaimer = brand.disclaimer or lab['disclaimer']
    if disclaimer:
        lines += ['---', disclaimer]
    return '\n'.join(lines).strip() + '\n'


def _card_bullets_html(row: Mapping[str, Any]) -> str:
    items = [f'<li>{html.escape(safe_text(row.get(f"bullet_{index}")))}</li>' for index in range(1, 5) if safe_text(row.get(f'bullet_{index}'))]
    return '<ul>' + ''.join(items) + '</ul>' if items else ''


def render_consumer_cards_html(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    if cards is None or cards.empty:
        return f'<p>{html.escape(lab["no_rows"])}</p>'
    title = brand.report_title or lab['cards']
    parts = [
        '<style>.aba-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin:1rem 0}.aba-card{border:1px solid rgba(125,125,125,.35);border-radius:18px;padding:1rem;background:rgba(255,255,255,.045)}.aba-pill{display:inline-block;border:1px solid rgba(125,125,125,.45);border-radius:999px;padding:.18rem .55rem;margin:.1rem .2rem .1rem 0;font-size:.78rem}.aba-card .pick{font-size:1.15rem;font-weight:800;margin:.45rem 0}</style>',
        f'<h2>{html.escape(title)}</h2>',
        f'<p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p>',
        '<div class="aba-card-grid">',
    ]
    for _, row in cards.fillna('').iterrows():
        proof_id = safe_text(row.get('proof_id'))
        proof = f'<span class="aba-pill">{html.escape(lab["proof"])}: {html.escape(proof_id)}</span>' if proof_id else ''
        parts += [
            '<article class="aba-card">',
            f'<div>{html.escape(safe_text(row.get("sport")))} · {html.escape(safe_text(row.get("market")))}</div>',
            f'<h3>{html.escape(safe_text(row.get("event")))}</h3>',
            f'<div class="pick">{html.escape(lab["tendency"])}: {html.escape(safe_text(row.get("tendency") or row.get("prediction")))}</div>',
            f'<span class="aba-pill">{html.escape(lab["odds"])}: {html.escape(safe_text(row.get("decimal_price")) or "-")}</span>',
            f'<span class="aba-pill">{html.escape(lab["confidence"])}: {html.escape(safe_text(row.get("confidence")))}</span>',
            f'<span class="aba-pill">{html.escape(lab["risk"])}: {html.escape(safe_text(row.get("risk")))}</span>',
            proof, _card_bullets_html(row), '</article>',
        ]
    parts.append('</div>')
    disclaimer = brand.disclaimer or lab['disclaimer']
    if disclaimer:
        parts.append(f'<p>{html.escape(disclaimer)}</p>')
    return '\n'.join(parts)


def render_magazine_html(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    title = brand.report_title or lab['report']
    if cards is None or cards.empty:
        return f'<p>{html.escape(lab["no_rows"])}</p>'
    logo = f'<img src="{html.escape(brand.logo_url)}" alt="logo" style="max-height:54px">' if brand.logo_url else ''
    parts = ['<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:Georgia,serif;margin:0;background:#f3eadc;color:#1f1a14}.page{min-height:920px;padding:48px 58px;border-bottom:6px solid #1f1a14;page-break-after:always;box-sizing:border-box}.brand{display:flex;justify-content:space-between;align-items:center}.pill{display:inline-block;border:1px solid #1f1a14;border-radius:999px;padding:.28rem .7rem;margin:.15rem .25rem .15rem 0}.pick{font-size:2rem;font-weight:800;margin:1.8rem 0 .6rem 0}li{margin:.45rem 0;font-size:1.08rem;line-height:1.35}</style></head><body>', '<section class="page"><div class="brand"><div>', f'<h1>{html.escape(title)}</h1><p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p><p>{html.escape(lab["workspace"])}: {html.escape(brand.workspace_id)}</p></div>{logo}</div></section>']
    for _, row in cards.fillna('').iterrows():
        parts += ['<section class="page">', f'<h2>{html.escape(safe_text(row.get("event")))}</h2>', f'<span class="pill">{html.escape(lab["market"])}: {html.escape(safe_text(row.get("market")))}</span>', f'<span class="pill">{html.escape(lab["confidence"])}: {html.escape(safe_text(row.get("confidence")))}</span>', f'<span class="pill">{html.escape(lab["risk"])}: {html.escape(safe_text(row.get("risk")))}</span>', f'<div class="pick">{html.escape(lab["tendency"])}<br>{html.escape(safe_text(row.get("tendency") or row.get("prediction")))}</div>', f'<p><strong>{html.escape(lab["odds"])}:</strong> {html.escape(safe_text(row.get("decimal_price")) or "-")}</p>', _card_bullets_html(row)]
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            parts.append(f'<p><strong>{html.escape(lab["proof"])}:</strong> {html.escape(proof_id)}</p>')
        parts.append('</section>')
    parts.append(f'<section class="page"><h2>{html.escape(brand.brand_name)}</h2><p>{html.escape(brand.disclaimer or lab["disclaimer"])}</p></section></body></html>')
    return '\n'.join(parts)
