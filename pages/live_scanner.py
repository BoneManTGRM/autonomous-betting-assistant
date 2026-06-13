import os
import unicodedata
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Live Market Scanner", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Live Market Command Center", "Español": "Centro de Comando de Mercado en Vivo"},
    "caption": {
        "English": "Scan across sports and find the teams with the highest market-implied chance to win. Leave the team filter blank for all sports, or enter one team/player to hunt for only that name.",
        "Español": "Escanea varios deportes y encuentra los equipos con mayor probabilidad de ganar según el mercado. Deja el filtro vacío para todos los deportes o escribe un equipo/jugador para buscar solo ese nombre.",
    },
    "token": {"English": "Provider access token", "Español": "Clave de acceso del proveedor"},
    "token_help": {"English": "Paste your own provider access token. It is used only for this browser session unless the app owner configures one separately.", "Español": "Pega tu propia clave. Se usa solo en esta sesión del navegador salvo que el dueño configure una aparte."},
    "mode": {"English": "Scan mode", "Español": "Modo de escaneo"},
    "smart": {"English": "Smart dashboard", "Español": "Panel inteligente"},
    "single": {"English": "Single feed", "Español": "Una fuente"},
    "objective": {"English": "Scanner objective", "Español": "Objetivo del escáner"},
    "highest_win": {"English": "Find highest team win chance", "Español": "Encontrar mayor probabilidad de victoria"},
    "market_command": {"English": "Full market command center", "Español": "Centro completo de mercado"},
    "regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "regions_help": {"English": "The Odds API regions: us, us2, uk, eu, au. These are bookmaker markets, not event host countries.", "Español": "Regiones de The Odds API: us, us2, uk, eu, au. Son mercados de casas de apuestas, no países sede del evento."},
    "sport_search": {"English": "Sport / league search", "Español": "Buscar deporte / liga"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo/jugador"},
    "team_filter_help": {"English": "Optional. Leave blank for all sports. Example: Mexico, Lakers, Djokovic, Yankees", "Español": "Opcional. Déjalo vacío para todos los deportes. Ejemplo: México, Lakers, Djokovic, Yankees"},
    "max_feeds": {"English": "Max feeds to scan", "Español": "Máximo de fuentes a revisar"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "min_fav": {"English": "Minimum team win probability", "Español": "Probabilidad mínima de victoria"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "sport_feed": {"English": "Sport feed", "Español": "Fuente deportiva"},
    "scan": {"English": "Scan live markets", "Español": "Escanear mercados en vivo"},
    "no_games": {"English": "No games with usable market data were returned.", "Español": "No se devolvieron partidos con datos de mercado utilizables."},
    "no_exact": {"English": "No exact matches were found for that filter. Showing the highest-probability games found instead, plus closest name matches when available.", "Español": "No se encontraron coincidencias exactas para ese filtro. Mostrando los juegos con mayor probabilidad encontrados y las coincidencias más cercanas cuando existan."},
    "start": {"English": "Start", "Español": "Inicio"},
    "most_likely": {"English": "Most likely", "Español": "Más probable"},
    "team_pick": {"English": "Team win pick", "Español": "Equipo con mayor opción"},
    "win_probability": {"English": "Win probability", "Español": "Probabilidad de victoria"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg price", "Español": "Precio promedio"},
    "best_price": {"English": "Best price", "Español": "Mejor precio"},
    "best_book": {"English": "Best book", "Español": "Mejor casa"},
    "range": {"English": "Book spread", "Español": "Diferencia entre casas"},
    "probability": {"English": "Probability", "Español": "Probabilidad"},
    "books": {"English": "Books", "Español": "Casas"},
    "scorelines": {"English": "Likely scorelines / margins", "Español": "Marcadores / márgenes probables"},
    "score": {"English": "Score / margin", "Español": "Marcador / margen"},
    "read": {"English": "Read", "Español": "Lectura"},
    "estimated": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "dashboard": {"English": "Scanner dashboard", "Español": "Panel del escáner"},
    "events": {"English": "Events found", "Español": "Eventos encontrados"},
    "feeds": {"English": "Feeds scanned", "Español": "Fuentes revisadas"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "highest_team": {"English": "Highest team win chance", "Español": "Mayor probabilidad de victoria"},
    "by_sport": {"English": "Best by sport", "Español": "Mejor por deporte"},
    "closest_filter": {"English": "Closest filter matches", "Español": "Coincidencias más cercanas"},
    "strongest": {"English": "Strongest favorites", "Español": "Favoritos más fuertes"},
    "balanced": {"English": "Closest markets", "Español": "Mercados más cerrados"},
    "draw_heavy": {"English": "Highest draw risk", "Español": "Mayor riesgo de empate"},
    "disagreement": {"English": "Bookmaker disagreement", "Español": "Desacuerdo entre casas"},
    "all_games": {"English": "All ranked games", "Español": "Todos los juegos ordenados"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda de mercado"},
    "ara_read": {"English": "ARA read", "Español": "Lectura ARA"},
    "quality": {"English": "Market quality", "Español": "Calidad del mercado"},
    "overround": {"English": "Overround", "Español": "Margen del mercado"},
    "download": {"English": "Download ranked scan CSV", "Español": "Descargar CSV del escaneo"},
    "note": {"English": "Market-only scan. This finds the team with the highest market-implied win chance, not a guaranteed winner.", "Español": "Escaneo solo de mercado. Encuentra el equipo con mayor probabilidad implícita de ganar, no un ganador garantizado."},
}

COUNTRY_ALIASES = {
    "mexico": ["mexico", "méxico", "mex", "el tri", "mexico national", "méxico national"],
    "canada": ["canada", "canadá", "can"],
    "usa": ["usa", "united states", "united states of america", "usmnt", "estados unidos"],
    "brazil": ["brazil", "brasil"],
    "argentina": ["argentina"],
    "england": ["england", "inglaterra"],
    "france": ["france", "francia"],
    "germany": ["germany", "alemania", "deutschland"],
    "spain": ["spain", "españa"],
    "japan": ["japan", "japon", "japón"],
    "south korea": ["south korea", "korea republic", "republic of korea", "corea del sur", "korea"],
}


def t(key: str) -> str:
    entry = TEXT.get(key)
    if not entry:
        return key.replace("_", " ").title()
    return entry.get(language) or entry.get("English") or key.replace("_", " ").title()


st.title(t("title"))
st.caption(t("caption"))

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
POPULAR_TERMS = [
    "nba", "nfl", "mlb", "nhl", "soccer", "fifa", "world cup", "international", "friendlies", "concacaf",
    "tennis", "ufc", "mma", "boxing", "cricket", "rugby", "golf", "formula", "nascar", "darts", "snooker",
    "esports", "volleyball", "handball", "lacrosse",
]


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def pct(value) -> str:
    return "" if value is None else f"{value:.1%}"


def filter_aliases(value: str) -> list[str]:
    base = clean(value)
    aliases = {base}
    for key, values in COUNTRY_ALIASES.items():
        cleaned_values = [clean(item) for item in values]
        if base == clean(key) or base in cleaned_values:
            aliases.add(clean(key))
            aliases.update(cleaned_values)
    return [alias for alias in aliases if alias]


def is_country_filter(value: str) -> bool:
    base = clean(value)
    return any(base == clean(key) or base in [clean(item) for item in values] for key, values in COUNTRY_ALIASES.items())


def safe_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "Provider key was rejected. Check the key and plan access." if not IS_ES else "La clave del proveedor fue rechazada. Revisa la clave y el acceso del plan."
    if status == 422:
        return "This feed is not available for the selected market regions. Try fewer regions or another feed." if not IS_ES else "Esta fuente no está disponible para las regiones seleccionadas. Prueba menos regiones u otra fuente."
    if status == 429:
        return "Provider quota or rate limit reached. Wait or use another key." if not IS_ES else "Se alcanzó la cuota o límite del proveedor. Espera o usa otra clave."
    return "Provider request failed. Try another feed or region." if not IS_ES else "Falló la solicitud al proveedor. Prueba otra fuente o región."


def is_outright_feed(sport) -> bool:
    text = clean(f"{sport.key} {sport.title} {sport.description}")
    return any(word in text for word in ["winner", "championship", "outright"])


def sport_relevance(sport, query: str, team_filter: str = "") -> float:
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    terms = [clean(term) for term in query.split() if clean(term) and clean(term) != "auto"]
    score = -25.0 if is_outright_feed(sport) else 0.0

    if not terms:
        for index, term in enumerate(POPULAR_TERMS):
            if clean(term) in text:
                score += max(1.0, 10.0 - index * 0.25)
    else:
        for term in terms:
            if term in text:
                score += 12.0
            else:
                score += SequenceMatcher(None, term, text).ratio()

    if team_filter.strip() and is_country_filter(team_filter):
        for term in ["soccer", "fifa", "world", "cup", "international", "friendlies", "concacaf", "uefa", "copa", "qualifiers"]:
            if term in text:
                score += 14.0
        for term in ["nba", "nfl", "mlb", "nhl", "basketball", "baseball", "hockey", "americanfootball"]:
            if term in text:
                score -= 2.0
    return score


def name_match_score(filter_text: str, item) -> float:
    if not filter_text.strip():
        return 1.0
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    best = 0.0
    for alias in filter_aliases(filter_text):
        for name in names:
            target = clean(name)
            if alias and (alias in target or target in alias):
                best = max(best, 1.0)
            else:
                best = max(best, SequenceMatcher(None, alias, target).ratio())
    return best


def top_non_draw(item):
    return next((o for o in item.outcomes if clean(o.name) != "draw"), item.outcomes[0])


def market_snapshot(item) -> dict:
    top = item.outcomes[0]
    second = item.outcomes[1] if len(item.outcomes) > 1 else None
    team_pick = top_non_draw(item)
    draw_prob = next((outcome.normalized_probability for outcome in item.outcomes if clean(outcome.name) in ["draw", "empate"]), None)
    gap = top.normalized_probability - (second.normalized_probability if second else 0.0)
    max_range = max((getattr(o, "price_range", 0.0) or 0.0) for o in item.outcomes)
    best = getattr(team_pick, "best_price", None) or team_pick.average_price
    overround = getattr(item, "market_overround", 0.0)
    quality = min(100, round(50 + min(item.bookmaker_count, 12) * 3 + min(gap, 0.30) * 80 - max(overround, 0.0) * 100))
    return {
        "event": f"{item.away_team} at {item.home_team}",
        "sport": item.sport_title,
        "start": item.commence_time,
        "favorite": top.name,
        "favorite_prob": top.normalized_probability,
        "team_pick": team_pick.name,
        "team_win_prob": team_pick.normalized_probability,
        "best_price": best,
        "best_book": getattr(team_pick, "best_bookmaker", None) or "",
        "gap": gap,
        "draw_prob": draw_prob,
        "books": item.bookmaker_count,
        "max_range": max_range,
        "overround": overround,
        "quality": max(0, quality),
        "match_score": 1.0,
        "item": item,
    }


def event_table(item):
    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append({
            t("outcome"): outcome.name,
            t("avg_price"): round(outcome.average_price, 3),
            t("best_price"): round((getattr(outcome, "best_price", None) or outcome.average_price), 3),
            t("best_book"): getattr(outcome, "best_bookmaker", None) or "",
            t("range"): round((getattr(outcome, "price_range", None) or 0.0), 3),
            t("probability"): f"{outcome.normalized_probability:.1%}",
            t("books"): outcome.source_count,
        })
        if outcome.name == item.home_team:
            home_probability = outcome.normalized_probability
    return rows, home_probability


def margin_rows(item):
    fav = item.favorite
    dog = next((outcome.name for outcome in item.outcomes if clean(outcome.name) not in [clean(fav), "draw"]), "Opponent")
    fav_prob = item.outcomes[0].normalized_probability
    dog_prob = next((outcome.normalized_probability for outcome in item.outcomes if clean(outcome.name) not in [clean(fav), "draw"]), max(0.0, 1.0 - fav_prob))
    bands = [("close", 0.45), ("solid", 0.35), ("big", 0.20)]
    rows = []
    for label, weight in bands:
        rows.append({t("score"): f"{fav} {label}", t("read"): f"{fav} {label}", t("estimated"): f"{fav_prob * weight:.1%}"})
    for label, weight in bands:
        rows.append({t("score"): f"{dog} {label}", t("read"): f"{dog} {label}", t("estimated"): f"{dog_prob * weight:.1%}"})
    return sorted(rows, key=lambda row: float(row[t("estimated")].strip("%")), reverse=True)[:6]


def scoreline_rows(item, home_probability):
    if home_probability is None:
        return margin_rows(item)
    home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
    rows = []
    for pick in estimate_scorelines(home_xg, away_xg):
        if pick.margin > 0:
            read = f"{item.home_team} {t('by')} {pick.margin}"
        elif pick.margin < 0:
            read = f"{item.away_team} {t('by')} {abs(pick.margin)}"
        else:
            read = t("draw")
        rows.append({t("score"): pick.label, t("read"): read, t("estimated"): f"{pick.probability:.1%}"})
    return rows


def ara_report(item, snap) -> str:
    draw_line = ""
    if snap["draw_prob"] is not None and snap["draw_prob"] >= 0.25:
        draw_line = " Draw risk is meaningful; the highest team win chance may still be below 50%." if not IS_ES else " El riesgo de empate es importante; la mayor probabilidad de victoria aún puede estar debajo de 50%."
    price_line = f" Best available price: {snap['best_price']:.3f}"
    if snap["best_book"]:
        price_line += f" at {snap['best_book']}"
    if IS_ES:
        return f"Lectura: {snap['team_pick']} tiene la mayor probabilidad de ganar ({snap['team_win_prob']:.1%}). Calidad del mercado: {snap['quality']}/100. {price_line}. {draw_line}"
    return f"Read: {snap['team_pick']} has the highest team win chance ({snap['team_win_prob']:.1%}). Market quality: {snap['quality']}/100. {price_line}.{draw_line}"


def display_event(item, expanded=False):
    rows, home_probability = event_table(item)
    snap = market_snapshot(item)
    with st.expander(f"{snap['event']} | {snap['team_pick']} win {snap['team_win_prob']:.1%} | Q{snap['quality']}", expanded=expanded):
        st.info(ara_report(item, snap))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("team_pick"), snap["team_pick"])
        c2.metric(t("win_probability"), f"{snap['team_win_prob']:.1%}")
        c3.metric(t("best_price"), f"{snap['best_price']:.3f}")
        c4.metric(t("quality"), f"{snap['quality']}/100")
        st.write(f"{t('start')}: {snap['start']}")
        st.write(f"{t('overround')}: {pct(snap['overround'])}")
        st.write(t("scorelines"))
        st.dataframe(scoreline_rows(item, home_probability), use_container_width=True, hide_index=True)
        with st.expander(t("raw")):
            st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(t("note"))


def table_from_snapshots(rows):
    return [{
        "Event": row["event"],
        "Sport": row["sport"],
        "Start": row["start"],
        "Team pick": row["team_pick"],
        "Team win %": f"{row['team_win_prob']:.1%}",
        "Match %": f"{row.get('match_score', 1.0):.0%}",
        "Top outcome": row["favorite"],
        "Top outcome %": f"{row['favorite_prob']:.1%}",
        "Best price": round(row["best_price"], 3),
        "Best book": row["best_book"],
        "Gap": f"{row['gap']:.1%}",
        "Draw %": "" if row["draw_prob"] is None else f"{row['draw_prob']:.1%}",
        "Book spread": round(row["max_range"], 3),
        "Overround": f"{row['overround']:.1%}",
        "Quality": row["quality"],
        "Books": row["books"],
    } for row in rows]


def best_one_per_sport(rows):
    best = {}
    for row in rows:
        current = best.get(row["sport"])
        if current is None or row["team_win_prob"] > current["team_win_prob"]:
            best[row["sport"]] = row
    return sorted(best.values(), key=lambda row: row["team_win_prob"], reverse=True)


try:
    saved_token = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_token = os.getenv("THE_ODDS_API_KEY", "")

entry_token = st.text_input(t("token"), value="", type="password")
key = entry_token.strip() or saved_token

if not key:
    st.info(t("token_help"))
    st.stop()

scan_mode = st.radio(t("mode"), [t("smart"), t("single")], horizontal=True)
objective = st.selectbox(t("objective"), [t("highest_win"), t("market_command")], index=0)
selected_regions = st.multiselect(t("regions"), ALL_REGIONS, default=ALL_REGIONS, help=t("regions_help"))
st.caption(t("regions_help"))
search_text = st.text_input(t("sport_search"), "auto")
team_filter = st.text_input(t("team_filter"), "", help=t("team_filter_help"))

if team_filter.strip():
    st.caption(("Filtering for: " if not IS_ES else "Filtrando por: ") + ", ".join(filter_aliases(team_filter)))

if not selected_regions:
    st.error(t("choose_region"))
    st.stop()

try:
    sports = list_sports(key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked_sports = sorted(sports, key=lambda item: sport_relevance(item, search_text, team_filter), reverse=True)
ranked_sports = [sport for sport in ranked_sports if not is_outright_feed(sport)] + [sport for sport in ranked_sports if is_outright_feed(sport)]

with st.expander("Pro filters" if not IS_ES else "Filtros pro"):
    min_books = st.number_input(t("min_books"), min_value=1, max_value=25, value=1, step=1)
    min_favorite = st.slider(t("min_fav"), min_value=0.0, max_value=1.0, value=0.0, step=0.01)

if scan_mode == t("smart"):
    default_feeds = 70 if team_filter.strip() else (35 if objective == t("highest_win") else 20)
    default_events = 50 if team_filter.strip() else (15 if objective == t("highest_win") else 12)
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=120, value=default_feeds, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=default_events, step=1)
    selected_sports = ranked_sports[: int(max_feeds)]
else:
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50 if team_filter.strip() else 20, step=1)
    labels = [f"{item.title} | {item.key}" for item in ranked_sports]
    selected = st.selectbox(t("sport_feed"), labels)
    selected_sports = [ranked_sports[labels.index(selected)]]

region_text = ",".join(selected_regions)

if st.button(t("scan"), type="primary"):
    all_items = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()

    for index, sport in enumerate(selected_sports):
        status.write(f"Scanning {sport.title}...")
        try:
            events = scan_market(key, sport.key, regions=region_text, max_events=int(max_events))
            all_items.extend(events)
        except Exception as exc:
            skipped.append((sport.title, safe_error(exc)))
        progress.progress((index + 1) / max(1, len(selected_sports)))

    status.empty()
    progress.empty()

    all_snapshots = [market_snapshot(item) for item in all_items]
    for row in all_snapshots:
        row["match_score"] = name_match_score(team_filter, row["item"])

    if team_filter.strip():
        exact_snapshots = [row for row in all_snapshots if row["match_score"] >= 0.72]
        closest_matches = sorted([row for row in all_snapshots if row["match_score"] >= 0.35], key=lambda row: row["match_score"], reverse=True)
        if exact_snapshots:
            snapshots = exact_snapshots
        else:
            st.warning(t("no_exact"))
            snapshots = all_snapshots
    else:
        closest_matches = []
        snapshots = all_snapshots

    snapshots = [row for row in snapshots if row["books"] >= int(min_books) and row["team_win_prob"] >= float(min_favorite)]

    if not snapshots:
        st.info(t("no_games"))
        if skipped:
            with st.expander(t("skipped")):
                for title, reason in skipped[:30]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    highest_team = sorted(snapshots, key=lambda row: row["team_win_prob"], reverse=True)
    by_sport = best_one_per_sport(snapshots)
    balanced = sorted(snapshots, key=lambda row: row["gap"])
    disagreement = sorted(snapshots, key=lambda row: row["max_range"], reverse=True)
    quality = sorted(snapshots, key=lambda row: row["quality"], reverse=True)
    draw_heavy = [row for row in sorted(snapshots, key=lambda row: row["draw_prob"] or 0.0, reverse=True) if row["draw_prob"] is not None]

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds"), len(selected_sports))
    c2.metric(t("events"), len(snapshots))
    c3.metric(t("skipped"), len(skipped))
    c4.metric(t("highest_team"), f"{highest_team[0]['team_pick']} {highest_team[0]['team_win_prob']:.1%}")

    csv_rows = table_from_snapshots(highest_team)
    st.download_button(t("download"), data="\n".join(
        [",".join(csv_rows[0].keys())] + [",".join(str(value).replace(',', ' ') for value in row.values()) for row in csv_rows]
    ), file_name="highest_team_win_scan.csv", mime="text/csv")

    tab_labels = [t("highest_team"), t("by_sport"), t("balanced"), t("disagreement"), t("draw_heavy"), t("all_games"), t("ara_read")]
    if team_filter.strip():
        tab_labels.insert(2, t("closest_filter"))
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        for row in highest_team[:15]:
            display_event(row["item"], expanded=row == highest_team[0])
    with tabs[1]:
        st.dataframe(table_from_snapshots(by_sport), use_container_width=True, hide_index=True)
        for row in by_sport[:10]:
            display_event(row["item"], expanded=False)

    tab_offset = 0
    if team_filter.strip():
        tab_offset = 1
        with tabs[2]:
            if not closest_matches:
                st.info(t("no_games"))
            else:
                st.dataframe(table_from_snapshots(closest_matches[:25]), use_container_width=True, hide_index=True)

    with tabs[2 + tab_offset]:
        for row in balanced[:10]:
            display_event(row["item"], expanded=False)
    with tabs[3 + tab_offset]:
        for row in disagreement[:10]:
            display_event(row["item"], expanded=False)
    with tabs[4 + tab_offset]:
        if not draw_heavy:
            st.info("No three-outcome draw markets found." if not IS_ES else "No se encontraron mercados de empate.")
        for row in draw_heavy[:10]:
            display_event(row["item"], expanded=False)
    with tabs[5 + tab_offset]:
        st.dataframe(table_from_snapshots(highest_team), use_container_width=True, hide_index=True)
    with tabs[6 + tab_offset]:
        for row in quality[:10]:
            st.write(f"- {ara_report(row['item'], row)}")

    with st.expander(t("diagnostics")):
        st.write(f"{t('feeds')}: {len(selected_sports)}")
        st.write(f"{t('events')}: {len(snapshots)}")
        st.write(f"All market events before filter: {len(all_snapshots)}")
        if team_filter.strip():
            st.write(f"Exact matches for filter: {len([row for row in all_snapshots if row['match_score'] >= 0.72])}")
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:30]:
                st.write(f"- {title}: {reason}")
