from autonomous_betting_agent.report_studio_spanish_ui import REPORT_TEXT_ES, sport_league_display_text


def test_spanish_report_headings_are_available():
    assert REPORT_TEXT_ES["DAILY SPORTS ANALYSIS"] == "ANÁLISIS DEPORTIVO DIARIO"
    assert REPORT_TEXT_ES["PARLAY RECOMMENDATION BOARD"] == "TABLERO DE RECOMENDACIONES PARLAY"
    assert REPORT_TEXT_ES["STRAIGHT ANCHOR ONLY"] == "SOLO ANCLA DIRECTA"
    assert REPORT_TEXT_ES["SOURCE DIAGNOSTICS"] == "DIAGNÓSTICO DE FUENTE"


def test_spanish_sport_labels_still_work():
    assert sport_league_display_text("Allsvenskan - Sweden", "es") == "Allsvenskan - Suecia"
    assert sport_league_display_text("NCAA Baseball", "es") == "Béisbol NCAA"
