from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.magazine_book_export import (
    pick_full_page_filename,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
    sanitize_image_filename,
)
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
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

st.set_page_config(page_title='Report Studio', layout='wide')
LANG = render_app_sidebar('report_studio', language_key='report_studio_language', selector='radio')

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

normalized_preview = normalize_frame(raw)
all_sport_options = sport_options(normalized_preview)

with st.expander(t('profile'), expanded=True):
    profile_rows = list_profiles()
    profile_ids = sorted({safe_text(row.get('profile_id')) for row in profile_rows if safe_text(row.get('profile_id'))}) or ['default']
    p1, p2, p3 = st.columns([2, 1, 1])
    selected_profile = p1.selectbox(t('profile_id'), profile_ids, index=0)
    profile_id = p1.text_input(t('profile_key'), value=selected_profile)
    if p2.button(t('load_profile'), use_container_width=True):
        profile = load_profile(profile_id)
        st.session_state['report_studio_profile'] = asdict(profile)
        st.rerun()
    loaded = WhiteLabelProfile(**st.session_state.get('report_studio_profile', {})).normalized() if st.session_state.get('report_studio_profile') else load_profile(profile_id)

    b1, b2 = st.columns(2)
    brand_name = b1.text_input(t('brand_name'), value=loaded.brand_name)
    tagline = b2.text_input(t('tagline'), value=loaded.tagline)
    report_title = b1.text_input(t('report_title'), value=loaded.report_title)
    full_magazine_book_name = st.text_input(
        "Full magazine book name",
        "ABA Signal Pro — Full Pick Magazine"
    )
    logo_url = b2.text_input(t('logo_url'), value=loaded.logo_url)
    background_profile_upload = st.file_uploader(t('background_upload'), type=['png', 'jpg', 'jpeg'], key='report_studio_profile_background_upload')
    profile_background_bytes = background_profile_upload.getvalue() if background_profile_upload is not None else None
    if profile_background_bytes:
        st.success(t('background_ready'))
        st.image(profile_background_bytes, caption=t('background_preview'), width=260)
    mode_options = ['Consumer Magazine', 'Tipster Report', 'Client-Safe Summary', 'Analyst Proof Report'] if LANG == 'en' else ['Revista consumidor', 'Reporte tipster', 'Resumen cliente', 'Reporte técnico']
    default_mode_index = mode_options.index(loaded.preferred_report_mode) if loaded.preferred_report_mode in mode_options else 0
    report_mode = b1.selectbox(t('mode'), mode_options, index=default_mode_index)
    risk_values = ['Balanced', 'Conservative', 'Aggressive'] if LANG == 'en' else ['Balanceado', 'Conservador', 'Agresivo']
    risk_index = risk_values.index(loaded.risk_preference) if loaded.risk_preference in risk_values else 0
    risk_preference = b2.selectbox(t('risk'), risk_values, index=risk_index)
    visibility_values = ['private', 'public']
    loaded_visibility = safe_text((loaded.delivery_settings or {}).get('visibility')) or 'private'
    visibility = b2.selectbox(t('visibility'), visibility_values, index=visibility_values.index(loaded_visibility) if loaded_visibility in visibility_values else 0)
    preferred_sports = st.multiselect(t('sports'), all_sport_options, default=[sport for sport in list(loaded.preferred_sports or []) if sport in all_sport_options], key='report_profile_sports')
    disclaimer_default = 'Informational content only. Results are not guaranteed.' if LANG == 'en' else 'Contenido informativo. No garantiza resultados.'
    disclaimer = st.text_area(t('disclaimer'), value=loaded.disclaimer or disclaimer_default, height=80)
    technical = 'Analyst' in report_mode or 'técnico' in report_mode.lower()
    if p3.button(t('save_profile'), use_container_width=True):
        saved = save_profile(WhiteLabelProfile(
            profile_id=profile_id,
            workspace_id=workspace_id,
            brand_name=brand_name,
            logo_url=logo_url,
            tagline=tagline,
            language=LANG,
            report_title=report_title,
            disclaimer=disclaimer,
            preferred_report_mode=report_mode,
            preferred_sports=list(preferred_sports),
            risk_preference=risk_preference,
            show_technical_fields=technical,
            default_audience='analyst' if technical else 'consumer',
            delivery_settings={'save_latest_feed': True, 'visibility': visibility},
        ))
        st.session_state['report_studio_profile'] = asdict(saved)
        st.success(t('save_profile'))

