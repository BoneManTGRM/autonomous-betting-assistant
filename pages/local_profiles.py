from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import (
    add_user_columns,
    create_or_update_user,
    current_user_from_session,
    list_user_profiles,
    user_data_path,
)

st.set_page_config(page_title='Local Profiles', layout='wide')
st.title('Local Profiles')
st.caption('Use multiple local users without auth, passwords, Stripe, or a cloud server. Each profile gets its own local data folder.')

profile = current_user_from_session(st.session_state)
st.success(f'Active local user: {profile.display_name} ({profile.user_id})')

st.subheader('Create or update local user')
with st.form('create_local_user_form'):
    display_name = st.text_input('Display name', value='')
    user_id = st.text_input('Optional user ID', value='', help='Leave blank to create one from the display name.')
    notes = st.text_area('Notes', value='')
    submitted = st.form_submit_button('Save local user')
    if submitted:
        if not display_name.strip():
            st.error('Display name is required.')
        else:
            saved = create_or_update_user(display_name, user_id=user_id or None, notes=notes)
            st.session_state['local_user_id'] = saved.user_id
            st.session_state['local_user_display_name'] = saved.display_name
            st.success(f'Saved and selected {saved.display_name} ({saved.user_id}).')
            st.rerun()

st.subheader('Existing local users')
profiles = list_user_profiles()
profile_rows = [
    {
        'display_name': item.display_name,
        'user_id': item.user_id,
        'created_at_utc': item.created_at_utc,
        'notes': item.notes,
        'data_folder': f'data/local_users/{item.user_id}',
    }
    for item in profiles
]
st.dataframe(pd.DataFrame(profile_rows), use_container_width=True, hide_index=True)

selected_id = st.selectbox('Switch active local user', [item.user_id for item in profiles], format_func=lambda value: next((p.display_name for p in profiles if p.user_id == value), value))
if st.button('Use this profile', type='primary'):
    selected = next(item for item in profiles if item.user_id == selected_id)
    st.session_state['local_user_id'] = selected.user_id
    st.session_state['local_user_display_name'] = selected.display_name
    st.success(f'Active profile changed to {selected.display_name}.')
    st.rerun()

st.subheader('Tag an uploaded CSV with the active user')
st.caption('This does not upload to any cloud service. It only adds local_user_id and local_user_display_name columns and lets you download the tagged file.')
uploaded = st.file_uploader('Upload CSV to tag', type=['csv'])
if uploaded is not None:
    frame = pd.read_csv(uploaded)
    tagged = add_user_columns(frame, profile.user_id, profile.display_name)
    st.dataframe(tagged.head(50), use_container_width=True, hide_index=True)
    st.download_button(
        'Download user-tagged CSV',
        tagged.to_csv(index=False),
        file_name=f'{profile.user_id}_tagged_{uploaded.name}',
        mime='text/csv',
    )

with st.expander('How local multi-user mode works', expanded=False):
    st.write(
        {
            'no_auth': 'This is profile selection, not secure authentication.',
            'no_cloud': 'Data is stored under data/local_users/<user_id> inside the app filesystem.',
            'best_use': 'Good for demos, local testing, family/team profiles, or a pre-SaaS prototype.',
            'future_upgrade': 'Later this can map to real auth users and a database without changing the profile IDs.',
        }
    )
