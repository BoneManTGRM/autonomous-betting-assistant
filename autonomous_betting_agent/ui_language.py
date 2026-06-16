from __future__ import annotations

import streamlit as st

SESSION_KEY = 'app_language'
OPTIONS = ['English', 'Español']
PAGE_LANGUAGE_KEYS = [
    'language_settings_language',
    'tool_command_center_language',
    'command_center_language',
    'game_intelligence_language',
    'deployment_health_language',
    'scanner_pro_language',
    'pro_predictor_language',
    'what_are_the_odds_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'auto_result_grading_language',
    'daily_workflow_language',
    'learning_memory_language',
    'learn_memory_language',
    'monthly_license_readiness_language',
    'buyer_demo_mode_language',
    'daily_operator_checklist_language',
    'private_beta_sales_dashboard_language',
    'reset_data_language',
]
ALL_LANGUAGE_KEYS = [SESSION_KEY, 'global_language', *PAGE_LANGUAGE_KEYS]


def _code(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    if text.startswith('en') or 'english' in text:
        return 'en'
    return ''


def label(value: object = None) -> str:
    return 'Español' if _code(value) == 'es' else 'English'


def query_param_language() -> str | None:
    try:
        raw = st.query_params.get('lang')
    except Exception:
        return None
    if not raw:
        return None
    code = _code(raw)
    return label(raw) if code else None


def _safe_set_session(key: str, value: str) -> None:
    try:
        st.session_state[key] = value
    except Exception:
        pass


def set_global_language(selected: object) -> str:
    normalized = label(selected)
    for key in ALL_LANGUAGE_KEYS:
        _safe_set_session(key, normalized)
    try:
        st.query_params['lang'] = 'es' if normalized == 'Español' else 'en'
    except Exception:
        pass
    return normalized


def _session_language() -> str | None:
    values = [_code(st.session_state.get(key)) for key in ALL_LANGUAGE_KEYS]
    if 'es' in values:
        return 'Español'
    if 'en' in values:
        return 'English'
    return None


def current_language_label(default: object = 'Español') -> str:
    session = _session_language()
    if session:
        return session
    query = query_param_language()
    if query == 'Español':
        return query
    return label(default)


def render_language_selector(*, key: str) -> str:
    current = current_language_label()

    def _sync_language() -> None:
        set_global_language(st.session_state.get(key) or current)

    selected = st.sidebar.selectbox('Language / Idioma', OPTIONS, index=OPTIONS.index(current), key=key, on_change=_sync_language)
    set_global_language(selected)
    return _code(selected) or 'es'