max_rows = st.number_input(t('max_rows'), min_value=1, max_value=500, value=75, step=1)
mode_key = 'analyst' if technical else 'consumer'
brand = MagazineBrand(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace_id, language=LANG, logo_url=logo_url, disclaimer=disclaimer)
filters = ReportStudioFilters(selected_sports=tuple(preferred_sports), max_rows=int(max_rows), language=LANG, mode=mode_key, public_feed=visibility == 'public')
state = build_report_studio_state(raw, brand, filters=filters, source_note=source_note)
cards = state.cards
bundle = state.exports
legacy_feed = save_app_feed(cards, brand, mode=mode_key, public=visibility == 'public')
unified_feed = save_report_feed(cards, brand, mode=mode_key, public=visibility == 'public')
feed = {'unified_v2': unified_feed, 'legacy_v1': legacy_feed}
summary = report_studio_summary(state)

st.markdown(render_status_dashboard(cards, language=LANG), unsafe_allow_html=True)
st.caption(state.context_note)

safe_workspace = safe_workspace_name(workspace_id)
magazine_pdf_bytes = render_vintage_magazine_pdf(cards, brand)
report_background_bytes = profile_background_bytes
tabs = st.tabs([t('cards'), t('magazine'), t('copy'), t('audit'), t('proof'), t('exports'), t('images'), t('profile_json'), t('feed_json'), t('diagnostics')])
with tabs[0]:
    st.markdown(render_premium_card_deck(cards, language=LANG), unsafe_allow_html=True)
with tabs[1]:
    m1, m2 = st.columns(2)
    m1.download_button(t('magazine_pdf'), data=magazine_pdf_bytes, file_name=f'magazine_report_{safe_workspace}.pdf', mime='application/pdf', key='report_studio_magazine_pdf')
    magazine_tab_png = render_custom_background_summary_png(cards, brand, background_bytes=report_background_bytes) if report_background_bytes else render_magazine_summary_png(cards, brand)
    m2.download_button(t('magazine_png'), data=magazine_tab_png, file_name=f'magazine_report_{safe_workspace}.png', mime='image/png', key='report_studio_magazine_tab_png')
    if report_background_bytes:
        st.image(magazine_tab_png, caption=t('magazine_preview'), use_container_width=True)
    st.markdown(bundle.html, unsafe_allow_html=True)
with tabs[2]:
    st.text_area(t('copy_label'), value=bundle.whatsapp, height=420, key='report_studio_whatsapp_copy_text')
    st.download_button(t('copy_download'), data=bundle.whatsapp, file_name=f'whatsapp_copy_{safe_workspace}.txt', mime='text/plain', key='report_studio_copy_tab_download')
with tabs[3]:
    if not state.audit:
        st.info(t('no_audit'))
    for name, table in state.audit.items():
        st.subheader(name.replace('_', ' ').title())
        st.dataframe(table, use_container_width=True, hide_index=True)
with tabs[4]:
    proof_cols = [
        'event', 'sport', 'prediction', 'decimal_price', 'model_probability', 'market_probability', 'model_market_edge', 'expected_value_per_unit',
        'model_lean_label', 'price_value_label', 'official_status_label', 'result_status', 'learning_status', 'official_publish_ready', 'client_report_ready', 'learning_ready',
        'data_issue_reason', 'odds_verified', 'report_lane', 'report_lane_v2', 'publish_ready', 'tennis_blocked', 'proof_id', 'locked_at_utc', 'odds_source', 'bookmaker',
        'model_probability_source', 'sports_context_summary', 'profit_units',
    ]
    cols = [col for col in proof_cols if col in cards.columns]
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
with tabs[5]:
    st.download_button(t('pdf'), data=bundle.pdf_bytes, file_name=f'report_{safe_workspace}.pdf', mime='application/pdf', key='report_studio_export_pdf')
    st.download_button(t('magazine_pdf'), data=magazine_pdf_bytes, file_name=f'magazine_report_{safe_workspace}.pdf', mime='application/pdf', key='report_studio_export_magazine_pdf')
    st.download_button(t('html'), data=bundle.html, file_name=f'report_{safe_workspace}.html', mime='text/html', key='report_studio_export_html')
    st.download_button(t('md'), data=bundle.markdown, file_name=f'report_{safe_workspace}.md', mime='text/markdown', key='report_studio_export_md')
    st.download_button(t('copy_download'), data=bundle.whatsapp, file_name=f'whatsapp_copy_{safe_workspace}.txt', mime='text/plain', key='report_studio_export_whatsapp')
    st.download_button(t('json'), data=bundle.json_text, file_name=f'report_{safe_workspace}.json', mime='application/json', key='report_studio_export_json')
    st.download_button(t('csv'), data=bundle.csv_text, file_name=f'report_{safe_workspace}.csv', mime='text/csv', key='report_studio_export_csv')
