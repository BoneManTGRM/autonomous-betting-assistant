from __future__ import annotations


def install_mobile_button_fallback() -> None:
    """Leave Streamlit's native upload and button widgets untouched.

    Earlier mobile fallback logic monkey-patched Streamlit button/form behavior.
    That made debugging upload controls harder because all pages inherited the
    patch through sitecustomize/sidebar setup. The safest fix is to remove the
    runtime monkey-patch completely and let st.file_uploader, st.button, forms,
    and form submit buttons run normally.
    """
    return None
