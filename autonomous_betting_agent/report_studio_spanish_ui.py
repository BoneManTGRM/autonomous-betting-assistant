from __future__ import annotations

from typing import Any, Iterable, Sequence

REPORT_TEXT_ES = {
    "DAILY SPORTS ANALYSIS": "ANÁLISIS DEPORTIVO DIARIO",
    "TEAM SNAPSHOTS": "RESUMEN DE EQUIPOS",
    "RISK DESK": "MESA DE RIESGO",
    "PARLAY RECOMMENDATION BOARD": "TABLERO DE RECOMENDACIONES PARLAY",
    "PRIMARY ANCHOR": "ANCLA PRINCIPAL",
    "TOP PARLAY RECOMMENDATIONS": "MEJORES RECOMENDACIONES PARLAY",
    "BEST 2-LEG PARLAYS": "MEJORES PARLAYS DE 2 SELECCIONES",
    "BEST 3/4-LEG PARLAYS": "MEJORES PARLAYS DE 3/4 SELECCIONES",
    "SGP / CROSS / PROP / LIVE": "SGP / CRUZADO / PROP / EN VIVO",
    "PARLAY AVOID LIST": "PARLAYS A EVITAR",
    "SOURCE DIAGNOSTICS": "DIAGNÓSTICO DE FUENTE",
    "CANCEL CONDITIONS": "CONDICIONES DE CANCELACIÓN",
    "ADVANCED MARKET ANALYSIS": "ANÁLISIS AVANZADO DE MERCADO",
    "STRAIGHT ANCHOR ONLY": "SOLO ANCLA DIRECTA",
    "NO VERIFIED PARLAY AVAILABLE": "SIN PARLAY VERIFICADO DISPONIBLE",
    "FINAL RECOMMENDATION": "RECOMENDACIÓN FINAL",
    "RECOMMENDATION": "RECOMENDACIÓN",
    "TARGET": "OBJETIVO",
    "VERIFY PRICE": "VERIFICAR CUOTA",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "REPORT SOURCE": "FUENTE DEL REPORTE",
    "DATA SCOPE": "ALCANCE DE DATOS",
    "TRUTH": "VERDAD",
    "ODDS STATUS": "ESTADO DE CUOTAS",
    "Uploaded / saved row": "Fila cargada / guardada",
    "Saved-source verification report": "Reporte de verificación de fuente guardada",
    "UPLOADED_ROW": "FILA CARGADA",
    "Ranked parlays use real priced legs only. SGPs need sportsbook pricing or modeled correlation. Props need prop-specific probability.": "Los parlays clasificados usan solo selecciones con cuotas reales. Los SGP requieren precio de la casa o correlación modelada. Los props requieren probabilidad específica.",
    "Page 1 remains the straight-bet anchor; Page 2 only adds verified parlays.": "La página 1 sigue siendo el ancla de apuesta directa; la página 2 solo agrega parlays verificados.",
    "No verified parlay available. Straight anchor only until another priced, positive-EV, source-traceable leg exists.": "Sin parlay verificado disponible. Solo ancla directa hasta que exista otra selección con cuota, VE positivo y fuente rastreable.",
    "Parlay candidates were blocked by pricing, correlation, EV, stale data, or missing model probability.": "Los candidatos parlay fueron bloqueados por precio, correlación, VE, datos vencidos o probabilidad de modelo faltante.",
    "No SGP/cross-game/prop/live parlay is playable until provider returns priced eligible legs and correlation is handled.": "No hay parlay SGP/cruzado/prop/en vivo jugable hasta que el proveedor devuelva selecciones elegibles con cuota y la correlación esté resuelta.",
    "Avoid any market with stale odds, line movement against the anchor, missing prop model, unsupported SGP pricing, or expired live window.": "Evitar cualquier mercado con cuotas vencidas, movimiento de línea contra el ancla, modelo de prop faltante, SGP sin precio o ventana en vivo expirada.",
    "Cancel if Page 1 line changes or sportsbook line differs from the report line.": "Cancelar si la línea de la página 1 cambia o si la casa muestra una línea distinta.",
    "Cancel if any leg loses odds, timestamp, provider match, market status, or positive EV.": "Cancelar si alguna selección pierde cuota, marca de tiempo, coincidencia de proveedor, estado de mercado o VE positivo.",
    "Cancel if SGP correlation cannot be priced by sportsbook or model.": "Cancelar si la correlación SGP no puede ser tasada por la casa o por el modelo.",
    "Cancel if a live/flash window is started, suspended, or expired.": "Cancelar si una ventana en vivo/flash inició, fue suspendida o expiró.",
    "No verified 2-leg parlay found. Reason: only one priced positive-EV leg available or correlation/pricing blocked.": "No se encontró parlay verificado de 2 selecciones. Motivo: solo hay una selección con cuota y VE positivo, o la correlación/precio está bloqueado.",
    "No verified 3-leg parlay found. Three independently eligible legs were not available.": "No se encontró parlay verificado de 3 selecciones. No hubo tres selecciones independientes elegibles.",
    "No verified 4-leg longshot. Four eligible priced legs were not available.": "No se encontró parlay largo verificado de 4 selecciones. No hubo cuatro selecciones elegibles con cuota.",
    "Context unavailable.": "Contexto no disponible.",
    "Data unavailable": "Dato no disponible",
    "Not provided": "No proporcionado",
    "Sport N/A": "Deporte N/D",
    "Team form data was not returned for this soccer event.": "No se recibieron datos de forma para este evento de fútbol.",
    "Team form data was not returned for this baseball event.": "No se recibieron datos de forma para este evento de béisbol.",
    "Lineup and injury data were not returned for this soccer event.": "No se recibieron datos de alineación o lesiones para este evento de fútbol.",
    "Lineup and injury data were not returned for this baseball event.": "No se recibieron datos de alineación o lesiones para este evento de béisbol.",
    "Context was not returned for this event.": "No se recibió contexto para este evento.",
    "Check lineup and news updates before publishing.": "Revisar alineación y noticias antes de publicar.",
    "Recheck price before publishing.": "Revisar la cuota antes de publicar.",
    "uploaded/cached row": "fila cargada/en caché",
}

