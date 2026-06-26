from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

UNVERIFIED_SOURCE_TOKENS = ("unavailable", "missing", "no odds", "no_odds", "api limit", "limit reached", "quota", "maxed", "rate limit", "offline", "simulated", "model_only")
TENNIS_TOKENS = ("tennis", "atp", "wta", "itf", "challenger")

COUNTRY_ES = {
    "iraq": "Irak",
    "iran": "Irán",
    "france": "Francia",
    "germany": "Alemania",
    "ecuador": "Ecuador",
    "australia": "Australia",
    "paraguay": "Paraguay",
    "netherlands": "Países Bajos",
    "tunisia": "Túnez",
    "egypt": "Egipto",
    "ivory coast": "Costa de Marfil",
    "cote d'ivoire": "Costa de Marfil",
    "côte d’ivoire": "Costa de Marfil",
    "curacao": "Curazao",
    "curaçao": "Curazao",
    "senegal": "Senegal",
    "norway": "Noruega",
    "algeria": "Argelia",
    "jordan": "Jordania",
    "argentina": "Argentina",
    "brazil": "Brasil",
    "spain": "España",
    "england": "Inglaterra",
    "united states": "Estados Unidos",
    "united states of america": "Estados Unidos",
    "usa": "Estados Unidos",
    "us": "Estados Unidos",
    "mexico": "México",
    "italy": "Italia",
    "portugal": "Portugal",
    "canada": "Canadá",
    "japan": "Japón",
    "south korea": "Corea del Sur",
    "new zealand": "Nueva Zelanda",
    "switzerland": "Suiza",
    "belgium": "Bélgica",
    "czech republic": "República Checa",
    "czechia": "Chequia",
    "cape verde": "Cabo Verde",
    "saudi arabia": "Arabia Saudita",
    "morocco": "Marruecos",
    "croatia": "Croacia",
    "poland": "Polonia",
    "denmark": "Dinamarca",
    "sweden": "Suecia",
    "finland": "Finlandia",
    "china": "China",
    "turkey": "Turquía",
    "uruguay": "Uruguay",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Perú",
    "venezuela": "Venezuela",
    "bolivia": "Bolivia",
    "panama": "Panamá",
    "costa rica": "Costa Rica",
    "jamaica": "Jamaica",
    "qatar": "Catar",
    "uae": "Emiratos Árabes Unidos",
    "united arab emirates": "Emiratos Árabes Unidos",
    "south africa": "Sudáfrica",
    "nigeria": "Nigeria",
    "ghana": "Ghana",
    "cameroon": "Camerún",
    "austria": "Austria",
    "scotland": "Escocia",
    "uzbekistan": "Uzbekistán",
    "wales": "Gales",
}

SPORT_ES = {
    "boxing": "Boxeo",
    "soccer": "Fútbol",
    "football": "Fútbol americano",
    "basketball": "Baloncesto",
    "baseball": "Béisbol",
    "hockey": "Hockey",
    "tennis": "Tenis",
    "fifa world cup": "Copa Mundial FIFA",
    "brazil série b": "Serie B de Brasil",
    "league of ireland": "Liga de Irlanda",
    "mlb": "MLB",
    "mma": "MMA",
    "ncaa baseball": "Béisbol NCAA",
    "super league - china": "Superliga - China",
    "veikkausliiga - finland": "Veikkausliiga - Finlandia",
}

