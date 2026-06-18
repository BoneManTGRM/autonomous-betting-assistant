from __future__ import annotations

import builtins
import os
from typing import Any


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _running_in_ci() -> bool:
    return os.getenv('CI', '').lower() == 'true' or os.getenv('GITHUB_ACTIONS', '').lower() == 'true'


def _is_orphan_workflow_heading(body: Any) -> bool:
    text = str(body or '').strip().lower()
    cleaned = text.replace('#', '').replace('*', '').strip()
    return cleaned in {'workflow', 'flujo de trabajo'}


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        values = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in values and 'Español' in values and ('language' in text or 'idioma' in text)


def _render_page_links(st: Any) -> None:
    pages = [
        ('Signal Board', 'pages/signal_board.py'),
        ('Pro Predictor', 'pages/pro_predictor.py'),
        ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
        ('What Are the Odds', 'pages/what_are_the_odds.py'),
        ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
        ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
        ('Learning Memory', 'pages/learn_memory.py'),
        ('Reset Lock File', 'pages/reset_lock_file.py'),
    ]
    try:
        with st.sidebar:
            st.markdown('---')
            st.markdown('### Tools')
            for label, path in pages:
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.caption(label)
    except Exception:
        pass


def _install_sidebar_page_links() -> None:
    if _running_in_ci():
        return
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_aba_sidebar_page_links_patch_v1', False):
        return
    original_radio = st.sidebar.radio
    original_selectbox = st.sidebar.selectbox

    def radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = original_radio(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_page_links(st)
        return value

    def selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = original_selectbox(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_page_links(st)
        return value

    st.sidebar.radio = radio
    st.sidebar.selectbox = selectbox
    st._aba_sidebar_page_links_patch_v1 = True


def _install_streamlit_content_guards() -> None:
    if _running_in_ci():
        return
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator

        real_st_subheader = st.subheader
        real_sidebar_subheader = st.sidebar.subheader
        real_dg_subheader = DeltaGenerator.subheader
        real_st_header = st.header
        real_sidebar_header = st.sidebar.header
        real_dg_header = DeltaGenerator.header
        real_st_markdown = st.markdown
        real_sidebar_markdown = st.sidebar.markdown
        real_dg_markdown = DeltaGenerator.markdown
        real_st_write = st.write
        real_sidebar_write = st.sidebar.write
        real_dg_write = DeltaGenerator.write

        def safe_subheader(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.empty()
            return real_st_subheader(body, *args, **kwargs)

        def safe_sidebar_subheader(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.sidebar.empty()
            return real_sidebar_subheader(body, *args, **kwargs)

        def safe_dg_subheader(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return self.empty()
            return real_dg_subheader(self, body, *args, **kwargs)

        def safe_header(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.empty()
            return real_st_header(body, *args, **kwargs)

        def safe_sidebar_header(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.sidebar.empty()
            return real_sidebar_header(body, *args, **kwargs)

        def safe_dg_header(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return self.empty()
            return real_dg_header(self, body, *args, **kwargs)

        def safe_markdown(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.empty()
            return real_st_markdown(body, *args, **kwargs)

        def safe_sidebar_markdown(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return st.sidebar.empty()
            return real_sidebar_markdown(body, *args, **kwargs)

        def safe_dg_markdown(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_orphan_workflow_heading(body):
                return self.empty()
            return real_dg_markdown(self, body, *args, **kwargs)

        def safe_write(*args: Any, **kwargs: Any) -> Any:
            if len(args) == 1 and _is_orphan_workflow_heading(args[0]):
                return st.empty()
            return real_st_write(*args, **kwargs)

        def safe_sidebar_write(*args: Any, **kwargs: Any) -> Any:
            if len(args) == 1 and _is_orphan_workflow_heading(args[0]):
                return st.sidebar.empty()
            return real_sidebar_write(*args, **kwargs)

        def safe_dg_write(self: Any, *args: Any, **kwargs: Any) -> Any:
            if len(args) == 1 and _is_orphan_workflow_heading(args[0]):
                return self.empty()
            return real_dg_write(self, *args, **kwargs)

        st.subheader = safe_subheader
        st.sidebar.subheader = safe_sidebar_subheader
        DeltaGenerator.subheader = safe_dg_subheader
        st.header = safe_header
        st.sidebar.header = safe_sidebar_header
        DeltaGenerator.header = safe_dg_header
        st.markdown = safe_markdown
        st.sidebar.markdown = safe_sidebar_markdown
        DeltaGenerator.markdown = safe_dg_markdown
        st.write = safe_write
        st.sidebar.write = safe_sidebar_write
        DeltaGenerator.write = safe_dg_write
    except Exception:
        pass


def _install_all_runtime_hooks() -> None:
    if _running_in_ci():
        return
    _install_sidebar_page_links()
    _install_streamlit_content_guards()
    try:
        from autonomous_betting_agent.pro_predictor_defaults_patch import install_pro_predictor_defaults_patch
        install_pro_predictor_defaults_patch()
    except Exception:
        pass
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


_install_all_runtime_hooks()
