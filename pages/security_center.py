from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.security import (
    SecurityCheck,
    all_checks_passed,
    checks_to_frame,
    file_sha256,
    secure_csv_download,
    validate_dataframe,
    validate_upload_bytes,
    validate_upload_name,
)

st.set_page_config(page_title='Security Center', layout='wide')
st.title('Security Center')
st.caption('Defensive checks for uploads, CSV downloads, secret leakage, and local-file safety. This is not an antivirus engine and does not make the app unhackable.')

st.subheader('Upload security scan')
upload = st.file_uploader('Upload a CSV/text file to scan', type=['csv', 'txt'])

if upload is None:
    st.info('Upload a CSV or text file to run security checks.')
    st.stop()

raw = upload.getvalue()
name_checks = validate_upload_name(upload.name)
byte_checks = validate_upload_bytes(raw)

st.metric('SHA-256', file_sha256(raw)[:16] + '...')
st.metric('File size bytes', len(raw))

checks = list(name_checks) + list(byte_checks)
frame: pd.DataFrame | None = None
try:
    frame = pd.read_csv(BytesIO(raw))
    checks.extend(validate_dataframe(frame))
except Exception as exc:
    checks.append(SecurityCheck('csv_parse', False, 'high', f'Could not parse CSV: {exc}'))

results = checks_to_frame(checks)
st.dataframe(results, use_container_width=True, hide_index=True)

if all_checks_passed(checks):
    st.success('High-severity security checks passed.')
else:
    st.error('One or more high-severity security checks failed. Do not trust this file until reviewed.')

if frame is not None:
    st.subheader('Preview')
    st.dataframe(frame.head(50), use_container_width=True, hide_index=True)

    st.subheader('Safer CSV download')
    st.caption('The safer download redacts secret-like strings and escapes spreadsheet formulas that can execute when opened in Excel/Sheets.')
    safe_csv = secure_csv_download(frame, redact_secrets=True)
    st.download_button('Download safer CSV', safe_csv, file_name=f'safe_{upload.name}', mime='text/csv')

with st.expander('What this protects against', expanded=False):
    st.write(
        {
            'blocked_by_design': 'The page accepts CSV/text only and rejects executable/script extensions.',
            'csv_formula_injection': 'Cells beginning with =, +, -, @, tab, or newline are escaped before download.',
            'secret_leakage': 'API-key/token/password-like strings are detected and redacted in safer exports.',
            'path_traversal': 'Security helpers sanitize filenames and include safe path joining for local files.',
            'limits': 'This does not replace OS antivirus, endpoint protection, HTTPS hosting, real auth, or dependency vulnerability scanning.',
        }
    )
