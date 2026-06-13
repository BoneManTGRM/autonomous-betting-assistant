import csv
import io
import os
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Pro Intelligence Scanner", layout="wide")

LANGUAGE = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = LANGUAGE == "Español"

TEXT = {
    "title": {"English": "Pro Betting Intelligence Scanner", "Español": "Escáner Pro de Inteligencia Deportiva"},
    "caption": {
        "English": "The advanced scanner: upcoming fallback, cross-sport search, team matching, best-price shopping, line-movement memory, confidence-adjusted reads, CSV export, and ARA-style reports.",
        "Español": "Escáner avanzado: búsqueda próxima, multideporte, coincidencia de equipos, mejores precios, memoria de movimiento de línea, lecturas ajustadas por confianza, exportación CSV y reportes estilo ARA.",
    },
    "token": {"English": "The Odds API key", "Español": "Clave de The Odds API"},
    "token_help": {"English": "Paste your key here. Do not share it publicly.", "Español": "Pega tu clave aquí. No la compartas públicamente."},
    "objective": {"English": "Objective", "Español": "Objetivo"},
    "scan_all": {"English": "Scan all sports", "Español": "Escanear todos los deportes"},
    "team_search": {"English": "Find one team/player", "Español": "Buscar un equipo/jugador"},
    "single_feed": {"English": "Single sport feed", "Español": "Una fuente deportiva"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas"},
    "regions_help": {"English": "These are bookmaker markets, not event host countries. The scanner automatically retries regions one-by-one when a combined region request fails.", "Español": "Son mercados de casas, no países sede. El escáner vuelve a intentar región por región cuando una solicitud combinada falla."},
    "sport_query": {"English": "Sport / league search", "Español": "Buscar deporte / liga"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo/jugador"},
    "team_help": {"English": "Leave blank to scan everything. Examples: Mexico, Lakers, Yankees, Djokovic, India.", "Español": "Déjalo vacío para escanear todo. Ejemplos: México, Lakers, Yankees, Djokovic, India."},
    "include_upcoming": {"English": "Use upcoming all-sports fallback", "Español": "Usar respaldo de próximos eventos multideporte"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de fuentes"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "min_match": {"English": "Minimum match score", "Español": "Coincidencia mínima"},
    "scan": {"English": "Run pro scan", "Español": "Ejecutar escaneo pro"},
    "dashboard": {"English": "Intelligence dashboard", "Español": "Panel de inteligencia"},
    "events": {"English": "Events", "Español": "Eventos"},
    "feeds": {"English": "Feeds", "Español": "Fuentes"},
    "matches": {"English": "Matches", "Español": "Coincidencias"},
    "skipped": {"English": "Skipped", "Español": "Omitidas"},
    "best_win": {"English": "Highest win chances", "Español": "Mayores probabilidades"},
    "best_by_sport": {"English": "Best by sport", "Español": "Mejor por deporte"},
    "best_report": {"English": "Best report", "Español": "Mejor reporte"},
    "line_move": {"English": "Line movement", "Español": "Movimiento de línea"},
    "book_disagree": {"English": "Book disagreement", "Español": "Desacuerdo entre casas"},
    "all_games": {"English": "All games", "Español": "Todos"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "no_games": {"English": "No usable markets were returned. Try fewer regions, a specific sport like soccer, or leave the team filter blank.", "Español": "No se devolvieron mercados utilizables. Prueba menos regiones, un deporte específico como soccer o deja el filtro vacío."},
    "warning_no_match": {"English": "No strong team/player match was found. Showing the full scan so the page still returns useful markets.", "Español": "No se encontró una coincidencia fuerte. Mostrando el escaneo completo para devolver mercados útiles."},
    "pick": {"English": "Pick", "Español": "Selección"},
    "market_prob": {"English": "Market probability", "Español": "Probabilidad de mercado"},
    "agent_prob": {"English": "Agent-adjusted probability", "Español": "Probabilidad ajustada"},
    "confidence": {"English": "Confidence", "Español": "Confianza"},
    "best_price": {"English": "Best price", "Español": "Mejor precio"},
    "best_book": {"English": "Best book", "Español": "Mejor casa"},
    "books": {"English": "Books", "Español": "Casas"},
    "quality": {"English": "Quality", "Español": "Calidad"},
    "start": {"English": "Start", "Español": "Inicio"},
    "scorelines": {"English": "Likely scorelines / margins", "Español": "Marcadores / márgenes probables"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda"},
    "download": {"English": "Download CSV", "Español": "Descargar CSV"},
    "note": {"English": "This is market intelligence, not a guaranteed result. True accuracy requires injuries, lineups, weather, ratings, and backtesting.", "Español": "Esto es inteligencia de mercado, no un resultado garantizado. Para precisión real se requieren lesiones, alineaciones, clima, ratings y backtesting."},
}

ALIASES = {
    "mexico": ["mexico", "méxico", "mex", "el tri"],
    "canada": ["canada", "canadá", "can"],
    "usa": ["usa", "united states", "united states of america", "usmnt", "estados unidos"],
    "south korea": ["south korea", "korea republic", "republic of korea", "corea del sur", "korea"],
    "brazil": ["brazil", "brasil"],
    "argentina": ["argentina"],
    "japan": ["japan", "japon", "japón"],
    "india": ["india"],
    "australia": ["australia"],
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
POPULAR_TERMS = [
    "soccer", "fifa", "world cup", "international", "friendlies", "concacaf", "nba", "nfl", "mlb", "nhl",
    "tennis", "ufc", "mma", "boxing", "cricket", "rugby", "golf", "formula", "nascar", "esports",
]


def t(key: str) -> str:
    entry = TEXT.get(key)
    if not entry:
        return key.replace("_", " ").title()
    return entry.get(LANGUAGE) or entry.get("English") or key.replace("_", " ").title()


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def alias_terms(value: str) -> list[str]:
    base = clean(value)
    terms = {base}
    for key, values in ALIASES.items():
        cleaned = [clean(item) for item in values]
        if base == clean(key) or base in cleaned:
            terms.add(clean(key))
            terms.update(cleaned)
    return [term for term in terms if term]


def is_country(value: str) -> bool:
    base = clean(value)
    return any(base == clean(key) or base in [clean(item) for item in values] for key, values in ALIASES.items())


def safe_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "key rejected" if not IS_ES else "clave rechazada"
    if status == 422:
        return "region/feed unavailable" if not IS_ES else "región/fuente no disponible"
    if status == 429:
        return "quota or rate limit" if not IS_ES else "cuota o límite"
    return "request failed" if not IS_ES else "falló solicitud"


def is_outright(sport) -> bool:
    text = clean(f"{sport.key} {sport.title} {sport.description}")
    return any(word in text for word in ["winner", "championship", "outright"])


def sport_score(sport, query: str, team_filter: str) -> float:
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    query_terms = [clean(term) for term in query.split() if clean(term) and clean(term) != "auto"]
    score = -15.0 if is_outright(sport) else 0.0
    if query_terms:
        for term in query_terms:
            score += 14.0 if term in text else SequenceMatcher(None, term, text).ratio()
    else:
        for index, term in enumerate(POPULAR_TERMS):
            if clean(term) in text:
                score += max(1.0, 10.0 - index * 0.25)
    if team_filter and is_country(team_filter):
        for term in ["soccer", "fifa", "world", "international", "friendlies", "concacaf", "uefa", "copa", "qualifiers"]:
            if term in text:
                score += 18.0
    return score


def match_score(filter_text: str, item) -> float:
    if not filter_text.strip():
        return 1.0
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    best = 0.0
    for alias in alias_terms(filter_text):
        for name in names:
            target = clean(name)
            if alias and (alias in target or target in alias):
                best = max(best, 1.0)
            else:
                best = max(best, SequenceMatcher(None, alias, target).ratio())
    return best


def top_team_outcome(item):
    return next((outcome for outcome in item.outcomes if clean(outcome.name) != "draw"), item.outcomes[0])


def sport_kind(item) -> str:
    text = clean(f"{item.sport_key} {item.sport_title}")
    if any(term in text for term in ["soccer", "fifa", "epl", "mls"]):
        return "soccer"
    if "tennis" in text:
        return "tennis"
    if any(term in text for term in ["basketball", "nba"]):
        return "basketball"
    if any(term in text for term in ["americanfootball", "nfl"]):
        return "football"
    if any(term in text for term in ["baseball", "mlb"]):
        return "baseball"
    if any(term in text for term in ["hockey", "nhl"]):
        return "hockey"
    if any(term in text for term in ["mma", "ufc", "boxing"]):
        return "fight"
    return "general"


def quality_score(item, gap: float, max_range: float) -> int:
    overround = max(getattr(item, "market_overround", 0.0), 0.0)
    score = 48 + min(item.bookmaker_count, 12) * 3 + min(gap, 0.30) * 65 - overround * 100 - min(max_range, 1.0) * 8
    return max(0, min(100, round(score)))


def adjusted_probability(market_prob: float, quality: int, books: int, draw_prob, max_range: float) -> float:
    adjustment = 0.0
    adjustment += (quality - 55) / 1000
    adjustment += min(books, 12) / 1200
    adjustment -= min(max_range, 1.0) / 300
    if draw_prob is not None and draw_prob > 0.25:
        adjustment -= 0.025
    return max(0.01, min(0.99, market_prob + adjustment))


def make_snapshot(item, team_filter: str, previous: dict) -> dict:
    pick = top_team_outcome(item)
    second = item.outcomes[1] if len(item.outcomes) > 1 else None
    draw_prob = next((outcome.normalized_probability for outcome in item.outcomes if clean(outcome.name) == "draw"), None)
    gap = item.outcomes[0].normalized_probability - (second.normalized_probability if second else 0.0)
    max_range = max((getattr(outcome, "price_range", 0.0) or 0.0) for outcome in item.outcomes)
    best_price = getattr(pick, "best_price", None) or pick.average_price
    quality = quality_score(item, gap, max_range)
    agent_prob = adjusted_probability(pick.normalized_probability, quality, item.bookmaker_count, draw_prob, max_range)
    key = f"{item.event_id}:{pick.name}"
    old = previous.get(key, {})
    old_price = old.get("best_price")
    old_prob = old.get("market_prob")
    return {
        "key": key,
        "event": f"{item.away_team} at {item.home_team}",
        "sport": item.sport_title,
        "start": item.commence_time,
        "pick": pick.name,
        "market_prob": pick.normalized_probability,
        "agent_prob": agent_prob,
        "prob_delta": None if old_prob is None else pick.normalized_probability - old_prob,
        "best_price": best_price,
        "price_delta": None if old_price is None else best_price - old_price,
        "best_book": getattr(pick, "best_bookmaker", None) or "",
        "draw_prob": draw_prob,
        "gap": gap,
        "books": item.bookmaker_count,
        "quality": quality,
        "match_score": match_score(team_filter, item),
        "item": item,
    }


def raw_market_rows(item):
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


def score_margin_rows(row):
    item = row["item"]
    raw_rows, home_probability = raw_market_rows(item)
    if sport_kind(item) == "soccer" and home_probability is not None:
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
    labels = {
        "tennis": [("2-0 sets", 0.55), ("2-1 sets", 0.35), ("upset risk", 0.10)],
        "basketball": [("close", 0.35), ("solid", 0.40), ("big", 0.25)],
        "football": [("1-score", 0.40), ("solid", 0.35), ("big", 0.25)],
        "baseball": [("by 1", 0.55), ("by 2", 0.25), ("by 3+", 0.20)],
        "hockey": [("by 1", 0.58), ("by 2", 0.25), ("by 3+", 0.17)],
        "fight": [("decision", 0.42), ("finish", 0.43), ("late result", 0.15)],
        "general": [("close", 0.45), ("solid", 0.35), ("comfortable", 0.20)],
    }.get(sport_kind(item), [("close", 0.45), ("solid", 0.35), ("comfortable", 0.20)])
    return [{t("score"): f"{row['pick']} {label}", t("read"): f"{row['pick']} {label}", t("estimated"): f"{row['market_prob'] * weight:.1%}"} for label, weight in labels]


def display_event(row, expanded=False):
    item = row["item"]
    raw_rows, _ = raw_market_rows(item)
    header = f"{row['event']} | {row['pick']} {row['market_prob']:.1%} | Match {row['match_score']:.0%}"
    with st.expander(header, expanded=expanded):
        verdict = "Watch" if row["quality"] >= 70 and row["agent_prob"] >= row["market_prob"] else "Lean"
        if IS_ES:
            verdict = "Vigilar" if verdict == "Watch" else "Lectura"
        st.info(f"{verdict}: {row['pick']} | Market {row['market_prob']:.1%} | Agent-adjusted {row['agent_prob']:.1%} | Quality {row['quality']}/100")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["pick"])
        c2.metric(t("market_prob"), f"{row['market_prob']:.1%}")
        c3.metric(t("best_price"), f"{row['best_price']:.3f}")
        c4.metric(t("confidence"), f"{row['quality']}/100")
        st.write(f"{t('start')}: {row['start']}")
        if row["price_delta"] is not None or row["prob_delta"] is not None:
            st.write(f"Line movement: price {row['price_delta']:+.3f}, probability {row['prob_delta']:+.1%}")
        st.write(t("scorelines"))
        st.dataframe(score_margin_rows(row), use_container_width=True, hide_index=True)
        with st.expander(t("raw")):
            st.dataframe(raw_rows, use_container_width=True, hide_index=True)
        st.caption(t("note"))


def table_rows(rows):
    return [{
        "Event": row["event"],
        "Sport": row["sport"],
        "Start": row["start"],
        "Pick": row["pick"],
        "Market %": f"{row['market_prob']:.1%}",
        "Agent %": f"{row['agent_prob']:.1%}",
        "Match": f"{row['match_score']:.0%}",
        "Best price": round(row["best_price"], 3),
        "Best book": row["best_book"],
        "Price move": "" if row["price_delta"] is None else round(row["price_delta"], 3),
        "Prob move": "" if row["prob_delta"] is None else f"{row['prob_delta']:+.1%}",
        "Books": row["books"],
        "Quality": row["quality"],
    } for row in rows]


def best_by_sport(rows):
    best = {}
    for row in rows:
        current = best.get(row["sport"])
        if current is None or row["market_prob"] > current["market_prob"]:
            best[row["sport"]] = row
    return sorted(best.values(), key=lambda value: value["market_prob"], reverse=True)


def scan_resilient(api_key, sport_key, regions, max_events):
    attempts = [",".join(regions)] + regions
    seen = set()
    results = []
    errors = []
    for region_text in attempts:
        try:
            events = scan_market(api_key, sport_key, regions=region_text, max_events=max_events)
            for event in events:
                event_key = event.event_id or f"{event.sport_key}:{event.home_team}:{event.away_team}:{event.commence_time}"
                if event_key not in seen:
                    seen.add(event_key)
                    results.append(event)
            if results:
                return results, errors
        except Exception as exc:
            errors.append(f"{region_text}: {safe_error(exc)}")
    return results, errors


def csv_text(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(table_rows(rows)[0].keys()))
    writer.writeheader()
    writer.writerows(table_rows(rows))
    return output.getvalue()


st.title(t("title"))
st.caption(t("caption"))

try:
    saved_token = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_token = os.getenv("THE_ODDS_API_KEY", "")

entry_token = st.text_input(t("token"), value="", type="password")
api_key = entry_token.strip() or saved_token
if not api_key:
    st.info(t("token_help"))
    st.stop()

objective = st.radio(t("objective"), [t("scan_all"), t("team_search"), t("single_feed")], horizontal=True)
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"], help=t("regions_help"))
st.caption(t("regions_help"))
sport_query = st.text_input(t("sport_query"), "auto")
team_filter = st.text_input(t("team_filter"), "", help=t("team_help"))
include_upcoming = st.checkbox(t("include_upcoming"), value=True)

if not regions:
    st.error(t("choose_region"))
    st.stop()

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked_sports = sorted(sports, key=lambda sport: sport_score(sport, sport_query, team_filter), reverse=True)
ranked_sports = [sport for sport in ranked_sports if not is_outright(sport)] + [sport for sport in ranked_sports if is_outright(sport)]

with st.expander("Pro controls" if not IS_ES else "Controles pro"):
    min_books = st.number_input(t("min_books"), min_value=1, max_value=25, value=1, step=1)
    min_match = st.slider(t("min_match"), min_value=0.0, max_value=1.0, value=0.40 if team_filter.strip() else 0.0, step=0.05)

if objective == t("single_feed"):
    labels = [f"{sport.title} | {sport.key}" for sport in ranked_sports]
    selected = st.selectbox(t("sport_feed"), labels)
    selected_sports = [ranked_sports[labels.index(selected)]]
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50, step=1)
else:
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=120, value=60 if team_filter.strip() else 30, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50 if team_filter.strip() else 25, step=1)
    selected_sports = ranked_sports[: int(max_feeds)]

if include_upcoming:
    selected_sports = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games", has_outrights=False)] + selected_sports

if "pro_last_scan" not in st.session_state:
    st.session_state.pro_last_scan = {}

if st.button(t("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()

    for index, sport in enumerate(selected_sports):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_resilient(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:3])))
        progress.progress((index + 1) / max(1, len(selected_sports)))

    status.empty()
    progress.empty()

    previous = st.session_state.pro_last_scan
    all_rows = [make_snapshot(event, team_filter, previous) for event in all_events]
    all_rows = [row for row in all_rows if row["books"] >= int(min_books)]

    if team_filter.strip():
        matched = [row for row in all_rows if row["match_score"] >= float(min_match)]
        if matched:
            display_rows = matched
        else:
            st.warning(t("warning_no_match"))
            display_rows = all_rows
    else:
        matched = all_rows
        display_rows = all_rows

    if not display_rows:
        st.info(t("no_games"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped[:60]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    current_memory = {}
    for row in all_rows:
        current_memory[row["key"]] = {"best_price": row["best_price"], "market_prob": row["market_prob"], "seen_at": datetime.now(timezone.utc).isoformat()}
    st.session_state.pro_last_scan = current_memory

    ranked = sorted(display_rows, key=lambda row: (row["match_score"], row["market_prob"], row["quality"]), reverse=True)
    sport_best = best_by_sport(display_rows)
    movers = sorted([row for row in display_rows if row["price_delta"] is not None], key=lambda row: abs(row["price_delta"]), reverse=True)
    disagreement = sorted(display_rows, key=lambda row: row["item"].outcomes[0].price_range or 0.0, reverse=True)
    report = sorted(display_rows, key=lambda row: (row["quality"], row["agent_prob"]), reverse=True)

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds"), len(selected_sports))
    c2.metric(t("events"), len(display_rows))
    c3.metric(t("matches"), len(matched))
    c4.metric(t("skipped"), len(skipped))

    st.download_button(t("download"), data=csv_text(ranked), file_name="pro_intelligence_scan.csv", mime="text/csv")

    tabs = st.tabs([t("best_win"), t("best_by_sport"), t("best_report"), t("line_move"), t("book_disagree"), t("all_games")])

    with tabs[0]:
        for row in ranked[:20]:
            display_event(row, expanded=row == ranked[0])
    with tabs[1]:
        st.dataframe(table_rows(sport_best), use_container_width=True, hide_index=True)
        for row in sport_best[:10]:
            display_event(row, expanded=False)
    with tabs[2]:
        for row in report[:12]:
            st.write(f"- {row['event']}: {row['pick']} | market {row['market_prob']:.1%} | adjusted {row['agent_prob']:.1%} | quality {row['quality']}/100")
    with tabs[3]:
        if not movers:
            st.info("Run another scan later to see movement." if not IS_ES else "Ejecuta otro escaneo después para ver movimiento.")
        else:
            st.dataframe(table_rows(movers[:30]), use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(table_rows(disagreement[:30]), use_container_width=True, hide_index=True)
    with tabs[5]:
        st.dataframe(table_rows(ranked), use_container_width=True, hide_index=True)

    with st.expander(t("diagnostics")):
        st.write(f"{t('feeds')}: {len(selected_sports)}")
        st.write(f"All usable events before filters: {len(all_rows)}")
        st.write(f"Rows displayed: {len(display_rows)}")
        st.write(f"Team filter: {team_filter or 'blank'}")
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:60]:
                st.write(f"- {title}: {reason}")
