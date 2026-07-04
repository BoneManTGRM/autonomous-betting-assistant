from autonomous_betting_agent.report_studio_spanish_ui import REPORT_TEXT_ES, sport_league_display_text, translate_public_report_text


def test_spanish_report_headings_are_available():
    assert REPORT_TEXT_ES["DAILY SPORTS ANALYSIS"] == "ANÁLISIS DEPORTIVO DIARIO"
    assert REPORT_TEXT_ES["PARLAY RECOMMENDATION BOARD"] == "TABLERO DE RECOMENDACIONES PARLAY"
    assert REPORT_TEXT_ES["STRAIGHT ANCHOR ONLY"] == "SOLO ANCLA DIRECTA"
    assert REPORT_TEXT_ES["SOURCE DIAGNOSTICS"] == "DIAGNÓSTICO DE FUENTE"


def test_spanish_report_body_copy_is_translated():
    text = translate_public_report_text(
        "Ranked parlays use real priced legs only. SGPs need sportsbook pricing or modeled correlation. Props need prop-specific probability.",
        "es",
    )
    assert "Ranked parlays" not in text
    assert "sportsbook pricing" not in text
    assert "prop-specific probability" not in text
    assert "parlays clasificados" in text
    assert "correlación modelada" in text


def test_spanish_cancel_copy_is_translated():
    text = translate_public_report_text("Cancel if any leg loses odds, timestamp, provider match, market status, or positive EV.", "es")
    assert "Cancel if" not in text
    assert "timestamp" not in text
    assert "provider match" not in text
    assert "Cancelar si" in text
    assert "marca de tiempo" in text


def test_raw_provider_error_is_sanitized_for_spanish():
    text = translate_public_report_text("HTTP" + "Error: provider failed", "es")
    assert text == "Fuente del proveedor no disponible."


def test_spanish_sport_labels_still_work():
    assert sport_league_display_text("Allsvenskan - Sweden", "es") == "Allsvenskan - Suecia"
    assert sport_league_display_text("NCAA Baseball", "es") == "Béisbol NCAA"
