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


def _is_orphan_workflow_heading(body: Any) -> bool:
    text = str(body or '').strip().lower()
    cleaned = text.replace('#', '').replace('*', '').strip()
    return cleaned in {'workflow', 'flujo de trabajo'}


def _install_all_runtime_hooks() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
        from autonomous_betting_agent import sidebar_tools
        sidebar_tools.install_sidebar_tools()

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

        def render_pages_only(streamlit_module: Any, language: object = 'English') -> None:
            if sidebar_tools._already_rendered(streamlit_module, sidebar_tools.PAGES_RENDERED_KEY):
                return
            lang = sidebar_tools.normal_language(language)
            with streamlit_module.sidebar:
                streamlit_module.divider()
                streamlit_module.markdown('### Herramientas' if lang == 'Español' else '### Tools')
                for en, es, path in sidebar_tools.PAGES:
                    label = es if lang == 'Español' else en
                    try:
                        streamlit_module.page_link(path, label=label)
                    except Exception:
                        streamlit_module.caption(label)
                streamlit_module.divider()

        sidebar_tools.render_curated_sidebar = render_pages_only
        sidebar_tools.render_curated_sidebar(st, st.session_state.get('global_language', st.session_state.get('pro_predictor_language', 'English')))
    except Exception:
        pass
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
