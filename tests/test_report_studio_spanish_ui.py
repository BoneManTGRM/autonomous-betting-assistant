from __future__ import annotations

from pathlib import Path

from autonomous_betting_agent.report_studio_spanish_ui import selected_raw_sport_values, sport_league_display_text

ROOT = Path(__file__).resolve().parents[1]
REPORT_STUDIO = ROOT / "pages" / "report_studio.py"
SITECUSTOMIZE = ROOT / "sitecustomize.py"


def _report_studio_source() -> str:
    return REPORT_STUDIO.read_text(encoding="utf-8")


def _sitecustomize_source() -> str:
    return SITECUSTOMIZE.read_text(encoding="utf-8")


def test_sport_league_display_text_spanish():
    assert sport_league_display_text("Boxing", "es") == "Boxeo"
    assert sport_league_display_text("FIFA World Cup", "es") == "Copa Mundial FIFA"
    assert sport_league_display_text("League of Ireland", "es") == "Liga de Irlanda"
    assert sport_league_display_text("Brazil Série B", "es") == "Brasil Serie B"
    assert sport_league_display_text("MLB", "es") == "MLB"
    assert sport_league_display_text("Boxing", "en") == "Boxing"


def test_spanish_display_labels_map_back_to_raw_values():
    options = ["Boxing", "FIFA World Cup", "League of Ireland", "MLB"]
    assert selected_raw_sport_values(["Boxeo", "Liga de Irlanda"], options, "es") == ["Boxing", "League of Ireland"]
    assert selected_raw_sport_values(["Boxing", "MLB"], options, "es") == ["Boxing", "MLB"]


def test_report_studio_uses_local_spanish_sport_filter_not_global_widget_patch():
    text = _report_studio_source()
    assert "from autonomous_betting_agent.report_studio_spanish_ui import render_sport_league_filter" in text
    assert "preferred_sports = render_sport_league_filter(" in text
    assert "st.multiselect(t(\"sports\")" not in text
    assert "sport_league_display_text" in text


def test_report_studio_magazine_tab_uses_full_pick_renderer_not_old_mobile_preview():
    text = _report_studio_source()
    assert "magazine_pdf_bytes = magazine_book_export.render_full_magazine_book_pdf" in text
    assert "magazine_tab_png = magazine_book_export.render_full_pick_magazine_page_png" in text
    assert "render_magazine_summary_png" not in text
    assert "render_mobile_deck_png" not in text
    assert "Mobile readable report - 3 cards per image" not in text
    assert "Reporte legible móvil - 3 tarjetas por imagen" not in text


def test_sitecustomize_does_not_monkey_patch_streamlit_widgets():
    text = _sitecustomize_source()
    assert "st.multiselect =" not in text
    assert "st.selectbox =" not in text
    assert "st.file_uploader =" not in text
    assert "st.button =" not in text
    assert "translated_multiselect" not in text