with tabs[6]:
    st.caption(t('images_note'))
    st.info('Each game below downloads a full magazine-style page with game details, why the pick was selected, pro evidence, risk desk notes, chain-betting notes, and a final recommendation.')
    background_upload = st.file_uploader(t('background_upload'), type=['png', 'jpg', 'jpeg'], key='report_studio_image_background_upload')
    background_bytes = background_upload.getvalue() if background_upload is not None else report_background_bytes
    if background_bytes:
        st.success(t('background_ready'))
        st.image(background_bytes, caption=t('background_preview'), width=260)
    deck_png = render_custom_background_deck_png(cards, brand, background_bytes=background_bytes) if background_bytes else render_card_deck_png(cards, brand)
    magazine_png = render_custom_background_summary_png(cards, brand, background_bytes=background_bytes) if background_bytes else render_magazine_summary_png(cards, brand)
    if background_bytes:
        st.image(magazine_png, caption=t('magazine_preview'), use_container_width=True)
    c1, c2 = st.columns(2)
    c1.download_button(t('deck_png'), data=deck_png, file_name=f'card_deck_{safe_workspace}.png', mime='image/png', key='report_studio_image_deck_png')
    c2.download_button(t('magazine_png'), data=magazine_png, file_name=f'magazine_summary_{safe_workspace}.png', mime='image/png', key='report_studio_image_magazine_png')

    cards_as_rows = [row.to_dict() for _, row in cards.iterrows()]

    full_book_png = render_full_magazine_book_png(
        cards_as_rows,
        background_image=background_bytes,
        report_name=full_magazine_book_name,
    )

    full_book_pdf = render_full_magazine_book_pdf(
        cards_as_rows,
        background_image=background_bytes,
        report_name=full_magazine_book_name,
    )

    full_book_zip = render_full_magazine_zip(
        cards_as_rows,
        background_image=background_bytes,
        report_name=full_magazine_book_name,
    )

    st.download_button(
        "Download Full Magazine Book PNG",
        data=full_book_png,
        file_name=sanitize_image_filename(full_magazine_book_name, extension="png"),
        mime="image/png",
        key="report_studio_full_book_png",
    )

    st.download_button(
        "Download Full Magazine Book PDF",
        data=full_book_pdf,
        file_name=sanitize_image_filename(full_magazine_book_name, extension="pdf"),
        mime="application/pdf",
        key="report_studio_full_book_pdf",
    )

    st.download_button(
        "Download Full Magazine ZIP",
        data=full_book_zip,
        file_name=sanitize_image_filename(full_magazine_book_name, extension="zip"),
        mime="application/zip",
        key="report_studio_full_book_zip",
    )

    st.markdown('---')
    for idx, (_, row) in enumerate(cards.head(50).iterrows()):
        rowd = row.to_dict()
        event = safe_text(rowd.get('event')) or f'Game {idx + 1}'
        action = safe_text(rowd.get('consumer_action') or rowd.get('recommended_action')) or 'Full magazine analysis'
        full_page_png = render_full_pick_magazine_page_png(
            rowd,
            background_image=background_bytes,
            report_name=full_magazine_book_name,
            page_number=idx + 1,
            total_pages=len(cards_as_rows),
        )
        left, right = st.columns([3, 1])
        left.markdown(f'**{idx + 1}. {event}**  \n{action}')
        right.download_button(
            "Download Full Magazine Page",
            data=full_page_png,
            file_name=pick_full_page_filename(rowd, idx),
            mime="image/png",
            key=f"report_studio_image_full_page_{idx}",
        )
        compact_card = right.expander("Compact card image", expanded=False)
        compact_card_png = render_custom_background_card_png(rowd, brand, background_bytes=background_bytes, index=idx) if background_bytes else render_card_png(rowd, brand)
        compact_card.download_button(t('card_png'), data=compact_card_png, file_name=card_image_filename(rowd, workspace=safe_workspace, index=idx), mime='image/png', key=f'report_studio_image_card_{idx}')
with tabs[7]:
    st.json(asdict(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace_id, brand_name=brand_name, logo_url=logo_url, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_report_mode=report_mode, preferred_sports=preferred_sports, risk_preference=risk_preference, show_technical_fields=technical, default_audience='analyst' if technical else 'consumer')))
with tabs[8]:
    st.success(t('feed_saved'))
    st.json(feed)
with tabs[9]:
    st.json({
        'summary': summary,
        'diagnostics': asdict(state.diagnostics),
        'filters': asdict(state.filters),
        'source': source_note,
        'unified_feed_paths': unified_feed.get('saved_paths', {}),
        'legacy_feed_paths': legacy_feed.get('saved_paths', {}),
    })
