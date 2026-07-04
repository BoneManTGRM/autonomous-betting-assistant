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
}

BODY_TEXT_ES = {
    "Ranked parlays use real priced legs only.": "Los parlays clasificados usan solo selecciones con cuotas reales.",
    "SGPs need sportsbook pricing or modeled correlation.": "Los SGP requieren precio de la casa o correlación modelada.",
    "Props need prop-specific probability.": "Los props requieren probabilidad específica.",
    "Straight anchor only": "Solo ancla directa",
    "no verified parlay qualified from current provider markets": "ningún parlay verificado calificó con los mercados actuales del proveedor",
    "Eligible legs found": "Selecciones elegibles encontradas",
    "Need at least two verified priced positive-EV legs.": "Se necesitan al menos dos selecciones verificadas, con cuota y VE positivo.",
    "No verified 2-leg parlay found.": "No se encontró parlay verificado de 2 selecciones.",
    "No verified 3-leg parlay found.": "No se encontró parlay verificado de 3 selecciones.",
    "No verified 4-leg longshot.": "No se encontró parlay largo verificado de 4 selecciones.",
    "only one priced positive-EV leg available or correlation/pricing blocked": "solo hay una selección con cuota y VE positivo, o la correlación/precio está bloqueado",
    "Three independently eligible legs were not available.": "No hubo tres selecciones independientes elegibles.",
    "Four eligible priced legs were not available.": "No hubo cuatro selecciones elegibles con cuota.",
    "No SGP/cross-game/prop/live parlay is playable until provider returns priced eligible legs and correlation is handled.": "No hay parlay SGP/cruzado/prop/en vivo jugable hasta que el proveedor devuelva selecciones elegibles con cuota y la correlación esté resuelta.",
    "Avoid any market with stale odds, line movement against the anchor, missing prop model, unsupported SGP pricing, or expired live window.": "Evitar cualquier mercado con cuotas vencidas, movimiento de línea contra el ancla, modelo de prop faltante, SGP sin precio o ventana en vivo expirada.",
    "Cancel if Page 1 line changes or sportsbook line differs from the report line.": "Cancelar si la línea de la página 1 cambia o si la casa muestra una línea distinta.",
    "Cancel if any leg loses odds, timestamp, provider match, market status, or positive EV.": "Cancelar si alguna selección pierde cuota, marca de tiempo, coincidencia de proveedor, estado de mercado o VE positivo.",
    "Cancel if SGP correlation cannot be priced by sportsbook or model.": "Cancelar si la correlación SGP no puede ser tasada por la casa o por el modelo.",
    "Cancel if a live/flash window is started, suspended, or expired.": "Cancelar si una ventana en vivo/flash inició, fue suspendida o expiró.",
    "Page 1 remains the straight-bet anchor; Page 2 only adds verified parlays.": "La página 1 sigue siendo el ancla de apuesta directa; la página 2 solo añade parlays verificados.",
    "No verified parlay available. Straight anchor only until another priced, positive-EV, source-traceable leg exists.": "Sin parlay verificado disponible. Solo ancla directa hasta que exista otra selección con cuota, VE positivo y fuente rastreable.",
    "Parlay candidates were blocked by pricing, correlation, EV, stale data, or missing model probability.": "Los candidatos parlay fueron bloqueados por precio, correlación, VE, datos vencidos o probabilidad de modelo faltante.",
    "Provider feed unavailable.": "Fuente del proveedor no disponible.",
    "Provider": "Proveedor",
    "provider": "proveedor",
    "book": "casa",
    "timestamp": "marca de tiempo",
    "Timestamp": "Marca de tiempo",
    "state": "estado",
    "Markets discovered": "Mercados detectados",
    "eligible legs": "selecciones elegibles",
    "Parlay candidates": "Candidatos parlay",
    "playable": "jugables",
    "watchlist": "seguimiento",
    "repair status": "estado de reparación",
    "missing": "faltante",
    "odds": "cuota",
    "implied": "implícita",
    "edge": "ventaja",
    "corr": "correlación",
    "line": "línea",
}

RAW_ERROR_TOKENS = ("HTTP" + "Error", "Trace" + "back", "Request" + "Exception", "Connection" + "Error", "Read" + "Timeout")

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


def translate_public_report_text(value: Any, language: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or language != "es":
        return text
    lowered = text.lower()
    if any(token.lower() in lowered for token in RAW_ERROR_TOKENS):
        return "Fuente del proveedor no disponible."
    for old, new in sorted({**REPORT_TEXT_ES, **BODY_TEXT_ES}.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _patch_translation_function(module: Any) -> None:
    try:
        module.ES.update(REPORT_TEXT_ES)
    except Exception:
        pass
    original = getattr(module, "_tr", None)
    if not callable(original) or getattr(original, "_ABA_SPANISH_BODY_COPY_PATCH", False):
        return

    def patched(value: Any, language: str) -> str:
        return translate_public_report_text(original(value, language), language)

    patched._ABA_SPANISH_BODY_COPY_PATCH = True  # type: ignore[attr-defined]
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
