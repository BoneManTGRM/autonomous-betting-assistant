from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

from autonomous_betting_agent.pick_hold_store import github_store_enabled, normalize_workspace_id, store_snapshot
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Storage Diagnostics', layout='wide')
render_app_sidebar('storage_diagnostics')

GITHUB_API = 'https://api.github.com'


def _secret_value(*names: str) -> str:
    for name in names:
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


def _github_settings() -> tuple[str, str, str]:
    token = _secret_value('GITHUB_PROOF_TOKEN', 'PROOF_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')
    repo = _secret_value('GITHUB_PROOF_REPO', 'PROOF_GITHUB_REPO', 'GITHUB_REPOSITORY') or 'BoneManTGRM/autonomous-betting-agent'
    branch = _secret_value('GITHUB_PROOF_BRANCH', 'PROOF_GITHUB_BRANCH') or 'main'
    return token, repo, branch


def github_write_probe(workspace_id: str) -> dict[str, Any]:
    token, repo, branch = _github_settings()
    if not token:
        return {'ok': False, 'status_code': None, 'message': 'No GitHub token found in Streamlit secrets.'}
    path = f'.aba_state/diagnostic_probe_{normalize_workspace_id(workspace_id)}.json'
    url = f'{GITHUB_API}/repos/{repo}/contents/{path}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    sha = ''
    try:
        existing = requests.get(url, headers=headers, params={'ref': branch}, timeout=15)
        if existing.status_code == 200:
            sha = str(existing.json().get('sha', ''))
    except Exception:
        sha = ''
    payload = {
        'workspace_id': normalize_workspace_id(workspace_id),
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'ABA Signal Pro durable storage probe',
    }
    body: dict[str, Any] = {
        'message': f'Durable storage probe for {normalize_workspace_id(workspace_id)}',
        'branch': branch,
        'content': base64.b64encode((json.dumps(payload, indent=2) + '\n').encode('utf-8')).decode('ascii'),
    }
    if sha:
        body['sha'] = sha
    try:
        response = requests.put(url, headers=headers, json=body, timeout=20)
        if response.status_code in {200, 201}:
            return {'ok': True, 'status_code': response.status_code, 'message': f'GitHub durable write succeeded: {path}'}
        text = response.text[:500]
        return {'ok': False, 'status_code': response.status_code, 'message': text}
    except Exception as exc:
        return {'ok': False, 'status_code': None, 'message': str(exc)}


st.title('Storage Diagnostics')
st.caption('Session, local disk, and optional GitHub durable recovery status for the active workspace.')

workspace_input = st.text_input('Workspace ID', value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

snapshot = store_snapshot(workspace_id)

token, repo, branch = _github_settings()
st.metric('Active workspace', workspace_id)
st.metric('GitHub durable store', 'enabled' if github_store_enabled() else 'not configured')
st.caption(f'GitHub repo target: {repo} / branch: {branch}')
st.metric('Total loaded rows', int(snapshot['loaded_rows'].sum()) if not snapshot.empty else 0)
st.metric('Total disk rows', int(snapshot['disk_rows'].sum()) if not snapshot.empty else 0)
st.metric('Total backup rows', int(snapshot['backup_rows'].sum()) if not snapshot.empty else 0)
st.metric('Total GitHub rows', int(snapshot['github_rows'].sum()) if not snapshot.empty and 'github_rows' in snapshot.columns else 0)

if st.button('Run GitHub durable write test', type='primary', use_container_width=True):
    result = github_write_probe(workspace_id)
    if result.get('ok'):
        st.success(result.get('message'))
    else:
        st.error(f"GitHub write failed: {result.get('status_code')} / {result.get('message')}")

st.dataframe(snapshot, use_container_width=True, hide_index=True)

if not github_store_enabled():
    st.warning('GitHub durable storage is not configured. Add GITHUB_PROOF_TOKEN to Streamlit secrets to survive reboot/redeploy.')
elif not snapshot.empty and snapshot.get('github_rows', 0).sum() == 0:
    st.warning('GitHub durable storage is enabled, but no durable proof rows were found yet. Create a new lock in Odds Lock Pro, then return here.')
elif not snapshot.empty and snapshot.get('github_rows', 0).sum() > 0:
    st.success('GitHub durable storage has rows for this workspace.')

if not snapshot.empty and snapshot['loaded_rows'].sum() == 0 and snapshot['disk_rows'].sum() == 0 and snapshot['backup_rows'].sum() == 0 and snapshot.get('github_rows', 0).sum() == 0:
    st.warning('No saved rows found for this workspace.')
elif not snapshot.empty:
    st.success('Storage is readable for this workspace.')
