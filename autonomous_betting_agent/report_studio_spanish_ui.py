from __future__ import annotations

import re
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
    "WHY WE PICKED IT": "POR QUÉ LO ELEGIMOS",
    "PRO BETTOR EVIDENCE": "EVIDENCIA DEL APOSTADOR PRO",
    "PLAYER / INJURY NOTES": "JUGADORES / LESIONES",
    "MATCHUP NOTES": "NOTAS DEL PARTIDO",
    "FINAL RECOMMENDATION": "RECOMENDACIÓN FINAL",
    "FINAL": "FINAL",
    "RECOMMENDATION": "RECOMENDACIÓN",
    "TARGET": "OBJETIVO",
    "VERIFY PRICE": "VERIFICAR CUOTA",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "REPORT SOURCE": "FUENTE DEL REPORTE",
    "DATA SCOPE": "ALCANCE DE DATOS",
    "TRUTH": "VERDAD",
    "ODDS STATUS": "ESTADO DE CUOTAS",
    "ODDS": "CUOTA",
    "CONFIDENCE": "CONFIANZA",
    "EDGE": "VENTAJA",
    "RISK": "RIESGO",
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
    "No guarantees. Bet responsibly. This analysis is for informational purposes only.": "No garantizamos resultados. Apuesta responsablemente. Este análisis es solo informativo.",
    "Fallback/watchlist only.": "Solo respaldo/lista de seguimiento.",
    "Confirm current price before entry.": "Confirmar cuota actual antes de entrar.",
    "Watchlist only: current price and live context need verification.": "Solo seguimiento: la cuota actual y el contexto en vivo requieren verificación.",
    "Source type: Saved-source report": "Tipo de fuente: reporte de fuente guardada",
    "Current proveedor match: Not verificado": "Coincidencia actual del proveedor: no verificada",
    "marca de tiempo: Saved-row marca de tiempo": "Marca de tiempo: marca de fila guardada",
    "Verification status: Source saved": "Estado de verificación: fuente guardada",
    "STRAIGHT ANCHOR ONLY: No verificado parlay candidate yet qualified from current proveedor mercados.": "SOLO ANCLA DIRECTA: ningún candidato parlay verificado calificó con los mercados actuales del proveedor.",
    "Eligible legs found: 0. Need at least two verificado quotad positive-EV legs.": "Selecciones elegibles encontradas: 0. Se necesitan al menos dos selecciones verificadas, con cuota y VE positivo.",
    "No verificado parlay candidate yet available. Straight anchor only until another quotad, positive-EV, source-traceable leg exists.": "Sin parlay verificado disponible. Solo ancla directa hasta que exista otra selección con cuota, VE positivo y fuente rastreable.",
}

REPORT_TEXT_ES.update({f"PAGE {page} OF {total}": f"PÁGINA {page} DE {total}" for total in range(1, 201) for page in range(1, total + 1)})

REPORT_PART_ES = (
    ("DAILY SPORTS ANALYSIS", "ANÁLISIS DEPORTIVO DIARIO"),
    ("WHY WE PICKED IT", "POR QUÉ LO ELEGIMOS"),
    ("TEAM SNAPSHOTS", "RESUMEN DE EQUIPOS"),
    ("PLAYER / INJURY NOTES", "JUGADORES / LESIONES"),
    ("MATCHUP NOTES", "NOTAS DEL PARTIDO"),
    ("PRO BETTOR EVIDENCE", "EVIDENCIA DEL APOSTADOR PRO"),
    ("FINAL RECOMMENDATION", "RECOMENDACIÓN FINAL"),
    ("REPORT SOURCE", "FUENTE DEL REPORTE"),
    ("DATA SCOPE", "ALCANCE DE DATOS"),
    ("ODDS STATUS", "ESTADO DE CUOTAS"),
    ("Uploaded / saved row", "Fila cargada / guardada"),
    ("Saved-source verification report", "Reporte de verificación de fuente guardada"),
    ("UPLOADED_ROW", "FILA CARGADA"),
    ("VERIFY PRICE", "VERIFICAR CUOTA"),
    ("Source type", "Tipo de fuente"),
    ("Saved-source report", "reporte de fuente guardada"),
    ("Current proveedor match", "Coincidencia actual del proveedor"),
    ("Not verificado", "no verificada"),
    ("Verification status", "Estado de verificación"),
    ("Source saved", "fuente guardada"),
    ("Eligible legs found", "Selecciones elegibles encontradas"),
    ("Need at least two", "Se necesitan al menos dos"),
    ("verificado quotad", "verificadas con cuota"),
    ("positive-EV", "VE positivo"),
    ("STRAIGHT ANCHOR ONLY", "SOLO ANCLA DIRECTA"),
    ("candidate yet qualified from current proveedor mercados", "candidato calificado con los mercados actuales del proveedor"),
    ("candidate yet available", "candidato disponible"),
    ("Straight anchor only until another quotad", "Solo ancla directa hasta que exista otra selección con cuota"),
    ("source-traceable leg exists", "selección con fuente rastreable"),
    ("The pick is", "La selección es"),
    ("The pick for", "La selección para"),
    ("The game total for", "El total del partido para"),
    ("is supported by", "está respaldado por"),
    ("are favored by", "son favoritas por"),
    ("is favored by", "es favorito por"),
    ("are listed as", "aparecen como"),
    ("is listed as", "aparece como"),
    ("is not the current market", "no es el mercado actual"),
    ("home underdog", "local no favorito"),
    ("run underdog", "no favorito en línea de carrera"),
    ("run-line favorite", "favorito en línea de carrera"),
    ("current market", "mercado actual"),
    ("upcoming", "próximo"),
    ("most recent", "más reciente"),
    ("matched teams", "vinculó equipos"),
    ("injuries checked", "lesiones revisadas"),
    ("Weather: Weather:", "Clima:"),
    ("Weather:", "Clima:"),
    ("Location:", "Ubicación:"),
    ("wind", "viento"),
    ("Sunny", "Soleado"),
    ("Partly cloudy", "Parcialmente nublado"),
    ("Light rain", "Lluvia ligera"),
    ("Clear", "Despejado"),
    ("Overcast", "Nublado"),
    ("Context:", "Contexto:"),
    ("United States of America", "Estados Unidos"),
    ("United States", "Estados Unidos"),
    ("No guarantees. Bet responsibly. This analysis is for informational purposes only.", "No garantizamos resultados. Apuesta responsablemente. Este análisis es solo informativo."),
)

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


def spanish_report_text(value: Any, language: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or language != "es":
        return text
    if text in REPORT_TEXT_ES:
        return REPORT_TEXT_ES[text]
    text = re.sub(r"\bPAGE\s+(\d+)\s+OF\s+(\d+)\b", r"PÁGINA \1 DE \2", text, flags=re.I)
    for old, new in REPORT_PART_ES:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _patch_translation_function(module: Any) -> None:
    try:
        module.ES.update(REPORT_TEXT_ES)
    except Exception:
        pass
    original = getattr(module, "_tr", None)
    if not callable(original) or getattr(original, "_ABA_SPANISH_VISIBLE_TEXT_PATCH", False):
        return

    def patched(value: Any, language: str) -> str:
        return spanish_report_text(original(value, language), language)

    patched._ABA_SPANISH_VISIBLE_TEXT_PATCH = True  # type: ignore[attr-defined]
    module._tr = patched


def _install_report_text_terms() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export
        _patch_translation_function(magazine_book_export)
    except Exception:
        pass
    try:
        from autonomous_betting_agent import magazine_second_page_patch
        _patch_translation_function(magazine_second_page_patch)
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
