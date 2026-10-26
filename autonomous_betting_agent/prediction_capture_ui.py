"""Small bilingual download panel; never scans, persists, trains or places bets."""
import json
from .prediction_capture import capture_predictions

TEXT = {
 'en': {
  'title': 'Paper evidence: capture current predictions',
  'empty': 'No current Pro Predictor rows in this session. This panel does not load history or start a paid scan.',
  'note': 'One-tap download of the available prediction fields from every passed row in this session. This is not the full scanned population, an authenticated timestamp, a bet, or a complete forward-test packet. No model or history is changed.',
  'scope': 'The capture time is now, not when these predictions were made. Older session rows may be stale. Extra fields are omitted and listed by name; nonfinite values are explicitly marked, never replaced with probabilities.',
  'rows': 'Session rows captured', 'missing': 'Rows missing valid packet evidence',
  'blocked': 'Forward-test packet not ready. Original model/baseline provenance, exact identities, event/odds timing and a predeclared test protocol must be supplied and checked. Confidence labels, current time and market odds cannot fill those gaps.',
  'download': 'Download current prediction evidence', 'details': 'Missing fields and technical details',
  'next': 'Open evidence preparation',
  'error': 'These session rows could not be safely captured. No partial download, scan or record change was made.',
 },
 'es': {
  'title': 'Evidencia en papel: capturar predicciones actuales',
  'empty': 'No hay filas actuales del Predictor Pro en esta sesión. Este panel no carga el historial ni inicia un escaneo de pago.',
  'note': 'Descarga con un toque los campos disponibles de todas las filas aprobadas en esta sesión. No es la población completa escaneada, una constancia de tiempo autenticada, una apuesta ni un paquete prospectivo completo. No cambia el modelo ni el historial.',
  'scope': 'La fecha de captura es la actual, no la fecha de las predicciones. Las filas anteriores pueden estar desactualizadas. Los campos adicionales se omiten y se enumeran por nombre; los valores no finitos se marcan, nunca se sustituyen por probabilidades.',
  'rows': 'Filas de la sesión capturadas', 'missing': 'Filas sin evidencia válida para el paquete',
  'blocked': 'El paquete prospectivo aún no está listo. Se requieren y deben revisarse la procedencia del modelo y la referencia, las identidades exactas, las fechas de evento/cuotas y un protocolo declarado de antemano. Las etiquetas de confianza, la hora actual y las cuotas no completan esos datos faltantes.',
  'download': 'Descargar evidencia de predicciones actuales', 'details': 'Campos faltantes y detalles técnicos',
  'next': 'Abrir preparación de evidencia',
  'error': 'No se pudieron capturar estas filas de forma segura. No se generó una descarga parcial, un escaneo ni un cambio de registros.',
 }
}


def render_prediction_capture(rows, language='en'):
    import streamlit as st
    t = TEXT.get(language, TEXT['en'])
    st.subheader(t['title'])
    st.caption(t['note'])
    if rows is None or (isinstance(rows, list) and not rows):
        st.info(t['empty'])
        return
    try:
        snapshot = capture_predictions(rows)
    except (ValueError, TypeError, OverflowError, RecursionError):
        st.error(t['error'])
        return
    st.caption(t['scope'])
    a, b = st.columns(2)
    a.metric(t['rows'], snapshot['row_count'])
    b.metric(t['missing'], snapshot['rows_with_missing_or_invalid_fields'])
    st.warning(t['blocked'])
    st.download_button(t['download'], json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False),
                       file_name=f"prediction_evidence_{snapshot['capture_sha256'][:16]}.json",
                       mime='application/json', key='aba_prediction_capture_download')
    with st.expander(t['details']):
        st.json({'required_protocol_fields': snapshot['required_protocol_fields'], 'rows': [
            {key: row[key] for key in ('source_row_index', 'missing_fields', 'structural_error', 'omitted_field_names', 'possible_aliases_not_applied')}
            for row in snapshot['rows']]})
    st.page_link('pages/forward_test_tracker.py', label=t['next'])
