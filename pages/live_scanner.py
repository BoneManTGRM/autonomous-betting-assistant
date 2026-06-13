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
        "English": "A cross-sport market intelligence scanner: rank favorites, find close markets, spot bookmaker disagreement, estimate scores/margins, and generate a clean ARA-style read.",
        "Español": "Escáner de inteligencia de mercado multideporte: ordena favoritos, encuentra mercados cerrados, detecta desacuerdo entre casas, estima marcadores/márgenes y genera una lectura estilo ARA.",
    },
    "token": {"English": "Provider access token", "Español": "Clave de acceso del proveedor"},
    "token_help": {"English": "Paste your own provider access token. It is used only for this browser session unless the app owner configures one separately.", "Español": "Pega tu propia clave. Se usa solo en esta sesión del navegador salvo que el dueño configure una aparte."},
    "mode": {"English": "Scan mode", "Español": "Modo de escaneo"},
    "smart": {"English": "Smart dashboard", "Español": "Panel inteligente"},
    "single": {"English": "Single feed", "Español": "Una fuente"},
    "regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "regions_help": {"English": "The Odds API regions: us, us2, uk, eu, au. These are bookmaker markets, not event host countries.", "Español": "Regiones de The Odds API: us, us2, uk, eu, au. Son mercados de casas de apuestas, no países sede del evento."},
    "sport_search": {"English": "Sport / league search", "Español": "Buscar deporte / liga"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo/jugador"},
    "team_filter_help": {"English": "Optional. Example: Mexico, Lakers, Djokovic, Yankees", "Español": "Opcional. Ejemplo: México, Lakers, Djokovic, Yankees"},
    "max_feeds": {"English": "Max feeds to scan", "Español": "Máximo de fuentes a revisar"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "min_fav": {"English": "Minimum favorite probability", "Español": "Probabilidad mínima del favorito"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "sport_feed": {"English": "Sport feed", "Español": "Fuente deportiva"},
    "scan": {"English": "Scan live markets", "Español": "Escanear mercados en vivo"},
    "no_games": {"English": "No games with usable market data were returned.", "Español": "No se devolvieron partidos con datos de mercado utilizables."},
    "start": {"English": "Start", "Español": "Inicio"},
    "most_likely": {"English": "Most likely", "Español": "Más probable"},
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
    "note": {"English": "Market-only scan. Add injuries, lineups, weather, ratings, and news before trusting any pick.", "Español": "Escaneo solo de mercado. Agrega lesiones, alineaciones, clima, ratings y noticias antes de confiar en una selección."},
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
    "nba", "nfl", "mlb", "nhl", "soccer", "fifa", "world cup", "tennis", "ufc", "mma", "boxing", "cricket",
    "rugby", "golf", "formula", "nascar", "darts", "snooker", "esports", "volleyball", "handball", "lacrosse",
]


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def pct(value) -> str:
    return "" if value is None else f"{value:.1%}"


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


def sport_relevance(sport, query: str) -> float:
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    terms = [clean(term) for term in query.split() if clean(term) and clean(term) != "auto"]
    score = -25.0 if is_outright_feed(sport) else 0.0
    if not terms:
        for index, term in enumerate(POPULAR_TERMS):
            if clean(term) in text:
                score += max(1.0, 10.0 - index * 0.25)
        return score
    for term in terms:
        if term in text:
            score += 12.0
        else:
            score += SequenceMatcher(None, term, text).ratio()
    return score


def name_match_score(filter_text: str, item) -> float:
    if not filter_text.strip():
        return 1.0
    query = clean(filter_text)
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    return max(SequenceMatcher(None, query, clean(name)).ratio() if query not in clean(name) else 1.0 for name in names)


def top_non_draw(item):
    return next((o for o in item.outcomes if clean(o.name) != "draw"), item.outcomes[0])


def market_snapshot(item) -> dict:
    top = item.outcomes[0]
    second = item.outcomes[1] if len(item.outcomes) > 1 else None
    draw_prob = next((outcome.normalized_probability for outcome in item.outcomes if clean(outcome.name) in ["draw", "empate"]), None)
    gap = top.normalized_probability - (second.normalized_probability if second else 0.0)
    max_range = max((getattr(o, "price_range", 0.0) or 0.0) for o in item.outcomes)
    best = getattr(top, "best_price", None) or top.average_price
    overround = getattr(item, "market_overround", 0.0)
    quality = min(100, round(50 + min(item.bookmaker_count, 12) * 3 + min(gap, 0.30) * 80 - max(overround, 0.0) * 100))
    return {
        "event": f"{item.away_team} at {item.home_team}",
        "sport": item.sport_title,
        "start": item.commence_time,
        "favorite": top.name,
        "favorite_prob": top.normalized_probability,
        "best_price": best,
        "best_book": getattr(top, "best_bookmaker", None) or "",
        "gap": gap,
        "draw_prob": draw_prob,
        "books": item.bookmaker_count,
        "max_range": max_range,
        "overround": overround,
        "quality": max(0, quality),
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
        draw_line = " Draw risk is meaningful; avoid overconfidence." if not IS_ES else " El riesgo de empate es importante; evita exceso de confianza."
    price_line = f" Best available price: {snap['best_price']:.3f}"
    if snap["best_book"]:
        price_line += f" at {snap['best_book']}"
    if IS_ES:
        return f"Lectura: {snap['favorite']} es el resultado más probable ({snap['favorite_prob']:.1%}). Calidad del mercado: {snap['quality']}/100. {price_line}. {draw_line}"
    return f"Read: {snap['favorite']} is the most likely outcome ({snap['favorite_prob']:.1%}). Market quality: {snap['quality']}/100. {price_line}.{draw_line}"


def display_event(item, expanded=False):
    rows, home_probability = event_table(item)
    snap = market_snapshot(item)
    with st.expander(f"{snap['event']} | {snap['favorite']} {snap['favorite_prob']:.1%} | Q{snap['quality']}", expanded=expanded):
        st.info(ara_report(item, snap))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("most_likely"), snap["favorite"])
        c2.metric(t("probability"), f"{snap['favorite_prob']:.1%}")
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
        "Favorite": row["favorite"],
        "Favorite %": f"{row['favorite_prob']:.1%}",
        "Best price": round(row["best_price"], 3),
        "Best book": row["best_book"],
        "Gap": f"{row['gap']:.1%}",
        "Draw %": "" if row["draw_prob"] is None else f"{row['draw_prob']:.1%}",
        "Book spread": round(row["max_range"], 3),
        "Overround": f"{row['overround']:.1%}",
        "Quality": row["quality"],
        "Books": row["books"],
    } for row in rows]


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
selected_regions = st.multiselect(t("regions"), ALL_REGIONS, default=ALL_REGIONS, help=t("regions_help"))
st.caption(t("regions_help"))
search_text = st.text_input(t("sport_search"), "auto")
team_filter = st.text_input(t("team_filter"), "", help=t("team_filter_help"))

