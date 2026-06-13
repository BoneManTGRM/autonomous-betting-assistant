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
    "title": {"English": "Live Market Scanner", "Español": "Escáner de Mercado en Vivo"},
    "caption": {
        "English": "Search live games across sports. Leave the team/player filter blank to scan everything, or enter a team/player to find matching games.",
        "Español": "Busca partidos en vivo en varios deportes. Deja el filtro de equipo/jugador vacío para escanear todo, o escribe un equipo/jugador para encontrar partidos relacionados.",
    },
    "token": {"English": "Provider access token", "Español": "Clave de acceso del proveedor"},
    "token_help": {"English": "Paste your own provider access token. It is used only for this browser session unless the app owner configures one separately.", "Español": "Pega tu propia clave. Se usa solo en esta sesión del navegador salvo que el dueño configure una aparte."},
    "mode": {"English": "Scan mode", "Español": "Modo de escaneo"},
    "smart": {"English": "Smart multi-feed scan", "Español": "Escaneo inteligente multi-fuente"},
    "single": {"English": "Single feed", "Español": "Una fuente"},
    "regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "regions_help": {"English": "Regions are bookmaker markets, not host countries. If one region fails, the scanner tries the others automatically.", "Español": "Las regiones son mercados de casas de apuestas, no países sede. Si una región falla, el escáner prueba las otras automáticamente."},
    "sport_search": {"English": "Sport / league search", "Español": "Buscar deporte / liga"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo/jugador"},
    "team_filter_help": {"English": "Optional. Example: Mexico, Lakers, Djokovic, Yankees. Leave blank to show all games.", "Español": "Opcional. Ejemplo: México, Lakers, Djokovic, Yankees. Déjalo vacío para mostrar todos los juegos."},
    "max_feeds": {"English": "Max feeds to scan", "Español": "Máximo de fuentes a revisar"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "scan": {"English": "Scan live markets", "Español": "Escanear mercados en vivo"},
    "sport_feed": {"English": "Sport feed", "Español": "Fuente deportiva"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "no_games": {"English": "No games with usable market data were returned.", "Español": "No se devolvieron partidos con datos de mercado utilizables."},
    "no_exact": {"English": "No exact matches were found for that filter. Showing the closest games and the full scan instead.", "Español": "No se encontraron coincidencias exactas para ese filtro. Mostrando los partidos más cercanos y el escaneo completo."},
    "dashboard": {"English": "Scanner dashboard", "Español": "Panel del escáner"},
    "feeds": {"English": "Feeds scanned", "Español": "Fuentes revisadas"},
    "events": {"English": "Events found", "Español": "Eventos encontrados"},
    "matches": {"English": "Matches", "Español": "Coincidencias"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "best_matches": {"English": "Best matches", "Español": "Mejores coincidencias"},
    "closest_matches": {"English": "Closest matches", "Español": "Coincidencias cercanas"},
    "all_games": {"English": "All games", "Español": "Todos los juegos"},
    "by_sport": {"English": "Best by sport", "Español": "Mejor por deporte"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda de mercado"},
    "download": {"English": "Download CSV", "Español": "Descargar CSV"},
    "start": {"English": "Start", "Español": "Inicio"},
    "pick": {"English": "Market lean", "Español": "Lectura del mercado"},
    "probability": {"English": "Probability", "Español": "Probabilidad"},
    "best_price": {"English": "Best price", "Español": "Mejor precio"},
    "best_book": {"English": "Best book", "Español": "Mejor casa"},
    "books": {"English": "Books", "Español": "Casas"},
    "quality": {"English": "Quality", "Español": "Calidad"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg price", "Español": "Precio promedio"},
    "range": {"English": "Book spread", "Español": "Diferencia entre casas"},
    "scorelines": {"English": "Likely scorelines / margins", "Español": "Marcadores / márgenes probables"},
    "score": {"English": "Score / margin", "Español": "Marcador / margen"},
    "read": {"English": "Read", "Español": "Lectura"},
    "estimated": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "note": {"English": "Market-only scan. This is not a guaranteed pick.", "Español": "Escaneo solo de mercado. No es una selección garantizada."},
}

COUNTRY_ALIASES = {
    "mexico": ["mexico", "méxico", "mex", "el tri"],
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

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
POPULAR_TERMS = ["soccer", "fifa", "world cup", "international", "nba", "nfl", "mlb", "nhl", "tennis", "ufc", "mma", "boxing", "cricket", "rugby", "golf"]


def t(key: str) -> str:
    entry = TEXT.get(key)
    if not entry:
        return key.replace("_", " ").title()
    return entry.get(language) or entry.get("English") or key.replace("_", " ").title()


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


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
        return "Provider key rejected" if not IS_ES else "Clave rechazada"
    if status == 422:
        return "region/feed unavailable" if not IS_ES else "región/fuente no disponible"
    if status == 429:
        return "quota or rate limit reached" if not IS_ES else "cuota o límite alcanzado"
    return "provider request failed" if not IS_ES else "falló la solicitud"


def is_outright_feed(sport) -> bool:
    text = clean(f"{sport.key} {sport.title} {sport.description}")
    return any(word in text for word in ["winner", "championship", "outright"])


def sport_relevance(sport, query: str, team_filter: str = "") -> float:
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    terms = [clean(term) for term in query.split() if clean(term) and clean(term) != "auto"]
    score = -20.0 if is_outright_feed(sport) else 0.0
    if terms:
        for term in terms:
            score += 14.0 if term in text else SequenceMatcher(None, term, text).ratio()
    else:
        for index, term in enumerate(POPULAR_TERMS):
            if clean(term) in text:
                score += max(1.0, 10.0 - index * 0.25)
    if team_filter.strip() and is_country_filter(team_filter):
        for term in ["soccer", "fifa", "world", "cup", "international", "friendlies", "concacaf", "uefa", "copa", "qualifiers"]:
            if term in text:
                score += 16.0
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
    best_price = getattr(team_pick, "best_price", None) or team_pick.average_price
    overround = getattr(item, "market_overround", 0.0)
    quality = max(0, min(100, round(50 + min(item.bookmaker_count, 12) * 3 + min(gap, 0.30) * 80 - max(overround, 0.0) * 100)))
    return {
        "event": f"{item.away_team} at {item.home_team}",
        "sport": item.sport_title,
        "start": item.commence_time,
        "pick": team_pick.name,
        "prob": team_pick.normalized_probability,
        "favorite": top.name,
        "favorite_prob": top.normalized_probability,
        "best_price": best_price,
        "best_book": getattr(team_pick, "best_bookmaker", None) or "",
        "gap": gap,
        "draw_prob": draw_prob,
        "books": item.bookmaker_count,
        "max_range": max_range,
        "quality": quality,
        "item": item,
        "match_score": 1.0,
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
    pick = top_non_draw(item)
    rows = []
    for label, weight in [("close", 0.45), ("solid", 0.35), ("big", 0.20)]:
        rows.append({t("score"): f"{pick.name} {label}", t("read"): f"{pick.name} {label}", t("estimated"): f"{pick.normalized_probability * weight:.1%}"})
    return rows


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


def display_event(row, expanded=False):
    item = row["item"]
    rows, home_probability = event_table(item)
    with st.expander(f"{row['event']} | {row['pick']} {row['prob']:.1%} | Match {row['match_score']:.0%}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["pick"])
        c2.metric(t("probability"), f"{row['prob']:.1%}")
        c3.metric(t("best_price"), f"{row['best_price']:.3f}")
        c4.metric(t("quality"), f"{row['quality']}/100")
        st.write(f"{t('start')}: {row['start']}")
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
        "Pick": row["pick"],
        "Probability": f"{row['prob']:.1%}",
        "Match": f"{row.get('match_score', 1.0):.0%}",
        "Best price": round(row["best_price"], 3),
        "Best book": row["best_book"],
        "Draw %": "" if row["draw_prob"] is None else f"{row['draw_prob']:.1%}",
        "Books": row["books"],
        "Quality": row["quality"],
    } for row in rows]


def best_one_per_sport(rows):
    best = {}
    for row in rows:
        current = best.get(row["sport"])
        if current is None or row["prob"] > current["prob"]:
            best[row["sport"]] = row
    return sorted(best.values(), key=lambda row: row["prob"], reverse=True)


def scan_sport_resilient(key, sport_key, selected_regions, max_events):
    attempts = [",".join(selected_regions)] + selected_regions
    seen = set()
    results = []
    errors = []
    for region_text in attempts:
        try:
            events = scan_market(key, sport_key, regions=region_text, max_events=max_events)
            for item in events:
                item_key = item.event_id or f"{item.sport_key}-{item.home_team}-{item.away_team}-{item.commence_time}"
                if item_key not in seen:
                    seen.add(item_key)
                    results.append(item)
            if results:
                break
        except Exception as exc:
            errors.append(f"{region_text}: {safe_error(exc)}")
    return results, errors


st.title(t("title"))
st.caption(t("caption"))

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
selected_regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"], help=t("regions_help"))
st.caption(t("regions_help"))
search_text = st.text_input(t("sport_search"), "auto")
team_filter = st.text_input(t("team_filter"), "", help=t("team_filter_help"))
if team_filter.strip():
    st.caption(("Searching aliases: " if not IS_ES else "Buscando alias: ") + ", ".join(filter_aliases(team_filter)))

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

if scan_mode == t("smart"):
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=120, value=45 if team_filter.strip() else 25, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50 if team_filter.strip() else 25, step=1)
    selected_sports = ranked_sports[: int(max_feeds)]
else:
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50 if team_filter.strip() else 25, step=1)
    labels = [f"{item.title} | {item.key}" for item in ranked_sports]
    selected = st.selectbox(t("sport_feed"), labels)
    selected_sports = [ranked_sports[labels.index(selected)]]

if st.button(t("scan"), type="primary"):
    all_items = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()

    for index, sport in enumerate(selected_sports):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_sport_resilient(key, sport.key, selected_regions, int(max_events))
        all_items.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:3])))
        progress.progress((index + 1) / max(1, len(selected_sports)))

    status.empty()
    progress.empty()

    all_snapshots = [market_snapshot(item) for item in all_items]
    for row in all_snapshots:
        row["match_score"] = name_match_score(team_filter, row["item"])

    all_snapshots = [row for row in all_snapshots if row["books"] >= int(min_books)]

    exact_matches = []
    closest_matches = []
    if team_filter.strip():
        exact_matches = [row for row in all_snapshots if row["match_score"] >= 0.72]
        closest_matches = sorted([row for row in all_snapshots if row["match_score"] >= 0.30], key=lambda row: row["match_score"], reverse=True)
        display_rows = exact_matches if exact_matches else all_snapshots
        if not exact_matches and all_snapshots:
            st.warning(t("no_exact"))
    else:
        display_rows = all_snapshots

    if not display_rows:
        st.info(t("no_games"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped[:40]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    ranked = sorted(display_rows, key=lambda row: (row["match_score"], row["prob"]), reverse=True)
    by_sport = best_one_per_sport(display_rows)

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds"), len(selected_sports))
    c2.metric(t("events"), len(display_rows))
    c3.metric(t("matches"), len(exact_matches) if team_filter.strip() else len(display_rows))
    c4.metric(t("skipped"), len(skipped))

    csv_rows = table_from_snapshots(ranked)
    st.download_button(t("download"), data="\n".join(
        [",".join(csv_rows[0].keys())] + [",".join(str(value).replace(',', ' ') for value in row.values()) for row in csv_rows]
    ), file_name="live_market_scan.csv", mime="text/csv")

    tab_labels = [t("best_matches"), t("by_sport"), t("all_games")]
    if team_filter.strip():
        tab_labels.insert(1, t("closest_matches"))
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        for row in ranked[:15]:
            display_event(row, expanded=row == ranked[0])

    offset = 0
    if team_filter.strip():
        offset = 1
        with tabs[1]:
            if closest_matches:
                st.dataframe(table_from_snapshots(closest_matches[:25]), use_container_width=True, hide_index=True)
            else:
                st.info(t("no_games"))

    with tabs[1 + offset]:
        st.dataframe(table_from_snapshots(by_sport), use_container_width=True, hide_index=True)
        for row in by_sport[:10]:
            display_event(row, expanded=False)

    with tabs[2 + offset]:
        st.dataframe(table_from_snapshots(ranked), use_container_width=True, hide_index=True)

    with st.expander(t("diagnostics")):
        st.write(f"{t('feeds')}: {len(selected_sports)}")
        st.write(f"All market events before filter: {len(all_items)}")
        st.write(f"Rows displayed: {len(display_rows)}")
        if team_filter.strip():
            st.write(f"Exact matches: {len(exact_matches)}")
            st.write(f"Closest matches: {len(closest_matches)}")
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:40]:
                st.write(f"- {title}: {reason}")
