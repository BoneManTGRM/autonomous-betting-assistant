from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any


def _clean_label(value: Any) -> str:
    return ' '.join(str(value or '').strip().lower().replace('_', ' ').replace('-', ' ').split())


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '')
    if not text or text.lower() in {'none', 'null', 'nan', 'unknown', 'missing', 'n/a', 'na', 'pending'}:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    if price >= 100:
        return round(1.0 + price / 100.0, 6)
    if price <= -100:
        return round(1.0 + 100.0 / abs(price), 6)
    if price > 1.0:
        return round(price, 6)
    return None


def _parse_outcome(value: Any) -> int | None:
    text = str(value or '').strip().lower()
    if text in {'1', 'true', 'yes', 'y', 'win', 'won', 'w', 'correct', 'hit', 'ganada', 'gano', 'victoria'}:
        return 1
    if text in {'0', 'false', 'no', 'n', 'loss', 'lost', 'l', 'incorrect', 'miss', 'perdida', 'perdio', 'derrota'}:
        return 0
    try:
        number = int(float(text))
    except ValueError:
        return None
    return number if number in {0, 1} else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def roi_summary_from_memory_bank() -> dict[str, Any]:
    path = _repo_root() / 'data' / 'learning_memory_bank.json'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'graded_rows': 0, 'priced_rows': 0, 'wins': 0, 'losses': 0, 'profit_units': 0.0, 'roi': None}
    rows = payload.get('compact_rows', []) if isinstance(payload, dict) else []
    graded_rows = 0
    priced_rows = 0
    wins = 0
    losses = 0
    profit = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        outcome = _parse_outcome(row.get('outcome'))
        if outcome is None:
            continue
        graded_rows += 1
        price = _parse_price(row.get('best_price') or row.get('decimal_price') or row.get('price') or row.get('odds'))
        if price is None:
            continue
        priced_rows += 1
        if outcome == 1:
            wins += 1
            profit += price - 1.0
        else:
            losses += 1
            profit -= 1.0
    roi = None if priced_rows == 0 else profit / priced_rows
    return {
        'graded_rows': graded_rows,
        'priced_rows': priced_rows,
        'wins': wins,
        'losses': losses,
        'profit_units': round(profit, 4),
        'roi': roi,
    }


def _called_from_dashboard() -> bool:
    try:
        names = {'pages/pro_predictor.py', 'pages/learn_memory.py'}
        for frame in inspect.stack():
            filename = str(frame.filename).replace('\\', '/')
            if any(filename.endswith(name) for name in names):
                return True
    except Exception:
        pass
    return False


def _language() -> str:
    try:
        import streamlit as st
        value = str(st.session_state.get('global_language') or st.session_state.get('pro_predictor_language') or '').lower()
        return 'es' if value.startswith('es') or 'español' in value or 'espanol' in value else 'en'
    except Exception:
        return 'en'


def _format_signed_percent(value: float | None) -> str:
    if value is None:
        return 'N/A'
    sign = '+' if value > 0 else ''
    return f'{sign}{value * 100:.1f}%'


def _format_units(value: float) -> str:
    sign = '+' if value > 0 else ''
    return f'{sign}{value:.2f}u'


def _render_roi_card(container: Any) -> None:
    summary = roi_summary_from_memory_bank()
    roi = summary['roi']
    profit = float(summary['profit_units'])
    priced_rows = int(summary['priced_rows'])
    graded_rows = int(summary['graded_rows'])
    if roi is None:
        color = '#9ca3af'
    elif roi > 0:
        color = '#22c55e'
    elif roi < 0:
        color = '#ef4444'
    else:
        color = '#9ca3af'
    lang = _language()
    if lang == 'es':
        title = 'ROI apuesta plana'
        profit_label = 'Profit'
        rows_label = 'Filas con cuota'
    else:
        title = 'Flat-stake ROI'
        profit_label = 'Profit'
        rows_label = 'Rows with odds'
    detail = f'{profit_label}: {_format_units(profit)} · {rows_label}: {priced_rows}/{graded_rows}'
    container.markdown(
        f"""
        <div style="margin-top:0.35rem;padding-top:0.55rem;border-top:1px solid rgba(148,163,184,0.25);">
            <div style="font-size:0.88rem;color:rgba(148,163,184,0.95);line-height:1.25;">{title}</div>
            <div style="font-size:2.15rem;font-weight:500;line-height:1.15;color:{color};">{_format_signed_percent(roi)}</div>
            <div style="font-size:0.78rem;color:rgba(148,163,184,0.85);line-height:1.25;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def install_roi_metric_patch() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_roi_metric_patch_installed_v1', False):
        return
    st._aba_roi_metric_patch_installed_v1 = True
    original_metric = DeltaGenerator.metric

    def patched_metric(self: Any, label: Any, value: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_metric(self, label, value, *args, **kwargs)
        try:
            key = _clean_label(label).replace('é', 'e')
            if _called_from_dashboard() and key in {'brier after', 'brier despues'}:
                _render_roi_card(self)
        except Exception:
            pass
        return result

    DeltaGenerator.metric = patched_metric
