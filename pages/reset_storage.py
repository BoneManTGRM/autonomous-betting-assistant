from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.pick_hold_store import HELD_KEYS, normalize_workspace_id, save_held_rows, store_snapshot
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Reset Storage', layout='wide')
LANG = render_app_sidebar('reset_storage', language_key='storage_diagnostics_language')

TEXT = {
    'en': {
        'title': 'Reset Storage',
        'caption': 'Start the active test workspace from zero before rebuilding a clean ledger.',
        'workspace_id': 'Workspace ID',
        'warning': 'Use this only when you want to start this test workspace over.',
        'confirm': 'I understand. Reset this workspace.',
        'button': 'Reset current workspace now',
        'done': 'Workspace reset. Refresh the app, upload one clean file, and create the ledger once.',
        'snapshot': 'Storage snapshot',
    },
    'es': {
        'title': 'Reiniciar almacenamiento',
        'caption': 'Empieza el espacio de trabajo activo desde cero antes de reconstruir un ledger limpio.',
        'workspace_id': 'ID del espacio de trabajo',
        'warning': 'Usa esto solo cuando quieras empezar este espacio de trabajo desde cero.',
        'confirm': 'Entiendo. Reiniciar este espacio de trabajo.',
        'button': 'Reiniciar este espacio de trabajo ahora',
        'done': 'Espacio de trabajo reiniciado. Actualiza la app, sube un archivo limpio y crea el ledger una sola vez.',
        'snapshot': 'Estado de almacenamiento',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def reset_workspace(workspace_id: str) -> dict[str, int | str]:
    workspace = normalize_workspace_id(workspace_id)
    changed = 0
    for key in sorted(HELD_KEYS):
        save_held_rows(key, [], workspace)
        save_held_rows(key, [], 'test_01')
        st.session_state[key] = []
        st.session_state[f'latest_{key}'] = []
        changed += 1
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    return {'workspace_id': workspace, 'keys_reset': changed}


st.title(t('title'))
st.caption(t('caption'))

workspace_input = st.text_input(t('workspace_id'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

st.warning(t('warning'))
confirm = st.checkbox(t('confirm'))

if st.button(t('button'), type='primary', disabled=not confirm, use_container_width=True):
    result = reset_workspace(workspace_id)
    st.success(t('done'))
    st.json(result)

st.subheader(t('snapshot'))
st.dataframe(store_snapshot(workspace_id), use_container_width=True, hide_index=True)
