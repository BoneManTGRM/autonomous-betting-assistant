from __future__ import annotations

import html
from typing import Any

import pandas as pd

from .report_product_layer import grouped_report, safe_text


def _count_ready(cards: pd.DataFrame) -> int:
    if cards is None or cards.empty:
        return 0
    return int(cards.get('publish_ready', pd.Series(dtype=bool)).astype(bool).sum())


def average_model_label(cards: pd.DataFrame) -> str:
    values = pd.to_numeric(cards.get('model_probability', pd.Series(dtype=float)), errors='coerce').dropna()
    return 'N/A' if values.empty else f'{float(values.mean()) * 100:.1f}%'


def render_status_dashboard(cards: pd.DataFrame, *, language: str = 'en') -> str:
    es = language == 'es'
    groups = grouped_report(cards)
    total = int(len(cards)) if cards is not None else 0
    ready = _count_ready(cards)
    approved = int(len(groups.get('best_plays', pd.DataFrame())))
    watch = int(len(groups.get('watchlist', pd.DataFrame())))
    research = int(len(groups.get('no_play', pd.DataFrame())))
    flags = max(total - ready, 0)
    title = 'Filtro estricto activo' if es else 'Strict review gate active'
    if approved == 0 and watch == 0 and research > 0:
        body = 'No hay jugadas aprobadas en este grupo filtrado. Las filas siguen disponibles como investigación para revisión técnica.' if es else 'No approved cards were found in this filtered set. The rows are still visible as research for analyst review.'
    else:
        body = 'Las tarjetas se separan en aprobadas, seguimiento e investigación para mantener limpio el reporte final.' if es else 'Cards are separated into approved, watchlist, and research so the final report stays clean.'
    metric_items: list[tuple[str, Any, str]] = [
        ('Tarjetas totales' if es else 'Total Cards', total, 'Selected rows'),
        ('Aprobadas' if es else 'Approved', approved, 'Ready lane'),
        ('Seguimiento' if es else 'Watchlist', watch, 'Monitor lane'),
        ('Investigación' if es else 'Research', research, 'Not approved'),
        ('Prob. media' if es else 'Avg Model', average_model_label(cards), 'Model average'),
        ('Publicables' if es else 'Publish-ready', ready, 'Final ready'),
        ('Alertas' if es else 'Review flags', flags, 'Needs review'),
    ]
    boxes = []
    for label, value, sub in metric_items:
        boxes.append(
            '<div class="aba-metric-card">'
            f'<div class="aba-metric-label">{html.escape(str(label))}</div>'
            f'<div class="aba-metric-value">{html.escape(str(value))}</div>'
            f'<div class="aba-metric-sub">{html.escape(str(sub))}</div>'
            '</div>'
        )
    badges = ('Falla cerrado', 'Investigación visible', 'Prueba preservada') if es else ('Fail-closed', 'Research visible', 'Proof preserved')
    return f'''
<style>
.aba-summary-hero{{border:1px solid rgba(255,255,255,.14);border-radius:26px;padding:1.15rem;margin:1rem 0;background:linear-gradient(135deg,rgba(239,83,80,.18),rgba(255,255,255,.035) 48%,rgba(90,200,250,.10));box-shadow:0 18px 50px rgba(0,0,0,.18)}}
.aba-summary-title{{font-size:1.2rem;font-weight:900;margin-bottom:.25rem}}
.aba-summary-body{{opacity:.78;max-width:780px;line-height:1.45}}
.aba-badges{{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.8rem}}
.aba-badge{{border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:.28rem .62rem;font-weight:800;font-size:.78rem;background:rgba(255,255,255,.06)}}
.aba-metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin-top:1rem}}
.aba-metric-card{{border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:.85rem;background:rgba(0,0,0,.18)}}
.aba-metric-label{{font-size:.76rem;opacity:.7;text-transform:uppercase;letter-spacing:.04em;font-weight:800}}
.aba-metric-value{{font-size:2rem;font-weight:950;line-height:1.1;margin-top:.2rem}}
.aba-metric-sub{{font-size:.78rem;opacity:.62;margin-top:.25rem}}
</style>
<div class="aba-summary-hero"><div class="aba-summary-title">{html.escape(title)}</div><div class="aba-summary-body">{html.escape(body)}</div><div class="aba-badges"><span class="aba-badge">{html.escape(badges[0])}</span><span class="aba-badge">{html.escape(badges[1])}</span><span class="aba-badge">{html.escape(badges[2])}</span></div><div class="aba-metric-grid">{''.join(boxes)}</div></div>
'''


