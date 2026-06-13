import math
import os
import unicodedata
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Autonomous Betting Agent", "Español": "Agente Autónomo de Pronósticos"},
    "caption": {
        "English": "Paste a provider key, type one game, and let the agent search across sports, rank likely outcomes, estimate scorelines or margins, and explain confidence.",
        "Español": "Pega una clave del proveedor, escribe un partido y deja que el agente busque en varios deportes, ordene resultados, estime marcadores o márgenes y explique la confianza.",
    },
    "token": {"English": "The Odds API key", "Español": "Clave de The Odds API"},
    "token_help": {"English": "Each user can paste their own key. It is used only for this browser session unless the app owner configures one separately.", "Español": "Cada usuario puede pegar su propia clave. Se usa solo en esta sesión del navegador salvo que el dueño configure una aparte."},
    "game": {"English": "Game", "Español": "Partido"},
    "game_help": {"English": "Examples: Mexico vs South Korea, Lakers vs Celtics, Chiefs vs Bills, Yankees vs Dodgers, Djokovic vs Alcaraz, India vs Australia", "Español": "Ejemplos: México vs Corea del Sur, Lakers vs Celtics, Chiefs vs Bills, Yankees vs Dodgers, Djokovic vs Alcaraz, India vs Australia"},
    "competition": {"English": "Sport / competition", "Español": "Deporte / competición"},
    "advanced": {"English": "Advanced settings", "Español": "Configuración avanzada"},
    "market_regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "host_note": {"English": "Canada, Mexico, and the USA are FIFA 2026 host countries. The selector below is for bookmaker market regions, not host countries.", "Español": "Canadá, México y Estados Unidos son países sede de FIFA 2026. El selector abajo es para mercados de casas de apuestas, no países sede."},
    "team1": {"English": "Team 1 override", "Español": "Equipo 1 manual"},
    "team2": {"English": "Team 2 override", "Español": "Equipo 2 manual"},
    "max_feeds": {"English": "Max feeds to scan", "Español": "Máximo de fuentes a revisar"},
    "max_events": {"English": "Max games per feed", "Español": "Máximo de partidos por fuente"},
    "nearest": {"English": "Show closest games if no exact match", "Español": "Mostrar partidos cercanos si no hay coincidencia exacta"},
    "run": {"English": "Run autonomous agent", "Español": "Ejecutar agente autónomo"},
    "loading": {"English": "Loading and ranking sport feeds", "Español": "Cargando y clasificando fuentes"},
    "searching": {"English": "Searching games and building report", "Español": "Buscando partidos y construyendo reporte"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "could_not_load": {"English": "Could not load sport feeds", "Español": "No se pudieron cargar las fuentes"},
    "scanned": {"English": "Scanned", "Español": "Revisó"},
    "feeds_found": {"English": "feeds and found", "Español": "fuentes y encontró"},
    "games_market": {"English": "games with market data.", "Español": "partidos con datos de mercado."},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "no_match": {"English": "No exact team match found. The provider may not have this game yet, or the teams may be listed under different names.", "Español": "No se encontró coincidencia exacta. Puede que el proveedor todavía no tenga este partido o que los equipos aparezcan con otros nombres."},
    "closest": {"English": "Closest games found", "Español": "Partidos más cercanos"},
    "verdict": {"English": "Agent verdict", "Español": "Veredicto del agente"},
    "favorite": {"English": "Favorite", "Español": "Favorito"},
    "confidence": {"English": "Confidence", "Español": "Confianza"},
    "top_score": {"English": "Top score / margin", "Español": "Marcador / margen principal"},
    "draw_risk": {"English": "Draw risk", "Español": "Riesgo de empate"},
    "high": {"English": "High", "Español": "Alta"},
    "medium": {"English": "Medium", "Español": "Media"},
    "low": {"English": "Low", "Español": "Baja"},
    "start": {"English": "Start", "Español": "Inicio"},
    "market_view": {"English": "Market probabilities", "Español": "Probabilidades de mercado"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg price", "Español": "Precio promedio"},
    "probability": {"English": "No-vig probability", "Español": "Probabilidad sin margen"},
    "sources": {"English": "Books", "Español": "Casas"},
    "scorelines": {"English": "Most likely scorelines / margins", "Español": "Marcadores / márgenes más probables"},
    "score": {"English": "Score / margin", "Español": "Marcador / margen"},
    "spread": {"English": "Read", "Español": "Lectura"},
    "score_prob": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "why": {"English": "Why the agent says this", "Español": "Por qué el agente dice esto"},
    "cycle": {"English": "ARA cycle", "Español": "Ciclo ARA"},
    "research_note": {"English": "Research estimate only. This is market-based until team stats, injuries, lineups, weather, and news providers are added.", "Español": "Estimación de investigación solamente. Está basada en mercado hasta agregar estadísticas, lesiones, alineaciones, clima y noticias."},
}


def t(key: str) -> str:
    return TEXT[key][language]


st.title(t("title"))
st.caption(t("caption"))

COUNTRY_ALIASES = {
    "mexico": ["mexico", "méxico", "mexican", "el tri"],
    "south korea": ["south korea", "korea republic", "republic of korea", "korea", "corea del sur"],
    "usa": ["usa", "united states", "usmnt", "united states of america", "estados unidos"],
    "canada": ["canada", "canadá", "canadian"],
    "england": ["england", "english", "inglaterra"],
    "brazil": ["brazil", "brasil"],
    "germany": ["germany", "deutschland", "alemania"],
    "spain": ["spain", "españa"],
    "argentina": ["argentina"],
    "france": ["france", "francia"],
    "japan": ["japan", "japon", "japón"],
    "india": ["india"],
    "australia": ["australia"],
    "new zealand": ["new zealand", "nueva zelanda"],
    "south africa": ["south africa", "sudafrica", "sudáfrica"],
}

TEAM_SPORT_HINTS = {
    "lakers": "nba", "celtics": "nba", "warriors": "nba", "knicks": "nba", "bulls": "nba", "heat": "nba", "mavericks": "nba", "nuggets": "nba", "suns": "nba", "bucks": "nba", "spurs": "nba", "clippers": "nba", "76ers": "nba", "sixers": "nba", "timberwolves": "nba", "thunder": "nba",
    "chiefs": "nfl", "bills": "nfl", "cowboys": "nfl", "eagles": "nfl", "ravens": "nfl", "packers": "nfl", "patriots": "nfl", "steelers": "nfl", "49ers": "nfl", "niners": "nfl", "bengals": "nfl", "lions": "nfl", "dolphins": "nfl", "jets": "nfl", "raiders": "nfl", "broncos": "nfl", "chargers": "nfl", "rams": "nfl", "seahawks": "nfl", "vikings": "nfl",
    "yankees": "mlb", "dodgers": "mlb", "red sox": "mlb", "mets": "mlb", "cubs": "mlb", "braves": "mlb", "astros": "mlb", "padres": "mlb", "phillies": "mlb", "giants": "mlb", "cardinals": "mlb", "blue jays": "mlb", "orioles": "mlb", "mariners": "mlb",
    "maple leafs": "nhl", "bruins": "nhl", "rangers": "nhl", "canadiens": "nhl", "oilers": "nhl", "panthers": "nhl", "avalanche": "nhl", "golden knights": "nhl", "lightning": "nhl", "penguins": "nhl", "capitals": "nhl", "kings": "nhl", "stars": "nhl",
    "arsenal": "soccer", "chelsea": "soccer", "liverpool": "soccer", "manchester united": "soccer", "man city": "soccer", "real madrid": "soccer", "barcelona": "soccer", "psg": "soccer", "bayern": "soccer", "inter miami": "soccer", "club america": "soccer", "chivas": "soccer", "cruz azul": "soccer", "tigres": "soccer",
    "djokovic": "tennis", "alcaraz": "tennis", "sinner": "tennis", "nadal": "tennis", "federer": "tennis", "swiatek": "tennis", "sabalenka": "tennis", "gauff": "tennis",
    "india": "cricket", "australia": "cricket", "england": "cricket", "pakistan": "cricket", "new zealand": "cricket", "south africa": "cricket",
}

SPORT_SYNONYMS = {
    "auto": [],
    "soccer": ["soccer", "fifa", "football", "world cup", "international", "concacaf", "uefa", "epl", "premier", "la liga", "serie a", "bundesliga", "liga mx", "mls", "champions league", "europa"],
    "nba": ["nba", "basketball", "ncaab", "college basketball", "wnba", "euroleague"],
    "nfl": ["nfl", "americanfootball", "american football", "ncaaf", "college football", "cfl"],
    "mlb": ["mlb", "baseball", "npb", "kbo"],
    "nhl": ["nhl", "hockey", "icehockey", "ice hockey", "shl"],
    "tennis": ["tennis", "atp", "wta", "grand slam", "wimbledon", "us open", "australian open", "french open"],
    "mma": ["mma", "ufc", "bellator", "mixed martial"],
    "boxing": ["boxing", "boxeo"],
    "cricket": ["cricket", "ipl", "bbl", "psl", "test cricket", "odi", "t20"],
    "rugby": ["rugby", "rugby union", "rugby league", "nrl", "super rugby"],
    "aussierules": ["aussie rules", "aussierules", "afl", "australian rules"],
    "golf": ["golf", "pga", "liv golf", "masters", "ryder cup"],
    "motorsport": ["motorsport", "formula 1", "formula1", "f1", "nascar", "indycar", "motogp"],
    "darts": ["darts", "pdc"],
    "snooker": ["snooker"],
    "lacrosse": ["lacrosse", "pll", "nll"],
    "volleyball": ["volleyball", "voleibol"],
    "handball": ["handball", "balonmano"],
    "esports": ["esports", "cs2", "csgo", "counter strike", "league of legends", "lol", "dota", "valorant", "call of duty", "cod", "overwatch", "starcraft"],
}

POPULAR_HINTS = ["nba", "nfl", "mlb", "nhl", "soccer", "epl", "mls", "tennis", "mma", "ufc", "baseball", "basketball", "football", "hockey", "cricket", "rugby", "golf", "motorsport", "esports", "boxing"]


def read_provider_token() -> str:
    try:
        return str(st.secrets.get("THE_ODDS_API_KEY", ""))
    except Exception:
        return os.getenv("THE_ODDS_API_KEY", "")


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def parse_game(text: str) -> tuple[str, str]:
    raw = text.strip()
    padded = f" {raw.lower()} "
    for sep in [" vs ", " v ", " versus ", " at ", " @ ", " contra "]:
        if sep in padded:
            left, right = padded.split(sep, 1)
            return left.strip().title(), right.strip().title()
    return "", ""


def aliases(value: str) -> list[str]:
    base = clean(value)
    values = {base}
    for key, alias_list in COUNTRY_ALIASES.items():
        if base == clean(key) or base in [clean(alias) for alias in alias_list]:
            values.update(clean(alias) for alias in alias_list)
    return [item for item in values if item]


def is_known_country(value: str) -> bool:
    base = clean(value)
    return any(base == clean(key) or base in [clean(alias) for alias in vals] for key, vals in COUNTRY_ALIASES.items())


def infer_sport_hints(text: str, team_one: str, team_two: str) -> set[str]:
    haystack = clean(f"{text} {team_one} {team_two}")
    hints = set()
    for sport, words in SPORT_SYNONYMS.items():
        if any(clean(word) in haystack for word in words):
            hints.add(sport)
    for team, sport in TEAM_SPORT_HINTS.items():
        if clean(team) in haystack:
            hints.add(sport)
    if is_known_country(team_one) and is_known_country(team_two):
        hints.add("soccer")
    return hints


def match_score(query: str, candidate: str) -> float:
    query = clean(query)
    candidate = clean(candidate)
    if not query or not candidate:
        return 0.0
    if query in candidate or candidate in query:
        return 1.0
    return SequenceMatcher(None, query, candidate).ratio()


def best_name_score(query: str, names: list[str]) -> float:
    if not query:
        return 1.0
    return max(match_score(alias, name) for alias in aliases(query) for name in names)


def event_score(item, team_one: str, team_two: str) -> float:
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    one_score = best_name_score(team_one, names)
    two_score = best_name_score(team_two, names)
    return (one_score + two_score) / 2.0 if team_one and team_two else max(one_score, two_score)


def is_outright_feed(sport_item) -> bool:
    text = clean(f"{sport_item.key} {sport_item.title} {sport_item.description}")
    return any(word in text for word in ["winner", "championship", "outright"])


def sport_kind(item) -> str:
    text = clean(f"{getattr(item, 'sport_key', '')} {getattr(item, 'sport_title', '')}")
    if any(x in text for x in ["soccer", "fifa", "epl", "mls"]):
        return "soccer"
    if any(x in text for x in ["basketball", "nba", "ncaab", "wnba"]):
        return "basketball"
    if any(x in text for x in ["americanfootball", "nfl", "ncaaf", "cfl"]):
        return "football"
    if any(x in text for x in ["baseball", "mlb", "npb", "kbo"]):
        return "baseball"
    if any(x in text for x in ["icehockey", "hockey", "nhl"]):
        return "hockey"
    if "tennis" in text:
        return "tennis"
    if any(x in text for x in ["mma", "ufc", "boxing"]):
        return "fight"
    if "cricket" in text:
        return "cricket"
    if "rugby" in text:
        return "rugby"
    if any(x in text for x in ["aussierules", "afl"]):
        return "aussierules"
    if any(x in text for x in ["golf", "motorsport", "formula", "nascar", "darts", "snooker", "esports"]):
        return "field"
    return "general"


def sport_score(sport_item, competition: str, team_one: str, team_two: str) -> float:
    haystack = clean(f"{sport_item.key} {sport_item.group} {sport_item.title} {sport_item.description}")
    score_value = -30.0 if is_outright_feed(sport_item) else 0.0
    hints = infer_sport_hints(competition, team_one, team_two)
    if not hints or "auto" in hints:
        for idx, hint in enumerate(POPULAR_HINTS):
            if hint in haystack:
                score_value += max(1.0, 8.0 - idx * 0.25)
    for hint in hints:
        for synonym in SPORT_SYNONYMS.get(hint, [hint]):
            if clean(synonym) in haystack:
                score_value += 10.0
    for word in [clean(w) for w in competition.split() if clean(w) and clean(w) != "auto"]:
        if word in haystack:
            score_value += 3.0
    if is_known_country(team_one) and is_known_country(team_two):
        for word in ["international", "world", "fifa", "cup", "friendlies", "concacaf", "uefa"]:
            if word in haystack:
                score_value += 7.0
        for word in ["serie", "division", "league", "liga", "campeonato", "superleague"]:
            if word in haystack and "international" not in haystack and "world" not in haystack:
                score_value -= 4.0
    return score_value


def explain_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "provider token was rejected" if not IS_ES else "la clave fue rechazada"
    if status == 422:
        return "market not offered in selected regions" if not IS_ES else "mercado no disponible en esas regiones"
    if status == 429:
        return "provider quota or rate limit reached" if not IS_ES else "se alcanzó la cuota o límite"
    return "provider request failed" if not IS_ES else "falló la solicitud"


def outcome_prob(item, name: str) -> float | None:
    for outcome in item.outcomes:
        if clean(outcome.name) == clean(name):
            return outcome.normalized_probability
    return None


def draw_probability(item) -> float | None:
    for outcome in item.outcomes:
        if clean(outcome.name) in ["draw", "empate"]:
            return outcome.normalized_probability
    return None


def poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def grid_scorelines(home_xg: float, away_xg: float, max_goals: int = 7) -> list[dict]:
    rows = []
    for h in range(max_goals + 1):
        hp = poisson(h, home_xg)
        for a in range(max_goals + 1):
            rows.append({"home": h, "away": a, "prob": hp * poisson(a, away_xg)})
    return sorted(rows, key=lambda row: row["prob"], reverse=True)


def one_x_two_from_xg(home_xg: float, away_xg: float) -> tuple[float, float, float]:
    home_win = draw = away_win = 0.0
    for row in grid_scorelines(home_xg, away_xg):
        if row["home"] > row["away"]:
            home_win += row["prob"]
        elif row["home"] == row["away"]:
            draw += row["prob"]
        else:
            away_win += row["prob"]
    total = home_win + draw + away_win
    return home_win / total, draw / total, away_win / total


def fit_xg(home_prob: float, draw_prob: float | None, away_prob: float) -> tuple[float, float]:
    if draw_prob is None:
        edge = max(-0.45, min(0.45, home_prob - 0.5))
        home_xg = 1.30 + edge * 1.25
        return max(0.25, home_xg), max(0.25, 2.55 - home_xg)
    best = (999.0, 1.3, 1.1)
    for h in [x / 10 for x in range(4, 36)]:
        for a in [x / 10 for x in range(4, 36)]:
            hp, dp, ap = one_x_two_from_xg(h, a)
            error = (hp - home_prob) ** 2 + (dp - draw_prob) ** 2 + (ap - away_prob) ** 2
            if error < best[0]:
                best = (error, h, a)
    return best[1], best[2]


def win_margin_rows(item, fav_prob: float, dog_prob: float) -> list[dict]:
    kind = sport_kind(item)
    fav = item.favorite
    dog = next((o.name for o in item.outcomes if clean(o.name) not in [clean(fav), "draw"]), "Opponent")
    if kind == "tennis":
        fav_bands = [("2-0 sets", 0.62), ("2-1 sets", 0.38)]
        dog_bands = [("2-1 sets", 0.55), ("2-0 sets", 0.45)]
    elif kind in ["baseball", "hockey", "soccer"]:
        fav_bands = [("by 1", 0.55), ("by 2", 0.28), ("by 3+", 0.17)]
        dog_bands = [("by 1", 0.58), ("by 2", 0.27), ("by 3+", 0.15)]
    elif kind == "basketball":
        fav_bands = [("by 1-5", 0.32), ("by 6-10", 0.33), ("by 11+", 0.35)]
        dog_bands = [("by 1-5", 0.42), ("by 6-10", 0.33), ("by 11+", 0.25)]
    elif kind == "football":
        fav_bands = [("by 1-3", 0.33), ("by 4-7", 0.34), ("by 8+", 0.33)]
        dog_bands = [("by 1-3", 0.42), ("by 4-7", 0.33), ("by 8+", 0.25)]
    elif kind in ["rugby", "aussierules"]:
        fav_bands = [("by 1-7", 0.34), ("by 8-14", 0.31), ("by 15+", 0.35)]
        dog_bands = [("by 1-7", 0.45), ("by 8-14", 0.30), ("by 15+", 0.25)]
    elif kind == "cricket":
        fav_bands = [("narrow win", 0.40), ("solid win", 0.38), ("dominant win", 0.22)]
        dog_bands = [("narrow win", 0.48), ("solid win", 0.34), ("dominant win", 0.18)]
    elif kind == "fight":
        fav_bands = [("decision", 0.38), ("finish", 0.42), ("late result", 0.20)]
        dog_bands = [("decision", 0.42), ("finish", 0.38), ("late result", 0.20)]
    elif kind == "field":
        fav_bands = [("wins event", 0.55), ("top contender", 0.30), ("upset field risk", 0.15)]
        dog_bands = [("field/upset path", 0.55), ("close contender", 0.30), ("longshot path", 0.15)]
    else:
        fav_bands = [("close win", 0.45), ("medium win", 0.35), ("comfortable win", 0.20)]
        dog_bands = [("close win", 0.50), ("medium win", 0.32), ("comfortable win", 0.18)]
    rows = []
    for label, weight in fav_bands:
        rows.append({t("score"): f"{fav} {label}", t("spread"): f"{fav} {label}", t("score_prob"): f"{fav_prob * weight:.1%}"})
    for label, weight in dog_bands:
        rows.append({t("score"): f"{dog} {label}", t("spread"): f"{dog} {label}", t("score_prob"): f"{dog_prob * weight:.1%}"})
    return sorted(rows, key=lambda row: float(row[t("score_prob")].strip("%")), reverse=True)[:6]


def confidence_value(match: float, item) -> tuple[str, float]:
    top = item.outcomes[0].normalized_probability
    second = item.outcomes[1].normalized_probability if len(item.outcomes) > 1 else 0.0
    gap = max(0.0, top - second)
    books = min(1.0, item.bookmaker_count / 10.0)
    value = 0.45 * match + 0.30 * books + 0.25 * min(gap / 0.25, 1.0)
    if top < 0.50:
        value = min(value, 0.74)
    if value >= 0.75:
        return t("high"), value
    if value >= 0.55:
        return t("medium"), value
    return t("low"), value


def show_event(item, match: float | None = None, scan_summary: str = "") -> None:
    home_prob = outcome_prob(item, item.home_team)
    away_prob = outcome_prob(item, item.away_team)
    draw_prob = draw_probability(item)
    if home_prob is None or away_prob is None:
        st.warning("Could not map market outcomes to home/away teams." if not IS_ES else "No se pudieron mapear los resultados del mercado.")
        return

    conf_label, conf_value = confidence_value(match or 0.0, item)
    draw_text = f"{draw_prob:.1%}" if draw_prob is not None else "N/A"
    fav_prob = item.outcomes[0].normalized_probability
    dog_prob = next((o.normalized_probability for o in item.outcomes if clean(o.name) not in [clean(item.favorite), "draw"]), 1.0 - fav_prob)

    if draw_prob is not None:
        home_xg, away_xg = fit_xg(home_prob, draw_prob, away_prob)
        scores = grid_scorelines(home_xg, away_xg)[:8]
        top_summary = f"{scores[0]['home']}-{scores[0]['away']}"
        score_rows = []
        for row in scores:
            margin = row["home"] - row["away"]
            if margin > 0:
                read = f"{item.home_team} {t('by')} {margin}"
            elif margin < 0:
                read = f"{item.away_team} {t('by')} {abs(margin)}"
            else:
                read = t("draw")
            score_rows.append({t("score"): f"{row['home']}-{row['away']}", t("spread"): read, t("score_prob"): f"{row['prob']:.1%}"})
        model_note = f"xG model: {item.home_team} {home_xg:.2f}, {item.away_team} {away_xg:.2f}"
    else:
        score_rows = win_margin_rows(item, fav_prob, dog_prob)
        top_summary = score_rows[0][t("score")]
        model_note = "Margin model: estimated from moneyline strength only" if not IS_ES else "Modelo de margen: estimado solo desde la fuerza del mercado"

    st.subheader(f"{item.away_team} at {item.home_team}")
    st.success(f"{t('verdict')}: {item.favorite} — {item.favorite_probability:.1%}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("favorite"), item.favorite)
    c2.metric(t("confidence"), f"{conf_label} ({conf_value:.0%})")
    c3.metric(t("top_score"), top_summary)
    c4.metric(t("draw_risk"), draw_text)

    st.write(f"{t('start')}: {item.commence_time}")
    st.write(model_note)

    st.write(t("market_view"))
    st.dataframe([{t("outcome"): o.name, t("avg_price"): round(o.average_price, 3), t("probability"): f"{o.normalized_probability:.1%}", t("sources"): o.source_count} for o in item.outcomes], use_container_width=True, hide_index=True)

    st.write(t("scorelines"))
    st.dataframe(score_rows, use_container_width=True, hide_index=True)

    with st.expander(t("why"), expanded=True):
        st.write(f"- {item.bookmaker_count} market sources were averaged." if not IS_ES else f"- Se promediaron {item.bookmaker_count} fuentes de mercado.")
        st.write(f"- Team-match confidence: {(match or 0):.0%}." if not IS_ES else f"- Confianza de coincidencia: {(match or 0):.0%}.")
        if draw_prob is not None and draw_prob >= 0.25:
            st.write("- Draw risk is meaningful, so exact-score confidence should stay cautious." if not IS_ES else "- El riesgo de empate es importante, por eso la confianza del marcador debe ser cautelosa.")
        if draw_prob is None:
            st.write("- Margin bands are approximate because this version only uses moneyline markets, not spread or total markets." if not IS_ES else "- Los márgenes son aproximados porque esta versión usa moneyline, no líneas de spread o totales.")
        st.write("- This is market-implied research, not a guaranteed prediction." if not IS_ES else "- Esto es investigación basada en mercado, no una predicción garantizada.")

    with st.expander(t("cycle")):
        st.write(f"- TEST: {scan_summary}")
        st.write("- DETECT: inferred sport hints, matched team aliases, and ignored obvious futures/outright feeds." if not IS_ES else "- DETECTAR: infirió deporte, coincidió alias e ignoró fuentes de futuros.")
        st.write("- REPAIR: normalized market probabilities and selected a sport-appropriate score/margin model." if not IS_ES else "- REPARAR: normalizó probabilidades y seleccionó un modelo de marcador/margen según el deporte.")
        st.write("- VERIFY: reported confidence, market depth, draw risk, and uncertainty." if not IS_ES else "- VERIFICAR: reportó confianza, profundidad de mercado, riesgo de empate e incertidumbre.")
    st.caption(t("research_note"))


saved_token = read_provider_token()
entry_token = st.text_input(t("token"), value="", type="password")
provider_token = entry_token.strip() or saved_token
if not provider_token:
    st.info(t("token_help"))
    st.stop()

game_text = st.text_input(t("game"), "Mexico vs South Korea", help=t("game_help"))
default_one, default_two = parse_game(game_text)
competition = st.text_input(t("competition"), "auto")

with st.expander(t("advanced")):
    st.caption(t("host_note"))
    team_one = st.text_input(t("team1"), default_one)
    team_two = st.text_input(t("team2"), default_two)
    selected_regions = st.multiselect(t("market_regions"), ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "uk", "eu", "au"])
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=120, value=40, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=30, step=1)
    show_nearest = st.checkbox(t("nearest"), value=True)

