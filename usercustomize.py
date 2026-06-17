from __future__ import annotations

from typing import Any

try:
    from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
    install_odds_breakdown_normalizer()
except Exception:
    pass

try:
    from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
    install_proof_dashboard_patch()
except Exception:
    pass

try:
    from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
    install_streamlit_local_user_selector()
except Exception:
    pass

LANGUAGE_KEYS = (
    'global_language', 'app_language', 'pro_predictor_language', 'ultra80_profit_mode_language',
    'simulation_lab_language', 'what_are_the_odds_language', 'odds_lock_pro_language',
    'public_proof_dashboard_language', 'reset_lock_file_language', 'learn_memory_language',
    'learning_memory_language', 'threshold_optimizer_language',
)

MOBILE_SIDEBAR_CSS = """
<style>
@media (max-width: 900px) {
    section[data-testid="stSidebar"] {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        transform: translateX(-120vw) !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }
    .block-container {
        padding-left: .85rem !important;
        padding-right: .85rem !important;
        max-width: 100vw !important;
    }
    div[data-testid="stToolbar"] {
        right: .25rem !important;
    }
}
</style>
"""


def _normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'Español'
    return 'English'


def _sync_language(st: Any, value: object) -> str:
    normalized = _normal_language(value)
    for key in LANGUAGE_KEYS:
        try:
            st.session_state[key] = normalized
        except Exception:
            pass
    return normalized


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    label_text = str(label or '').lower()
    return ('language' in label_text or 'idioma' in label_text) and 'English' in opts and 'Español' in opts


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return (
        value.replace('Scanner Pro', 'Pro Predictor')
        .replace('scanner strength', 'signal strength')
        .replace('Scanner strength', 'Signal strength')
        .replace('escáner', 'señal')
        .replace('Escáner', 'Señal')
    )


def _install_mobile_sidebar_fix() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_mobile_sidebar_fix_v3', False):
        return
    st._aba_mobile_sidebar_fix_v3 = True

    real_set_page_config = st.set_page_config
    real_st_radio = st.radio
    real_dg_radio = getattr(DeltaGenerator, 'radio', None)
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_caption = st.caption
    real_markdown = st.markdown
    real_info = st.info
    real_write = st.write
    real_dg_caption = DeltaGenerator.caption
    real_dg_markdown = DeltaGenerator.markdown
    real_dg_info = DeltaGenerator.info
    real_dg_write = DeltaGenerator.write

    def inject_css() -> None:
        try:
            real_markdown(MOBILE_SIDEBAR_CSS, unsafe_allow_html=True)
        except Exception:
            pass

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        kwargs['initial_sidebar_state'] = 'collapsed'
        result = real_set_page_config(*args, **kwargs)
        inject_css()
        return result

    def st_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_st_radio(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _sync_language(st, value)
        return value

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options):
            kwargs.setdefault('horizontal', True)
            value = real_st_radio(label, options, *args, **kwargs)
            return _sync_language(st, value)
        if real_dg_radio is not None:
            return real_dg_radio(self, label, options, *args, **kwargs)
        return real_st_radio(label, options, *args, **kwargs)

    def st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_st_selectbox(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _sync_language(st, value)
        return value

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options):
            value = real_st_selectbox(label, options, *args, **kwargs)
            return _sync_language(st, value)
        return real_dg_selectbox(self, label, options, *args, **kwargs)

    st.set_page_config = patched_set_page_config
    st.radio = st_radio
    st.selectbox = st_selectbox
    DeltaGenerator.selectbox = dg_selectbox
    if real_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    st.caption = lambda body, *a, **k: real_caption(_clean_text(body), *a, **k)
    st.markdown = lambda body, *a, **k: real_markdown(_clean_text(body), *a, **k)
    st.info = lambda body, *a, **k: real_info(_clean_text(body), *a, **k)
    st.write = lambda *a, **k: real_write(*[_clean_text(x) for x in a], **k)
    DeltaGenerator.caption = lambda self, body, *a, **k: real_dg_caption(self, _clean_text(body), *a, **k)
    DeltaGenerator.markdown = lambda self, body, *a, **k: real_dg_markdown(self, _clean_text(body), *a, **k)
    DeltaGenerator.info = lambda self, body, *a, **k: real_dg_info(self, _clean_text(body), *a, **k)
    DeltaGenerator.write = lambda self, *a, **k: real_dg_write(self, *[_clean_text(x) for x in a], **k)


_install_mobile_sidebar_fix()