VALUE_ES = {
    "Daily Sports Analysis": "Análisis Deportivo Diario",
    "Powered by Reparodynamics": "Impulsado por Reparodynamics",
    "Price Watch / Research": "Seguimiento de precio / investigación",
    "Price Watch": "Seguimiento de precio",
    "Research": "Investigación",
    "Research / Learning": "Investigación / aprendizaje",
    "Research / Track for Learning": "Investigación / seguimiento para aprendizaje",
    "Research / Not Official": "Investigación / no oficial",
    "Watchlist / thin value": "Lista de seguimiento / valor delgado",
    "Official +EV Play": "Jugada oficial +EV",
    "Official +EV": "Oficial +EV",
    "Full magazine analysis": "Análisis completo de revista",
    "No approved plays in this report.": "No hay jugadas aprobadas en este reporte.",
    "No approved plays.": "No hay jugadas aprobadas.",
    "No cards.": "Sin tarjetas.",
    "Matchup": "Partido",
    "Sport": "Deporte",
    "Medium": "Medio",
    "High": "Alto",
    "Low": "Bajo",
    "Strong": "Fuerte",
    "Thin": "Delgado",
    "Positive": "Positivo",
    "Negative at listed odds": "Negativo con la cuota actual",
    "Unknown": "Desconocido",
    "unknown": "desconocido",
    "UNKNOWN": "DESCONOCIDO",
    "PENDING": "PENDIENTE",
    "pending": "pendiente",
    "WIN": "GANADO",
    "win": "ganada",
    "LOSS": "PERDIDO",
    "loss": "perdida",
    "PUSH": "EMPATE/PUSH",
    "push": "push",
    "CANCELLED": "CANCELADO",
    "cancel": "cancelada",
    "Needs grading": "Necesita calificación",
    "Included in calibration": "Incluido en calibración",
    "Excluded: data blocked": "Excluido: datos bloqueados",
    "Data Blocked": "Bloqueado por datos",
    "Watchlist": "Lista de seguimiento",
    "Unsupported sport": "Deporte no soportado",
    "Missing or unverified odds": "Cuotas faltantes o no verificadas",
    "Missing independent model probability": "Falta probabilidad independiente del modelo",
    "Research upgrade candidate": "Candidato para subir a investigación",
    "Calibration opportunity / needs larger sample": "Oportunidad de calibración / necesita muestra mayor",
    "Monitor / no promotion": "Monitorear / sin promoción",
    "Model average": "Promedio del modelo",
    "Selected rows": "Filas seleccionadas",
    "Strict proof gate": "Filtro estricto de prueba",
    "Model lean / track": "Lean del modelo / seguimiento",
    "Report-ready": "Listas para reporte",
    "Final results": "Resultados finales",
    "Blocked rows": "Filas bloqueadas",
    "Paid proof": "Prueba pagada",
    "Calibration rows": "Filas de calibración",
    "totals": "totales",
    "total": "total",
    "spreads": "hándicaps",
    "spread": "hándicap",
    "moneyline": "ganador",
    "team_total": "total del equipo",
    "game_total": "total del partido",
}


@dataclass(frozen=True)
class MagazineBrand:
    brand_name: str = "ABA Signal Pro"
    tagline: str = "Powered by Reparodynamics"
    report_title: str = "Daily Sports Analysis"
    workspace_id: str = "test_01"
    language: str = "en"
    logo_url: str = ""
    disclaimer: str = "Informational content only. Results are not guaranteed."


def lang_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def safe_float(value: Any) -> float | None:
    text = safe_text(value).replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "n/a"}:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def value_text(value: Any, language: str = "en") -> str:
    text = safe_text(value)
    if lang_code(language) != "es" or not text:
        return text
    if text in VALUE_ES:
        return VALUE_ES[text]
    result = text
    replacements = (
        (r"\bFIFA World Cup\b", "Copa Mundial FIFA"),
        (r"\bGame total\b", "Total del partido"),
        (r"\bPoint spread\b", "Hándicap"),
        (r"\bMoneyline\b", "Ganador"),
        (r"\bTeam total\b", "Total del equipo"),
        (r"\bDraw no bet\b", "Empate no apuesta"),
        (r"\bBoth teams to score\b", "Ambos equipos anotan"),
        (r"\bOver\b", "Más de"),
        (r"\bUnder\b", "Menos de"),
        (r"\bNegative at listed odds\b", "Negativo con la cuota actual"),
        (r"\bNeeds grading\b", "Necesita calificación"),
        (r"\bPrice Watch / Research\b", "Seguimiento de precio / investigación"),
        (r"\bResearch / Not Official\b", "Investigación / no oficial"),
    )
    for old, new in replacements:
        result = re.sub(old, new, result, flags=re.I)
    return result


def team_label(team: Any, language: str = "en") -> str:
    text = safe_text(team)
    if lang_code(language) != "es":
        return text
    return COUNTRY_ES.get(text.lower(), text)


