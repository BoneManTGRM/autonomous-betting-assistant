from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_background_image_service import render_custom_background_card_png, render_custom_background_deck_png, render_custom_background_summary_png
from autonomous_betting_agent.report_feed_service import save_report_feed
from autonomous_betting_agent.report_image_export_service import card_image_filename, render_card_deck_png, render_card_png, render_magazine_summary_png
from autonomous_betting_agent.report_magazine_pdf_service import render_vintage_magazine_pdf
from autonomous_betting_agent.report_product_layer import MagazineBrand, safe_text
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import render_upload_css
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

st.set_page_config(page_title='Report Studio', layout='wide')
LANG = render_app_sidebar('report_studio', language_key='report_studio_language', selector='radio')
render_upload_css(st, LANG)

TEXT = {
    'en': {
        'title': 'Report Studio',
        'caption': 'Unified premium reports, official +EV proof, learning audit, exports, profiles, and app feed.',
        'input': 'Input rows', 'workspace': 'Client / Workspace ID', 'use_saved': 'Use saved workspace rows', 'upload': 'Upload CSV rows', 'source': 'Source',
        'empty': 'No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.',
        'profile': 'White-label profile', 'profile_id': 'Profile ID', 'profile_key': 'Profile key', 'load_profile': 'Load profile', 'save_profile': 'Save profile',
        'brand_name': 'Brand / tipster name', 'tagline': 'Tagline', 'report_title': 'Report title', 'logo_url': 'Logo URL', 'disclaimer': 'Disclaimer',
        'mode': 'Report mode', 'risk': 'Risk preference', 'sports': 'Sport / League Filter', 'max_rows': 'Max rows', 'visibility': 'Feed visibility',
        'cards': 'Premium Cards', 'magazine': 'Magazine Report', 'copy': 'WhatsApp / Telegram', 'audit': 'Learning Audit', 'proof': 'Analyst Proof', 'exports': 'Exports', 'images': 'Images', 'profile_json': 'Profile JSON', 'feed_json': 'App Feed', 'diagnostics': 'Diagnostics',
        'pdf': 'Download PDF', 'magazine_pdf': 'Download Magazine PDF', 'html': 'Download HTML', 'md': 'Download Markdown', 'json': 'Download JSON', 'csv': 'Download CSV', 'copy_download': 'Download WhatsApp copy',
        'deck_png': 'Download full card deck PNG', 'magazine_png': 'Download Magazine PNG', 'card_png': 'Download Card Image', 'images_note': 'Server-rendered PNG images for saving and sharing.',
        'background_upload': 'Optional background image for PNG exports', 'background_ready': 'Custom background enabled for Magazine PNG, Card Image, and full Card Deck downloads.',
        'background_preview': 'Uploaded background preview', 'magazine_preview': 'Generated Magazine PNG preview',
        'feed_saved': 'Unified and legacy app feeds saved.', 'copy_label': 'Short copy', 'no_audit': 'No graded calibration data available yet.',
    },
    'es': {
        'title': 'Estudio de Reportes',
        'caption': 'Reportes premium, prueba oficial +EV, auditoría de aprendizaje, exportaciones, perfiles y feed de app.',
        'input': 'Filas de entrada', 'workspace': 'ID de cliente / workspace', 'use_saved': 'Usar filas guardadas', 'upload': 'Subir CSV', 'source': 'Fuente',
        'empty': 'No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.',
        'profile': 'Perfil white-label', 'profile_id': 'ID del perfil', 'profile_key': 'Clave del perfil', 'load_profile': 'Cargar perfil', 'save_profile': 'Guardar perfil',
        'brand_name': 'Marca / tipster', 'tagline': 'Lema', 'report_title': 'Título del reporte', 'logo_url': 'URL del logo', 'disclaimer': 'Aviso legal',
        'mode': 'Modo de reporte', 'risk': 'Preferencia de riesgo', 'sports': 'Filtro deporte / liga', 'max_rows': 'Máximo de filas', 'visibility': 'Visibilidad del feed',
        'cards': 'Tarjetas premium', 'magazine': 'Reporte revista', 'copy': 'WhatsApp / Telegram', 'audit': 'Auditoría de aprendizaje', 'proof': 'Prueba técnica', 'exports': 'Exportaciones', 'images': 'Imágenes', 'profile_json': 'JSON del perfil', 'feed_json': 'Feed de app', 'diagnostics': 'Diagnóstico',
        'pdf': 'Descargar PDF', 'magazine_pdf': 'Descargar PDF revista', 'html': 'Descargar HTML', 'md': 'Descargar Markdown', 'json': 'Descargar JSON', 'csv': 'Descargar CSV', 'copy_download': 'Descargar copy WhatsApp',
        'deck_png': 'Descargar PNG de tarjetas', 'magazine_png': 'Descargar PNG de revista', 'card_png': 'Descargar imagen de tarjeta', 'images_note': 'Imágenes PNG generadas por servidor para guardar y compartir.',
        'background_upload': 'Imagen de fondo opcional para exportaciones PNG', 'background_ready': 'Fondo personalizado activo para PNG de revista, imágenes individuales y deck completo.',
        'background_preview': 'Vista previa del fondo subido', 'magazine_preview': 'Vista previa del PNG de revista generado',
        'feed_saved': 'Feed unificado y feed legado guardados.', 'copy_label': 'Copy corto', 'no_audit': 'Aún no hay datos gradados para calibración.',
    },
}

HANDOFF_KEYS = (
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
    'pro_predictor_high_confidence_rows',
    'pro_predictor_latest_rows',
    'what_are_the_odds_latest_rows',
    'ara_latest_predictions',
)


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, key)


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return 'persistent_proof_ledger', persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return f'session:{key}', pd.DataFrame(rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    return (f'saved:{key}', pd.DataFrame(rows)) if rows else ('', pd.DataFrame())


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame['source_file'] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f'{upload.name}: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


def sport_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or 'sport' not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame['sport'].tolist() if safe_text(value)})


def safe_workspace_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in str(value or 'report'))


st.title(t('title'))
st.caption(t('caption'))
profile_background_bytes = None

with st.expander(t('input'), expanded=True):
    workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    use_saved = st.checkbox(t('use_saved'), value=True)
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ('', pd.DataFrame())
    upload_source, upload_rows = read_uploaded_rows()
    raw = pd.concat([frame for frame in (saved_rows, upload_rows) if frame is not None and not frame.empty], ignore_index=True, sort=False) if (not saved_rows.empty or not upload_rows.empty) else pd.DataFrame()
    source_note = ', '.join([name for name in (saved_source, upload_source) if name]) or 'none'
    st.caption(f"{t('source')}: {source_note}")

if raw.empty:
    st.warning(t('empty'))
    st.stop()

# The rest of the original Report Studio page continues below in the existing file.
