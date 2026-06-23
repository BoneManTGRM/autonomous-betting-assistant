from __future__ import annotations

import streamlit as st


NOTICE_EN = "This report page is retained for compatibility. The unified Report Studio now contains the final premium cards, magazine report, image exports, proof tables, learning audit, app feed, profiles, and diagnostics. Use the main Report Studio page for production delivery."
NOTICE_ES = "Esta página de reportes se conserva por compatibilidad. El Estudio de Reportes unificado contiene las tarjetas premium finales, reporte revista, exportación de imágenes, prueba técnica, auditoría de aprendizaje, feed de app, perfiles y diagnóstico. Usa el Estudio de Reportes principal para entrega de producción."


def render_legacy_report_notice(language: str = "en") -> None:
    text = NOTICE_ES if str(language or "en").lower().startswith("es") else NOTICE_EN
    st.info(text)
