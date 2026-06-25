from __future__ import annotations

import html
from typing import Any

import pandas as pd

from .report_learning_layer_compat import apply_learning_layer_compat as apply_learning_layer
from .report_product_layer import event_text, pick_text, safe_text, sport_text, value_text


def _bool_count(cards: pd.DataFrame, column: str) -> int:
    if cards is None or cards.empty or column not in cards.columns:
        return 0
    return int(cards[column].astype(bool).sum())


def average_model_label(cards: pd.DataFrame) -> str:
    values = pd.to_numeric(cards.get('model_probability', pd.Series(dtype=float)), errors='coerce').dropna()
    return 'N/A' if values.empty else f'{float(values.mean()) * 100:.1f}%'


def _lane_count(cards: pd.DataFrame, values: set[str]) -> int:
    if cards is None or cards.empty or 'report_lane_v2' not in cards.columns:
        return 0
    return int(cards['report_lane_v2'].isin(values).sum())


def _data_issue_mask(cards: pd.DataFrame) -> pd.Series:
    if cards is None or cards.empty or 'data_issue_reason' not in cards.columns:
        return pd.Series(False, index=cards.index if cards is not None else None)
    return cards['data_issue_reason'].map(lambda x: bool(safe_text(x)))


def render_status_dashboard(cards: pd.DataFrame, *, language: str = 'en') -> str:
    cards = apply_learning_layer(cards)
    es = language == 'es'
    total = int(len(cards)) if cards is not None else 0
    official = _bool_count(cards, 'official_publish_ready')
    report_ready = _bool_count(cards, 'client_report_ready')
    learning_ready = _bool_count(cards, 'learning_ready')
    issue_mask = _data_issue_mask(cards)
    price_watch = _lane_count(cards, {'strong_prediction_price_watch', 'learning_candidate', 'research_play'})
    graded_winners = int((cards['report_lane_v2'].eq('graded_winner') & ~issue_mask).sum()) if cards is not None and not cards.empty and 'report_lane_v2' in cards.columns else 0
    data_issues = int(issue_mask.sum()) if cards is not None and not cards.empty else 0
    research = max(report_ready - official, 0)
    title = 'Sistema de aprendizaje activo' if es else 'Learning-aware report gate'
    if official == 0 and report_ready > 0:
        body = f'{report_ready} tarjetas están listas para reporte e investigación. 0 jugadas oficiales +EV pasaron el filtro estricto.' if es else f'{report_ready} cards are report-ready for research. 0 official +EV plays passed the strict proof gate.'
    else:
        body = 'El reporte separa resultado, valor de precio, estado oficial y aprendizaje.' if es else 'The report separates result grading, price value, official status, and learning readiness.'
    metric_items: list[tuple[str, Any, str]] = [
        ('Tarjetas totales' if es else 'Total Cards', total, 'Filas seleccionadas' if es else 'Selected rows'),
        ('Oficial +EV' if es else 'Official +EV Plays', official, 'Filtro estricto de prueba' if es else 'Strict proof gate'),
        ('Seguimiento precio' if es else 'Price Watch', price_watch, 'Lean del modelo / seguimiento' if es else 'Model lean / track'),
        ('Investigación' if es else 'Research / Learning', research, 'Listas para reporte' if es else 'Report-ready'),
        ('Ganadoras grad.' if es else 'Graded Winners', graded_winners, 'Resultados finales' if es else 'Final results'),
        ('Problemas de datos' if es else 'Data Issues', data_issues, 'Filas bloqueadas' if es else 'Blocked rows'),
        ('Publicables oficiales' if es else 'Official Publish-Ready', official, 'Prueba pagada' if es else 'Paid proof'),
        ('Listas aprendizaje' if es else 'Learning Ready', learning_ready, 'Filas de calibración' if es else 'Calibration rows'),
        ('Prob. media' if es else 'Avg Model', average_model_label(cards), 'Promedio del modelo' if es else 'Model average'),
    ]
    boxes = []
    for label, value, sub in metric_items:
        boxes.append('<div class="aba-metric-card">' f'<div class="aba-metric-label">{html.escape(str(label))}</div>' f'<div class="aba-metric-value">{html.escape(str(value))}</div>' f'<div class="aba-metric-sub">{html.escape(str(sub))}</div>' '</div>')
    badges = ('Resultado separado', 'Valor separado', 'Prueba estricta') if es else ('Result separated', 'Value separated', 'Strict proof preserved')
    return f'''
<style>
.aba-summary-hero{{border:1px solid rgba(255,255,255,.14);border-radius:26px;padding:1.15rem;margin:1rem 0;background:linear-gradient(135deg,rgba(67,160,255,.18),rgba(255,255,255,.035) 48%,rgba(120,255,190,.10));box-shadow:0 18px 50px rgba(0,0,0,.18)}}
.aba-summary-title{{font-size:1.2rem;font-weight:900;margin-bottom:.25rem}}
.aba-summary-body{{opacity:.82;max-width:820px;line-height:1.45}}
.aba-badges{{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.8rem}}
.aba-badge{{border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:.28rem .62rem;font-weight:800;font-size:.78rem;background:rgba(255,255,255,.06)}}
.aba-metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin-top:1rem}}
.aba-metric-card{{border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:.85rem;background:rgba(0,0,0,.18)}}
.aba-metric-label{{font-size:.76rem;opacity:.7;text-transform:uppercase;letter-spacing:.04em;font-weight:800}}
.aba-metric-value{{font-size:1.9rem;font-weight:950;line-height:1.1;margin-top:.2rem}}
.aba-metric-sub{{font-size:.78rem;opacity:.62;margin-top:.25rem}}
</style>
<div class="aba-summary-hero"><div class="aba-summary-title">{html.escape(title)}</div><div class="aba-summary-body">{html.escape(body)}</div><div class="aba-badges"><span class="aba-badge">{html.escape(badges[0])}</span><span class="aba-badge">{html.escape(badges[1])}</span><span class="aba-badge">{html.escape(badges[2])}</span></div><div class="aba-metric-grid">{''.join(boxes)}</div></div>
'''


