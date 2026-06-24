from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.report_exports import PRINT_TO_PDF_NOTE, render_html_report, render_markdown_report, render_messenger_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage
from autonomous_betting_agent.ui_i18n import tr

st.set_page_config(page_title="Report Studio Local Export", layout="wide")
LANG = render_app_sidebar("report_studio_local_export", language_key="report_studio_local_export_language")
require_streamlit_access(st, allow_roles={"admin", "client"})

st.title(tr(LANG, "Report Studio Local Export", "Exportación Local de Reportes"))
st.caption(tr(LANG, "Generate Markdown, HTML, and copy/paste report output from local rows.", "Genera Markdown, HTML y texto para copiar/pegar desde filas locales."))
st.info(tr(LANG, PRINT_TO_PDF_NOTE, "Abre el HTML en un navegador y usa Imprimir o Guardar como PDF."))

store = LocalStorage()
rows = store.load_rows()

if not rows:
    st.info(tr(LANG, "No local rows found yet.", "Todavía no hay filas locales."))
    st.stop()

with st.sidebar:
    st.markdown(tr(LANG, "### Report settings", "### Configuración del reporte"))
    title = st.text_input(tr(LANG, "Report title", "Título del reporte"), tr(LANG, "ABA Signal Pro Report", "Reporte ABA Signal Pro"))
    client_name = st.text_input(tr(LANG, "Client name", "Nombre del cliente"), "")
    public_safe = st.toggle(tr(LANG, "Public-safe mode", "Modo seguro para público"), value=True)
    background = st.text_input(tr(LANG, "Background image", "Imagen de fondo"), "")

markdown_report = render_markdown_report(rows, title=title, client_name=client_name, public_safe=public_safe)
html_report = render_html_report(rows, title=title, client_name=client_name, background_image_url=background, public_safe=public_safe)
message_report = render_messenger_report(rows, title=title)

st.subheader(tr(LANG, "Copy/paste report", "Reporte para copiar/pegar"))
st.text_area(tr(LANG, "Message summary", "Resumen para mensaje"), message_report, height=140)

st.subheader(tr(LANG, "Markdown report", "Reporte Markdown"))
st.download_button(tr(LANG, "Download Markdown report", "Descargar reporte Markdown"), markdown_report.encode("utf-8"), file_name="aba_signal_pro_report.md", mime="text/markdown")
st.text_area(tr(LANG, "Markdown preview", "Vista previa Markdown"), markdown_report, height=360)

st.subheader(tr(LANG, "HTML report", "Reporte HTML"))
st.download_button(tr(LANG, "Download HTML report", "Descargar reporte HTML"), html_report.encode("utf-8"), file_name="aba_signal_pro_report.html", mime="text/html")
with st.expander(tr(LANG, "HTML preview/source", "Vista previa/código HTML")):
    st.code(html_report, language="html")

st.warning(tr(LANG, "Presentation and proof-tracking tool only.", "Solo herramienta de presentación y seguimiento."))