REPORT_TEXT_ES.update({f"PAGE {page} OF {total}": f"PÁGINA {page} DE {total}" for total in range(1, 201) for page in range(1, total + 1)})

SPORT_LEAGUE_ES = {
    "Boxing": "Boxeo",
    "MMA": "MMA",
    "MLB": "MLB",
    "NCAAB": "NCAAB",
    "NCAAF": "NCAAF",
    "NBA": "NBA",
    "NFL": "NFL",
    "NHL": "NHL",
    "FIFA World Cup": "Copa Mundial FIFA",
    "League of Ireland": "Liga de Irlanda",
    "Allsvenskan - Sweden": "Allsvenskan - Suecia",
    "Eliteserien - Norway": "Eliteserien - Noruega",
    "Veikkausliiga - Finland": "Veikkausliiga - Finlandia",
    "NCAA Baseball": "Béisbol NCAA",
    "Super League - China": "Superliga - China",
    "Brazil Série B": "Brasil Serie B",
    "Brazil Serie B": "Brasil Serie B",
    "Soccer": "Fútbol",
    "Football": "Fútbol americano",
    "Basketball": "Baloncesto",
    "Baseball": "Béisbol",
    "Tennis": "Tenis",
    "English Premier League": "Premier League inglesa",
    "Premier League": "Premier League",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Liga MX": "Liga MX",
}


def _install_report_text_terms() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export
        magazine_book_export.ES.update(REPORT_TEXT_ES)
    except Exception:
        pass
    try:
        from autonomous_betting_agent import magazine_second_page_patch
        magazine_second_page_patch.ES.update(REPORT_TEXT_ES)
    except Exception:
        pass


def sport_league_display_text(value: Any, language: str = "en") -> str:
    text = str(value or "").strip()
    if language == "es":
        return SPORT_LEAGUE_ES.get(text, text)
    return text


def selected_raw_sport_values(display_values: Iterable[str], options: Sequence[str], language: str = "en") -> list[str]:
    wanted = {str(value or "").strip() for value in display_values}
    selected: list[str] = []
    for option in options:
        display = sport_league_display_text(option, language)
        if option in wanted or display in wanted:
            selected.append(option)
    return selected


def render_sport_league_filter(st, *, label: str, options: Sequence[str], default: Iterable[str] | None = None, language: str = "en", key: str = "report_profile_sports") -> list[str]:
    _install_report_text_terms()
    raw_options = [str(option) for option in options if str(option or "").strip()]
    default_values = [option for option in raw_options if option in {str(value) for value in (default or [])}]
    return list(st.multiselect(label, raw_options, default=default_values, key=key, format_func=lambda option: sport_league_display_text(option, language)))


_install_report_text_terms()