team_one = team_one or default_one
team_two = team_two or default_two

if st.button(t("run"), type="primary"):
    if not selected_regions:
        st.error(t("choose_region"))
        st.stop()
    if not team_one and not team_two:
        st.error("Enter a game like Mexico vs South Korea, Lakers vs Celtics, or India vs Australia." if not IS_ES else "Escribe un partido como México vs Corea del Sur, Lakers vs Celtics o India vs Australia.")
        st.stop()

    with st.spinner(t("loading")):
        try:
            sports = list_sports(provider_token, include_all=False)
        except Exception as exc:
            st.error(f"{t('could_not_load')}: {explain_error(exc)}")
            st.stop()

    ranked = sorted(sports, key=lambda item: sport_score(item, competition, team_one, team_two), reverse=True)
    candidate_sports = [sport for sport in ranked if not is_outright_feed(sport)][: int(max_feeds)]
    region_text = ",".join(selected_regions)
    all_results = []
    skipped = []

    with st.spinner(t("searching")):
        for sport_item in candidate_sports:
            try:
                all_results.extend(scan_market(provider_token, sport_key=sport_item.key, regions=region_text, max_events=int(max_events)))
            except Exception as exc:
                skipped.append((sport_item.title, explain_error(exc)))

    scored = sorted([(event_score(item, team_one, team_two), item) for item in all_results], key=lambda pair: pair[0], reverse=True)
    matches = [(score, item) for score, item in scored if score >= 0.55]
    scan_summary = f"{t('scanned')} {len(candidate_sports)} {t('feeds_found')} {len(all_results)} {t('games_market')}"

    if matches:
        show_event(matches[0][1], matches[0][0], scan_summary)
        if len(matches) > 1:
            with st.expander("Other matching games" if not IS_ES else "Otros partidos coincidentes"):
                for score, item in matches[1:5]:
                    show_event(item, score, scan_summary)
    else:
        st.info(t("no_match"))
        if show_nearest and scored:
            st.write(t("closest"))
            for score, item in scored[:3]:
                show_event(item, score, scan_summary)
        else:
            st.write(t("try_terms"))

    with st.expander(t("diagnostics")):
        st.write(scan_summary)
        st.write("Sport hints: " + ", ".join(sorted(infer_sport_hints(competition, team_one, team_two)) or ["auto"]))
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:20]:
                st.write(f"- {title}: {reason}")
