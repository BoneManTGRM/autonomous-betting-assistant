from __future__ import annotations


def is_spanish(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("es")


def tr(language: str | None, english: str, spanish: str) -> str:
    return spanish if is_spanish(language) else english


def upload_helper(language: str | None) -> str:
    return tr(language, "Upload control text may be controlled by Streamlit.", "El botón interno de carga puede depender de Streamlit.")


def render_upload_css(st_module, language: str | None) -> None:
    """Best-effort Spanish styling for Streamlit's built-in file uploader.

    Streamlit owns the internal file-uploader button text. This CSS only runs in
    Spanish mode and visually replaces the default button label where Streamlit's
    current DOM supports it.
    """
    if not is_spanish(language):
        return
    st_module.markdown(
        """
<style>
div[data-testid="stFileUploader"] button div p,
div[data-testid="stFileUploader"] button p,
div[data-testid="stFileUploader"] button span {
  font-size: 0 !important;
  line-height: 0 !important;
}
div[data-testid="stFileUploader"] button div p::after,
div[data-testid="stFileUploader"] button p::after,
div[data-testid="stFileUploader"] button span::after {
  content: "Subir";
  font-size: 1rem !important;
  line-height: 1.2 !important;
}
div[data-testid="stFileUploader"] small {
  font-size: 0 !important;
}
div[data-testid="stFileUploader"] small::after {
  content: "CSV u otro archivo compatible";
  font-size: .9rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
