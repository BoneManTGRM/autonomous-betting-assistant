from autonomous_betting_agent.report_studio_spanish_ui import REPORT_TEXT_ES, sport_league_display_text


def test_spanish_report_headings_are_available():
    assert REPORT_TEXT_ES["DAILY SPORTS ANALYSIS"] == "ANÁLISIS DEPORTIVO DIARIO"
    assert REPORT_TEXT_ES["PARLAY RECOMMENDATION BOARD"] == "TABLERO DE RECOMENDACIONES PARLAY"
    assert REPORT_TEXT_ES["STRAIGHT ANCHOR ONLY"] == "SOLO ANCLA DIRECTA"
    assert REPORT_TEXT_ES["SOURCE DIAGNOSTICS"] == "DIAGNÓSTICO DE FUENTE"


def test_spanish_body_report_terms_are_available():
    assert REPORT_TEXT_ES["Ranked parlays use real priced legs only. SGPs need sportsbook pricing or modeled correlation. Props need prop-specific probability."] == "Los parlays clasificados usan solo selecciones con cuotas reales. Los SGP requieren precio de la casa o correlación modelada. Los props requieren probabilidad específica."
    assert REPORT_TEXT_ES["Cancel if any leg loses odds, timestamp, provider match, market status, or positive EV."] == "Cancelar si alguna selección pierde cuota, marca de tiempo, coincidencia de proveedor, estado de mercado o VE positivo."
    assert REPORT_TEXT_ES["No verified 2-leg parlay found. Reason: only one priced positive-EV leg available or correlation/pricing blocked."] == "No se encontró parlay verificado de 2 selecciones. Motivo: solo hay una selección con cuota y VE positivo, o la correlación/precio está bloqueado."


def test_spanish_sport_labels_still_work():
    assert sport_league_display_text("Allsvenskan - Sweden", "es") == "Allsvenskan - Suecia"
    assert sport_league_display_text("NCAA Baseball", "es") == "Béisbol NCAA"
