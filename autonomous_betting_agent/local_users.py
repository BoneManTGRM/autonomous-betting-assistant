from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
LOCAL_USERS_DIR = BASE_DATA_DIR / 'local_users'
DEFAULT_USER_ID = 'owner'
DEFAULT_DISPLAY_NAME = 'Owner'


@dataclass(frozen=True)
class LocalUserProfile:
    user_id: str
    display_name: str
    created_at_utc: str
    notes: str = ''


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sanitize_user_id(value: str) -> str:
    text = str(value or '').strip().lower()
    text = re.sub(r'[^a-z0-9_-]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_-')
    return text[:64] or DEFAULT_USER_ID


def user_dir(user_id: str) -> Path:
    return LOCAL_USERS_DIR / sanitize_user_id(user_id)


def profile_path(user_id: str) -> Path:
    return user_dir(user_id) / 'profile.json'


def user_data_path(user_id: str, filename: str) -> Path:
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]+', '_', str(filename or 'data.csv')).strip('._') or 'data.csv'
    return user_dir(user_id) / safe_name


def ensure_user_dirs(user_id: str) -> Path:
    path = user_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / 'exports').mkdir(exist_ok=True)
    (path / 'ledgers').mkdir(exist_ok=True)
    (path / 'uploads').mkdir(exist_ok=True)
    return path


def create_or_update_user(display_name: str, *, user_id: str | None = None, notes: str = '') -> LocalUserProfile:
    clean_display = str(display_name or DEFAULT_DISPLAY_NAME).strip() or DEFAULT_DISPLAY_NAME
    clean_id = sanitize_user_id(user_id or clean_display)
    ensure_user_dirs(clean_id)
    path = profile_path(clean_id)
    created_at = utc_now_iso()
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding='utf-8'))
            created_at = str(existing.get('created_at_utc') or created_at)
        except Exception:
            pass
    profile = LocalUserProfile(user_id=clean_id, display_name=clean_display, created_at_utc=created_at, notes=str(notes or ''))
    path.write_text(json.dumps(asdict(profile), indent=2, sort_keys=True), encoding='utf-8')
    return profile


def load_user_profile(user_id: str) -> LocalUserProfile:
    clean_id = sanitize_user_id(user_id)
    path = profile_path(clean_id)
    if not path.exists():
        return create_or_update_user(DEFAULT_DISPLAY_NAME if clean_id == DEFAULT_USER_ID else clean_id.replace('_', ' ').title(), user_id=clean_id)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return create_or_update_user(clean_id.replace('_', ' ').title(), user_id=clean_id)
    return LocalUserProfile(
        user_id=sanitize_user_id(str(data.get('user_id') or clean_id)),
        display_name=str(data.get('display_name') or clean_id.replace('_', ' ').title()),
        created_at_utc=str(data.get('created_at_utc') or utc_now_iso()),
        notes=str(data.get('notes') or ''),
    )


def list_user_profiles() -> list[LocalUserProfile]:
    LOCAL_USERS_DIR.mkdir(parents=True, exist_ok=True)
    if not profile_path(DEFAULT_USER_ID).exists():
        create_or_update_user(DEFAULT_DISPLAY_NAME, user_id=DEFAULT_USER_ID)
    profiles: list[LocalUserProfile] = []
    for path in sorted(LOCAL_USERS_DIR.glob('*/profile.json')):
        profiles.append(load_user_profile(path.parent.name))
    if not profiles:
        profiles.append(create_or_update_user(DEFAULT_DISPLAY_NAME, user_id=DEFAULT_USER_ID))
    return sorted(profiles, key=lambda profile: profile.display_name.lower())


def current_user_from_session(session_state: Any) -> LocalUserProfile:
    user_id = sanitize_user_id(str(session_state.get('local_user_id') or DEFAULT_USER_ID))
    profile = load_user_profile(user_id)
    session_state['local_user_id'] = profile.user_id
    session_state['local_user_display_name'] = profile.display_name
    return profile


def install_streamlit_local_user_selector() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if st.session_state.get('_local_user_selector_rendered'):
        return
    st.session_state['_local_user_selector_rendered'] = True
    profiles = list_user_profiles()
    ids = [profile.user_id for profile in profiles]
    labels = {profile.user_id: f'{profile.display_name} ({profile.user_id})' for profile in profiles}
    current = sanitize_user_id(str(st.session_state.get('local_user_id') or DEFAULT_USER_ID))
    index = ids.index(current) if current in ids else 0
    with st.sidebar:
        st.markdown('---')
        st.caption('Local profile')
        selected = st.selectbox('Active user', ids, index=index, format_func=lambda value: labels.get(value, value), key='local_user_selector')
        profile = load_user_profile(selected)
        st.session_state['local_user_id'] = profile.user_id
        st.session_state['local_user_display_name'] = profile.display_name
        st.caption(f'Data folder: data/local_users/{profile.user_id}')


def add_user_columns(frame: Any, user_id: str, display_name: str | None = None) -> Any:
    try:
        import pandas as pd
    except Exception:
        return frame
    if not isinstance(frame, pd.DataFrame):
        return frame
    out = frame.copy()
    out['local_user_id'] = sanitize_user_id(user_id)
    out['local_user_display_name'] = str(display_name or user_id)
    return out
