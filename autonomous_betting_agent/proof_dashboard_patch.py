from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from .proof_roi_tools import curve, enhance, group, summarize


def _on_page() -> bool:
    try:
        for f in inspect.stack():
            name = str(f.filename).replace('\\', '/')
            if name.endswith('pages/odds_lock_pro.py') or name.endswith('pages/public_proof_dashboard.py'):
                return True
    except Exception:
        pass
    return False


def _ledger() -> pd.DataFrame:
    try:
        for f in inspect.stack():
            for key in ('filtered_ledger', 'active_locked', 'ledger'):
                value = f.frame.f_locals.get(key)
                if isinstance(value, pd.DataFrame) and not value.empty:
                    return value
    except Exception:
        pass
    return pd.DataFrame()


def _lang() -> str:
    try:
        import streamlit as st
        value = str(st.session_state.get('global_language') or '').lower()
        return 'es' if value.startswith('es') else 'en'
    except Exception:
        return 'en'


def _pct(v: Any) -> str:
    try:
        n = float(v)
    except Exception:
        return 'N/A'
    return f"{'+' if n > 0 else ''}{n * 100:.1f}%"


def _color(v: Any) -> str:
    try:
        n = float(v)
    except Exception:
        return '#9ca3af'
    return '#22c55e' if n > 0 else '#ef4444' if n < 0 else '#9ca3af'


def _card(box: Any, title: str, value: Any, detail: str) -> None:
    box.markdown(f'<div style="border-top:1px solid rgba(148,163,184,.25);padding-top:.55rem"><div style="font-size:.84rem;color:#94a3b8">{title}</div><div style="font-size:1.65rem;font-weight:650;color:{_color(value)}">{_pct(value)}</div><div style="font-size:.74rem;color:#94a3b8">{detail}</div></div>', unsafe_allow_html=True)


def _extras() -> None:
    if not _on_page():
        return
    frame = _ledger()
    if frame.empty:
        return
    try:
        import streamlit as st
        stats = summarize(frame)
        resolved = int(stats.get('resolved_picks', 0) or 0)
        missing = int(stats.get('resolved_missing_odds', 0) or 0)
        if missing:
            st.warning(f'ROI excludes {missing} of {resolved} resolved rows because locked odds are missing.' if _lang() == 'en' else f'ROI excluye {missing} de {resolved} filas resueltas porque faltan cuotas bloqueadas.')
        a, b, c = st.columns(3)
        _card(a, 'Flat ROI' if _lang() == 'en' else 'ROI flat', stats.get('flat_roi'), f"Profit {stats.get('flat_profit_units')}u · {stats.get('resolved_with_odds')}/{resolved}")
        _card(b, 'Stake ROI' if _lang() == 'en' else 'ROI stake', stats.get('roi'), f"Profit {stats.get('profit_units')}u")
        c.metric('Voids / no-grade' if _lang() == 'en' else 'Voids / sin calificar', stats.get('pushes', 0))
        data = curve(frame)
        if not data.empty:
            st.subheader('Cumulative profit' if _lang() == 'en' else 'Profit acumulado')
            st.line_chart(data[[x for x in ['cumulative_profit_units', 'flat_cumulative_profit_units'] if x in data.columns]])
        for col in ('sport', 'confidence_tier', 'bookmaker', 'odds_range_bucket', 'model_edge_bucket'):
            table = group(frame, col)
            if not table.empty:
                with st.expander(col.replace('_', ' ').title(), expanded=col in {'sport', 'confidence_tier'}):
                    st.dataframe(table, use_container_width=True, hide_index=True)
    except Exception:
        pass


def install_proof_dashboard_patch() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
        from . import odds_lock_tools as tools
    except Exception:
        return
    if getattr(st, '_proof_roi_patch_v1', False):
        return
    st._proof_roi_patch_v1 = True
    old_json = st.json
    old_dg_json = DeltaGenerator.json

    def patched_json(body: Any, *args: Any, **kwargs: Any) -> Any:
        out = old_json(body, *args, **kwargs)
        if isinstance(body, dict) and 'locked_picks' in body:
            _extras()
        return out

    def patched_dg_json(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
        out = old_dg_json(self, body, *args, **kwargs)
        if isinstance(body, dict) and 'locked_picks' in body:
            _extras()
        return out

    st.json = patched_json
    DeltaGenerator.json = patched_dg_json
    tools.update_profit_columns = enhance
    tools.summarize_locked_picks = summarize
    tools.performance_by_group = group
    tools.cumulative_profit_frame = curve