def event_text(value: Any, language: str = "en") -> str:
    text = safe_text(value)
    if lang_code(language) != "es" or not text:
        return text
    match = re.search(r"\s+(?:at|vs|v|@)\s+", text, flags=re.I)
    if match:
        first = text[: match.start()].strip()
        second = text[match.end() :].strip()
        return f"{team_label(first, 'es')} vs {team_label(second, 'es')}"
    return value_text(text, "es")


def probability(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    parsed = parsed / 100.0 if parsed > 1.0 else parsed
    return parsed if 0.0 <= parsed <= 1.0 else None


def pct(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:+.1f}%" if signed else f"{value * 100:.1f}%"


def decimal_price(row: Mapping[str, Any]) -> float | None:
    for name in ("decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick"):
        value = safe_float(row.get(name))
        if value is not None and value > 1.0:
            return value
    return None


def market_source(row: Mapping[str, Any]) -> str:
    return safe_text(row.get("odds_source")) or safe_text(row.get("bookmaker")) or safe_text(row.get("sportsbook")) or safe_text(row.get("book"))


def has_verified_odds(row: Mapping[str, Any]) -> bool:
    source = market_source(row).lower()
    return bool(source) and not any(token in source for token in UNVERIFIED_SOURCE_TOKENS) and decimal_price(row) is not None


def model_probability(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for name in ("learned_model_probability", "final_adjusted_probability", "adjusted_model_probability"):
        value = probability(row.get(name))
        if value is not None and value > 0:
            return value, name
    source_label = safe_text(row.get("model_probability_source")).lower()
    if "base_market_probability" in source_label or "market_probability_no_learning" in source_label:
        return None, "market_baseline_only"
    for name in ("model_probability_clean", "model_probability", "probability"):
        value = probability(row.get(name))
        if value is not None and value > 0:
            return value, name
    return None, "missing_model_probability"


def sport_text(value: Any, language: str = "en") -> str:
    text = safe_text(value)
    if lang_code(language) != "es":
        return text
    return SPORT_ES.get(text.lower(), text)


def pick_text(value: Any, language: str = "en") -> str:
    text = safe_text(value)
    if lang_code(language) != "es":
        return text
    return value_text(text, "es")


def tennis_blocked(row: Mapping[str, Any]) -> bool:
    text = " ".join(safe_text(row.get(name)).lower() for name in ("sport", "league", "competition", "market_type", "source_file"))
    return any(token in text for token in TENNIS_TOKENS)


def classify_lane(*, odds_ok: bool, model_prob: float | None, edge: float | None, ev: float | None, tennis: bool = False) -> str:
    if tennis:
        return "no_play"
    if not odds_ok or model_prob is None:
        return "no_play"
    if edge is None or ev is None or edge <= 0 or ev <= 0:
        return "no_play"
    if edge >= 0.02 and ev >= 0.02:
        return "best_play"
    return "watchlist"


def action_label(lane: str, language: str = "en") -> str:
    if lang_code(language) == "es":
        return {"best_play": "Jugar", "watchlist": "Seguir / lean pequeño", "no_play": "No jugar"}.get(lane, "Revisar")
    return {"best_play": "Play", "watchlist": "Watch / small lean", "no_play": "No play"}.get(lane, "Review")


def confidence_tier(model_prob: float | None, language: str = "en") -> str:
    es = lang_code(language) == "es"
    if model_prob is None:
        return "Sin dato" if es else "Unavailable"
    if model_prob >= 0.72:
        return "Alta" if es else "High"
    if model_prob >= 0.62:
        return "Media" if es else "Medium"
    return "Baja / revisar" if es else "Low / review"


def risk_tier(row: Mapping[str, Any], edge: float | None, language: str = "en") -> str:
    es = lang_code(language) == "es"
    price = decimal_price(row)
    if price is None or edge is None or edge <= 0:
        return "Alto" if es else "High"
    if price >= 2.5 or edge < 0.02:
        return "Medio" if es else "Medium"
    return "Bajo" if es else "Low"


def market_read(odds_ok: bool, model_prob: float | None, market_prob: float | None, edge: float | None, language: str = "en") -> str:
    es = lang_code(language) == "es"
    if not odds_ok:
        return "Cuotas no disponibles o no verificadas." if es else "Odds are unavailable or not verified."
    if model_prob is None:
        return "Hay cuota, pero falta una probabilidad independiente del modelo." if es else "Price is available, but no independent model estimate was found."
    if edge is None:
        return "No se pudo calcular la ventaja." if es else "Edge could not be calculated."
    if edge > 0:
        return f"El modelo está {pct(edge, signed=True)} por encima del mercado." if es else f"The model is {pct(edge, signed=True)} above the market."
    return f"El mercado está por encima del modelo por {pct(abs(edge))}." if es else f"The market is above the model by {pct(abs(edge))}."


def game_preview(row: Mapping[str, Any], language: str = "en") -> str:
    es = lang_code(language) == "es"
    event = event_text(row.get("event"), language) or ("este partido" if es else "this matchup")
    sport = safe_text(row.get("sport")).lower()
    pick = pick_text(row.get("prediction") or row.get("tendency"), language)
    if "baseball" in sport or "mlb" in sport:
        fields = (("pitching_matchup", "Duelo de abridores", "Pitching matchup"), ("bullpen_angle", "Bullpen", "Bullpen angle"), ("park_weather_angle", "Parque/clima", "Park/weather"))
    elif "basketball" in sport or "nba" in sport:
        fields = (("pace_angle", "Ritmo", "Pace"), ("rest_angle", "Descanso", "Rest"), ("injury_angle", "Lesiones", "Injuries"))
    elif "soccer" in sport or "football" in sport:
        fields = (("form_angle", "Forma", "Form"), ("home_away_angle", "Local/visita", "Home/away"), ("draw_risk", "Riesgo de empate", "Draw risk"))
    else:
        fields = ()
    notes = []
    for key, es_label, en_label in fields:
        value = safe_text(row.get(key))
        if value:
            notes.append(f"{es_label if es else en_label}: {value_text(value, language)}")
    if notes:
        return " · ".join(notes[:3])
    return f"Vista previa de {event}: selección enfocada en {pick}. Datos contextuales adicionales no disponibles." if es else f"{event} preview: current lean is {pick}. Additional matchup context is unavailable."


def why_it_matters(row: Mapping[str, Any], odds_ok: bool, edge: float | None, language: str = "en") -> str:
    es = lang_code(language) == "es"
    if not odds_ok:
        return "Sin cuota verificada, esta selección queda fuera de publicación." if es else "Without a verified price, this selection stays out of publication."
    if edge is None or edge <= 0:
        return "El precio actual no da ventaja positiva frente al mercado." if es else "The current price does not create a positive edge versus the market."
    return "La selección combina precio verificado y ventaja positiva del modelo." if es else "The selection combines verified price data with a positive model edge."


def enrich_rows(rows: pd.DataFrame | list[Mapping[str, Any]], *, language: str = "en") -> pd.DataFrame:
    frame = pd.DataFrame(rows).copy()
    if frame.empty:
        return frame
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item = row.to_dict()
        price = decimal_price(item)
        odds_ok = has_verified_odds(item)
        model_prob, model_source = model_probability(item)
        market_prob = (1.0 / price) if price and odds_ok else None
        edge = None if model_prob is None or market_prob is None else model_prob - market_prob
        ev = None if model_prob is None or price is None or not odds_ok else model_prob * price - 1.0
        lane = classify_lane(odds_ok=odds_ok, model_prob=model_prob, edge=edge, ev=ev, tennis=tennis_blocked(item))
        enriched = dict(item)
        enriched.update({
            "model_probability": model_prob,
            "model_probability_source": model_source,
            "decimal_price": price,
            "market_probability": market_prob,
            "model_market_edge": edge,
            "expected_value_per_unit": ev,
            "odds_verified": odds_ok,
            "tennis_blocked": tennis_blocked(item),
            "report_lane": lane,
            "publish_ready": lane == "best_play" and bool(safe_text(item.get("proof_id")) or safe_text(item.get("locked_at_utc"))),
            "public_action": action_label(lane, language),
            "confidence_tier": confidence_tier(model_prob, language),
            "risk_tier": risk_tier(item, edge, language),
            "market_read": market_read(odds_ok, model_prob, market_prob, edge, language),
            "game_preview": game_preview(item, language),
            "why_it_matters": why_it_matters(item, odds_ok, edge, language),
            "recommended_action": action_label(lane, language),
            "public_pick": pick_text(item.get("prediction") or item.get("tendency"), language),
            "public_sport": sport_text(item.get("sport"), language),
            "public_event": event_text(item.get("event"), language),
        })
        if enriched["report_lane"] != "best_play":
            enriched["publish_ready"] = False
        records.append(enriched)
    return pd.DataFrame(records)


def grouped_report(cards: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if cards.empty or "report_lane" not in cards.columns:
        empty = pd.DataFrame()
        return {"best_plays": empty, "watchlist": empty, "no_play": cards.copy()}
    return {
        "best_plays": cards[cards["report_lane"].eq("best_play")].copy(),
        "watchlist": cards[cards["report_lane"].eq("watchlist")].copy(),
        "no_play": cards[cards["report_lane"].eq("no_play")].copy(),
    }


def labels(language: str = "en") -> dict[str, str]:
    if lang_code(language) == "es":
        return {"best": "Mejores jugadas", "watch": "Lista de seguimiento", "no_play": "Investigación / aprendizaje", "confidence": "Confianza", "risk": "Riesgo", "market": "Lectura del mercado", "why": "Por qué importa", "action": "Acción recomendada", "analysis": "Análisis"}
    return {"best": "Today’s Best Plays", "watch": "Watchlist / Leans", "no_play": "Research / Learning", "confidence": "Confidence", "risk": "Risk", "market": "Market read", "why": "Why it matters", "action": "Recommended action", "analysis": "Analysis"}


def _brand_from(value: MagazineBrand | Mapping[str, Any]) -> MagazineBrand:
    if isinstance(value, MagazineBrand):
        return value
    allowed = set(MagazineBrand.__dataclass_fields__)
    return MagazineBrand(**{k: v for k, v in dict(value).items() if k in allowed})


def _card_html(row: Mapping[str, Any], language: str, *, technical: bool = False) -> str:
    lab = labels(language)
    title = html.escape(event_text(row.get("public_event") or row.get("event") or "Matchup", language))
    sport = html.escape(sport_text(row.get("public_sport") or row.get("sport") or "Sport", language))
    pick = html.escape(pick_text(row.get("public_pick") or row.get("prediction"), language))
    action = html.escape(value_text(row.get("consumer_action") or row.get("recommended_action"), language))
    parts = [
        '<article class="aba-mag-card">',
        f'<div class="aba-kicker">{sport}</div>',
        f'<h3>{title}</h3>',
        f'<p><b>{html.escape("Selección" if lang_code(language) == "es" else "Pick")}:</b> {pick}</p>',
        f'<p><b>{html.escape(lab["action"])}:</b> {action}</p>',
        f'<p><b>{html.escape(lab["confidence"])}:</b> {html.escape(value_text(row.get("confidence_tier"), language))} · <b>{html.escape(lab["risk"])}:</b> {html.escape(value_text(row.get("risk_tier"), language))}</p>',
        f'<p><b>{html.escape(lab["market"])}:</b> {html.escape(value_text(row.get("market_read"), language))}</p>',
        f'<p><b>{html.escape(lab["why"])}:</b> {html.escape(value_text(row.get("why_it_matters"), language))}</p>',
        f'<p>{html.escape(value_text(row.get("game_preview"), language))}</p>',
    ]
    if technical:
        tech_label = "Modelo" if lang_code(language) == "es" else "Model"
        market_label = "Mercado" if lang_code(language) == "es" else "Market"
        source_label = "Fuente" if lang_code(language) == "es" else "Source"
        proof_label = "Prueba" if lang_code(language) == "es" else "Proof"
        parts.append("<div class='aba-tech'>" f"{tech_label}: {pct(row.get('model_probability'))} | {market_label}: {pct(row.get('market_probability'))} | Edge: {pct(row.get('model_market_edge'), signed=True)} | EV: {pct(row.get('expected_value_per_unit'), signed=True)} | Odds: {html.escape(str(row.get('decimal_price') or 'N/A'))} | {source_label}: {html.escape(market_source(row))} | {proof_label}: {html.escape(safe_text(row.get('proof_id')) or safe_text(row.get('locked_at_utc')) or 'N/A')}" "</div>")
    parts.append("</article>")
    return "\n".join(parts)


def render_consumer_magazine_html(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer") -> str:
    brand = _brand_from(brand)
    language = lang_code(brand.language)
    lab = labels(language)
    groups = grouped_report(cards)
    css = """
<style>.aba-mag{font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.45}.aba-hero{border:1px solid rgba(130,130,130,.35);border-radius:24px;padding:1.1rem 1.3rem;margin:1rem 0}.aba-section{margin:1.4rem 0}.aba-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1rem}.aba-mag-card{border:1px solid rgba(130,130,130,.35);border-radius:20px;padding:1rem;background:rgba(255,255,255,.035)}.aba-kicker{text-transform:uppercase;font-size:.78rem;opacity:.68;font-weight:800;letter-spacing:.04em}.aba-tech{font-size:.82rem;opacity:.72;border-top:1px solid rgba(130,130,130,.25);padding-top:.6rem;margin-top:.6rem}</style>
"""
    parts = [css, '<div class="aba-mag">', '<section class="aba-hero">']
    if brand.logo_url:
        parts.append(f'<img src="{html.escape(brand.logo_url)}" alt="logo" style="max-height:56px">')
    title = value_text(brand.report_title, language)
    tagline = value_text(brand.tagline, language)
    parts += [f"<h1>{html.escape(title)}</h1>", f"<p><b>{html.escape(brand.brand_name)}</b> — {html.escape(tagline)}</p>", "</section>"]
    technical = mode in {"analyst", "proof"}
    for key, title_key in (("best_plays", "best"), ("watchlist", "watch"), ("no_play", "no_play")):
        section = groups[key]
        if section.empty and key != "best_plays":
            continue
        parts.append(f'<section class="aba-section"><h2>{html.escape(lab[title_key])}</h2><div class="aba-grid">')
        if section.empty:
            msg = "No approved plays in this report." if language == "en" else "No hay jugadas aprobadas en este reporte."
            parts.append(f"<p>{html.escape(msg)}</p>")
        else:
            for _, row in section.iterrows():
                parts.append(_card_html(row.to_dict(), language, technical=technical))
        parts.append("</div></section>")
    if brand.disclaimer:
        parts.append(f'<p style="opacity:.7;font-size:.86rem">{html.escape(value_text(brand.disclaimer, language))}</p>')
    parts.append("</div>")
    return "\n".join(parts)


def render_markdown_summary(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer") -> str:
    brand = _brand_from(brand)
    language = lang_code(brand.language)
    lab = labels(language)
    groups = grouped_report(cards)
    lines = [f"# {value_text(brand.report_title, language)}", f"{brand.brand_name} — {value_text(brand.tagline, language)}", ""]
    for key, title_key in (("best_plays", "best"), ("watchlist", "watch"), ("no_play", "no_play")):
        section = groups[key]
        lines += [f"## {lab[title_key]}"]
        if section.empty:
            lines += ["No approved plays." if language == "en" else "No hay jugadas aprobadas."]
        for _, row in section.iterrows():
            lines += [
                f"- **{event_text(row.get('public_event') or row.get('event'), language)}** — {pick_text(row.get('public_pick') or row.get('prediction'), language)}",
                f"  - {lab['action']}: {value_text(row.get('consumer_action') or row.get('recommended_action'), language)}",
                f"  - {lab['market']}: {value_text(row.get('market_read'), language)}",
            ]
        lines.append("")
    return "\n".join(lines)


def cards_to_json(cards: pd.DataFrame) -> str:
    return json.dumps(cards.fillna("").to_dict("records"), ensure_ascii=False, indent=2)