if not selected_regions:
    st.error(t("choose_region"))
    st.stop()

try:
    sports = list_sports(key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked_sports = sorted(sports, key=lambda item: sport_relevance(item, search_text), reverse=True)
ranked_sports = [sport for sport in ranked_sports if not is_outright_feed(sport)] + [sport for sport in ranked_sports if is_outright_feed(sport)]

with st.expander("Pro filters" if not IS_ES else "Filtros pro"):
    min_books = st.number_input(t("min_books"), min_value=1, max_value=25, value=1, step=1)
    min_favorite = st.slider(t("min_fav"), min_value=0.0, max_value=1.0, value=0.0, step=0.01)

if scan_mode == t("smart"):
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=80, value=20, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=12, step=1)
    selected_sports = ranked_sports[: int(max_feeds)]
else:
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=20, step=1)
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

    if team_filter.strip():
        all_items = [item for item in all_items if name_match_score(team_filter, item) >= 0.45]
    all_items = [item for item in all_items if item.bookmaker_count >= int(min_books) and item.favorite_probability >= float(min_favorite)]

    if not all_items:
        st.info(t("no_games"))
        if skipped:
            with st.expander(t("skipped")):
                for title, reason in skipped[:30]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    snapshots = [market_snapshot(item) for item in all_items]
    strongest = sorted(snapshots, key=lambda row: row["favorite_prob"], reverse=True)
    balanced = sorted(snapshots, key=lambda row: row["gap"])
    disagreement = sorted(snapshots, key=lambda row: row["max_range"], reverse=True)
    quality = sorted(snapshots, key=lambda row: row["quality"], reverse=True)
    draw_heavy = [row for row in sorted(snapshots, key=lambda row: row["draw_prob"] or 0.0, reverse=True) if row["draw_prob"] is not None]

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds"), len(selected_sports))
    c2.metric(t("events"), len(all_items))
    c3.metric(t("skipped"), len(skipped))
    c4.metric(t("quality"), f"{round(sum(row['quality'] for row in snapshots) / len(snapshots))}/100")

    st.download_button(t("download"), data="\n".join(
        [",".join(table_from_snapshots(strongest)[0].keys())] + [",".join(str(value).replace(',', ' ') for value in row.values()) for row in table_from_snapshots(strongest)]
    ), file_name="live_market_scan.csv", mime="text/csv")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([t("strongest"), t("balanced"), t("disagreement"), t("draw_heavy"), t("all_games"), t("ara_read")])

    with tab1:
        for row in strongest[:10]:
            display_event(row["item"], expanded=row == strongest[0])
    with tab2:
        for row in balanced[:10]:
            display_event(row["item"], expanded=False)
    with tab3:
        for row in disagreement[:10]:
            display_event(row["item"], expanded=False)
    with tab4:
        if not draw_heavy:
            st.info("No three-outcome draw markets found." if not IS_ES else "No se encontraron mercados de empate.")
        for row in draw_heavy[:10]:
            display_event(row["item"], expanded=False)
    with tab5:
        st.dataframe(table_from_snapshots(strongest), use_container_width=True, hide_index=True)
    with tab6:
        for row in quality[:8]:
            st.write(f"- {ara_report(row['item'], row)}")

    with st.expander(t("diagnostics")):
        st.write(f"{t('feeds')}: {len(selected_sports)}")
        st.write(f"{t('events')}: {len(all_items)}")
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:30]:
                st.write(f"- {title}: {reason}")
