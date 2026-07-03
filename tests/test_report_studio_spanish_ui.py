from __future__ import annotations

from pathlib import Path

from autonomous_betting_agent.report_studio_spanish_ui import selected_raw_sport_values, sport_league_display_text

ROOT = Path(__file__).resolve().parents[1]
REPORT_STUDIO = ROOT / "pages" / "report_studio.py"
SITECUSTOMIZE = ROOT / "sitecustomize.py"
SIDEBAR_NAV = ROOT / "autonomous_betting_agent" / "sidebar_nav.py"
SHADOW_MODE = ROOT / "pages" / "shadow_mode_results.py"
MARKET_OPTIMIZER = ROOT / "pages" / "market_optimizer.py"
MARKET_BRIDGE = ROOT / "pages" / "market_dashboard_bridge.py"
APP_STREAMLIT = ROOT / "app_streamlit.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _report_studio_source() -> str:
    return _read(REPORT_STUDIO)


def _sitecustomize_source() -> str:
    return _read(SITECUSTOMIZE)


def test_sport_league_display_text_spanish():
    assert sport_league_display_text("Boxing", "es") == "Boxeo"
    assert sport_league_display_text("FIFA World Cup", "es") == "Copa Mundial FIFA"
    assert sport_league_display_text("League of Ireland", "es") == "Liga de Irlanda"
    assert sport_league_display_text("Brazil Série B", "es") == "Brasil Série B"
    assert sport_league_display_text("Brazil Serie B", "es") == "Brasil Série B"
    assert sport_league_display_text("NCAA Baseball", "es") == "Béisbol NCAA"
    assert sport_league_display_text("Allsvenskan - Sweden", "es") == "Allsvenskan - Suecia"
    assert sport_league_display_text("Eliteserien - Norway", "es") == "Eliteserien - Noruega"
    assert sport_league_display_text("Veikkausliiga - Finland", "es") == "Veikkausliiga - Finlandia"
    assert sport_league_display_text("MLB", "es") == "MLB"
    assert sport_league_display_text("Boxing", "en") == "Boxing"


def test_spanish_display_labels_map_back_to_raw_values():
    options = ["Boxing", "FIFA World Cup", "League of Ireland", "MLB", "Brazil Serie B"]
    assert selected_raw_sport_values(["Boxeo", "Liga de Irlanda"], options, "es") == ["Boxing", "League of Ireland"]
    assert selected_raw_sport_values(["Boxing", "MLB"], options, "es") == ["Boxing", "MLB"]
    assert selected_raw_sport_values(["Brasil Série B"], options, "es") == ["Brazil Serie B"]


def test_report_studio_uses_local_spanish_sport_filter_not_global_widget_patch():
    text = _report_studio_source()
    assert "from autonomous_betting_agent.report_studio_spanish_ui import render_sport_league_filter" in text
    assert "preferred_sports = render_sport_league_filter(" in text
    assert "st.multiselect(t(\"sports\")" not in text
    assert "render_sport_league_filter" in text


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


def test_sidebar_spanish_navigation_is_polished():
    text = _read(SIDEBAR_NAV)
    assert "Impulsado por Reparodinámica" in text
    assert "Constructor de cartelera con cuotas actualizadas" in text
    assert "Estudio de reportes" in text
    assert "Centro de pruebas" in text
    assert "Optimizador de mercados" in text
    assert "BDL: Activo" in text
    assert "Constructor de Slate de Odds Frescas" not in text
    assert "Impulsado por Reparodynamics" not in text
    assert "Centro de Prueba" not in text


def test_spanish_shadow_mode_copy_explains_data_blocked():
    text = _read(SHADOW_MODE)
    assert "Datos bloqueados" in text
    assert "Sin modelo" in text
    assert "la capa sombra no pudo crear una separación segura" in text
    assert "Metricas baseline" not in text
    assert "Comparacion dinamica" not in text
    assert "Dynamic aplicado EN VIVO" not in text


def test_spanish_market_pages_do_not_use_mixed_spanglish_labels():
    optimizer = _read(MARKET_OPTIMIZER)
    bridge = _read(MARKET_BRIDGE)
    app = _read(APP_STREAMLIT)
    assert "Optimizador de mercados" in optimizer
    assert "Vista previa" not in optimizer or "preview" not in optimizer[optimizer.find('"es"'):] 
    assert "Puente del panel de mercados" in bridge
    assert "SOLO VISTA PREVIA" in bridge
    assert "Impulsado por Reparodinámica" in app
    for bad in ["dashboard bridge", "outputs", "NO LIVE CHANGES", "NO FILES WRITTEN", "optimizer preview", "Learning Memory"]:
        assert bad not in bridge[bridge.find('"es"'):]
        assert bad not in optimizer[optimizer.find('"es"'):]
        assert bad not in app[app.find("'es'"):]