def _section_rows(cards: pd.DataFrame, section: str) -> pd.DataFrame:
    if cards.empty or 'report_lane_v2' not in cards.columns:
        return pd.DataFrame()
    issue_mask = _data_issue_mask(cards)
    if section == 'official':
        return cards[cards['official_publish_ready'].astype(bool)].copy()
    if section == 'price_watch':
        return cards[cards['report_lane_v2'].isin({'strong_prediction_price_watch', 'learning_candidate', 'research_play'})].copy()
    if section == 'graded':
        return cards[cards['report_lane_v2'].isin({'graded_winner', 'graded_loss'}) & ~issue_mask].copy()
    if section == 'blocked':
        return cards[issue_mask].copy()
    return pd.DataFrame()


def render_premium_card_deck(cards: pd.DataFrame, *, language: str = 'en') -> str:
    es = language == 'es'
    cards = apply_learning_layer(cards)
    if cards is None or cards.empty:
        return '<p>No hay tarjetas disponibles.</p>' if es else '<p>No cards available.</p>'
    sections = [
        ('official', 'Oficial +EV' if es else 'Official +EV'),
        ('price_watch', 'Seguimiento de precio / investigación' if es else 'Price Watch / Research'),
        ('graded', 'Resultados gradados' if es else 'Graded Results'),
        ('blocked', 'Bloqueadas por datos' if es else 'Data Blocked'),
    ]
    empty = 'No hay tarjetas en esta sección.' if es else 'No cards in this section.'
    css = '''<style>.aba-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(295px,1fr));gap:1rem}.aba-mini-card{border:1px solid rgba(255,255,255,.14);border-radius:22px;padding:1rem;background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.025));box-shadow:0 10px 32px rgba(0,0,0,.14)}.aba-mini-k{font-size:.74rem;opacity:.65;text-transform:uppercase;font-weight:900;letter-spacing:.05em}.aba-mini-v{font-weight:900}.aba-mini-row{display:grid;grid-template-columns:repeat(2,1fr);gap:.45rem}.aba-mini-box{border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:.55rem;background:rgba(0,0,0,.12)}.aba-section-title{margin-top:1.25rem}.aba-lane-empty{border:1px dashed rgba(255,255,255,.16);border-radius:18px;padding:.85rem;opacity:.72}.aba-card-status{display:inline-block;border-radius:999px;padding:.22rem .55rem;font-size:.74rem;font-weight:850;background:rgba(90,200,250,.14);border:1px solid rgba(90,200,250,.25);margin:.25rem 0 .6rem 0}.aba-market-note{opacity:.82}</style>'''
    parts = [css]
    for key, title_text in sections:
        section = _section_rows(cards, key)
        parts.append(f'<h2 class="aba-section-title">{html.escape(title_text)} <span style="opacity:.55;font-size:.85rem">({len(section)})</span></h2>')
        if section.empty:
            parts.append(f'<div class="aba-lane-empty">{html.escape(empty)}</div>')
            continue
        parts.append('<div class="aba-card-grid">')
        for _, row in section.iterrows():
            rowd = row.to_dict()
            title = event_text(rowd.get('public_event') or rowd.get('event') or 'Matchup', language)
            sport = sport_text(rowd.get('public_sport') or rowd.get('sport') or 'Sport', language)
            pick = pick_text(rowd.get('public_pick') or rowd.get('prediction'), language)
            action = value_text(rowd.get('consumer_action') or rowd.get('recommended_action'), language)
            market = value_text(rowd.get('market_read'), language)
            why = value_text(rowd.get('why_it_matters'), language)
            model_lean = value_text(rowd.get('model_lean_label'), language)
            price_value = value_text(rowd.get('price_value_label'), language)
            official = value_text(rowd.get('official_status_label'), language)
            result = value_text(rowd.get('result_status'), language)
            learning = value_text(rowd.get('learning_status'), language)
            parts.extend([
                '<article class="aba-mini-card">',
                f'<div class="aba-mini-k">{html.escape(sport)}</div>',
                f'<h3>{html.escape(title)}</h3>',
                f'<div class="aba-card-status">{html.escape(action)}</div>',
                f'<p><b>{html.escape("Selección" if es else "Pick")}:</b> {html.escape(pick)}</p>',
                '<div class="aba-mini-row">',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Modelo" if es else "Model lean")}</div><div class="aba-mini-v">{html.escape(model_lean)}</div></div>',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Valor" if es else "Price value")}</div><div class="aba-mini-v">{html.escape(price_value)}</div></div>',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Estado oficial" if es else "Official status")}</div><div class="aba-mini-v">{html.escape(official)}</div></div>',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Resultado" if es else "Final result")}</div><div class="aba-mini-v">{html.escape(result)}</div></div>',
                '</div>',
                f'<p><b>{html.escape("Aprendizaje" if es else "Learning status")}:</b> {html.escape(learning)}</p>',
                f'<p class="aba-market-note"><b>{html.escape("Mercado" if es else "Market read")}:</b> {html.escape(market)}</p>',
                f'<p><b>{html.escape("Por qué importa" if es else "Why it matters")}:</b> {html.escape(why)}</p>',
                '</article>',
            ])
        parts.append('</div>')
    return '\n'.join(parts)