def render_premium_card_deck(cards: pd.DataFrame, *, language: str = 'en') -> str:
    es = language == 'es'
    if cards is None or cards.empty:
        return '<p>No hay tarjetas disponibles.</p>' if es else '<p>No cards available.</p>'
    groups = grouped_report(cards)
    labels = {'best_plays': 'Jugadas aprobadas' if es else 'Approved Plays', 'watchlist': 'Seguimiento' if es else 'Watchlist', 'no_play': 'Investigación / no aprobado' if es else 'Research / Not Approved'}
    empty = 'No hay tarjetas en esta sección.' if es else 'No cards in this section.'
    css = '''<style>.aba-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(295px,1fr));gap:1rem}.aba-mini-card{border:1px solid rgba(255,255,255,.14);border-radius:22px;padding:1rem;background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.025));box-shadow:0 10px 32px rgba(0,0,0,.14)}.aba-mini-k{font-size:.74rem;opacity:.65;text-transform:uppercase;font-weight:900;letter-spacing:.05em}.aba-mini-v{font-weight:900}.aba-mini-row{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem}.aba-mini-box{border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:.55rem;background:rgba(0,0,0,.12)}.aba-section-title{margin-top:1.25rem}.aba-lane-empty{border:1px dashed rgba(255,255,255,.16);border-radius:18px;padding:.85rem;opacity:.72}.aba-card-status{display:inline-block;border-radius:999px;padding:.22rem .55rem;font-size:.74rem;font-weight:850;background:rgba(239,83,80,.14);border:1px solid rgba(239,83,80,.25);margin:.25rem 0 .6rem 0}.aba-market-note{opacity:.82}</style>'''
    parts = [css]
    for key in ('best_plays', 'watchlist', 'no_play'):
        section = groups.get(key, pd.DataFrame())
        parts.append(f'<h2 class="aba-section-title">{html.escape(labels[key])} <span style="opacity:.55;font-size:.85rem">({len(section)})</span></h2>')
        if section.empty:
            parts.append(f'<div class="aba-lane-empty">{html.escape(empty)}</div>')
            continue
        parts.append('<div class="aba-card-grid">')
        for _, row in section.iterrows():
            rowd = row.to_dict()
            title = safe_text(rowd.get('event')) or 'Matchup'
            sport = safe_text(rowd.get('public_sport')) or safe_text(rowd.get('sport')) or 'Sport'
            pick = safe_text(rowd.get('public_pick')) or safe_text(rowd.get('prediction'))
            action = safe_text(rowd.get('recommended_action'))
            confidence = safe_text(rowd.get('confidence_tier'))
            risk = safe_text(rowd.get('risk_tier'))
            market = safe_text(rowd.get('market_read'))
            preview = safe_text(rowd.get('game_preview'))
            parts.extend([
                '<article class="aba-mini-card">',
                f'<div class="aba-mini-k">{html.escape(sport)}</div>',
                f'<h3>{html.escape(title)}</h3>',
                f'<div class="aba-card-status">{html.escape(labels[key])}</div>',
                f'<p><b>{html.escape("Selección" if es else "Pick")}:</b> {html.escape(pick)}</p>',
                '<div class="aba-mini-row">',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Acción" if es else "Action")}</div><div class="aba-mini-v">{html.escape(action)}</div></div>',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Confianza" if es else "Confidence")}</div><div class="aba-mini-v">{html.escape(confidence)}</div></div>',
                f'<div class="aba-mini-box"><div class="aba-mini-k">{html.escape("Riesgo" if es else "Risk")}</div><div class="aba-mini-v">{html.escape(risk)}</div></div>',
                '</div>',
                f'<p class="aba-market-note"><b>{html.escape("Mercado" if es else "Market read")}:</b> {html.escape(market)}</p>',
                f'<p>{html.escape(preview)}</p>',
                '</article>',
            ])
        parts.append('</div>')
    return '\n'.join(parts)
