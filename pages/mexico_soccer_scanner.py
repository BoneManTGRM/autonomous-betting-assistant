import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Mexico Soccer Scanner", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Mexico Soccer Scanner", "Español": "Escáner de Futbol Mexicano"},
    "caption": {
        "English": "Dedicated scanner for Mexico national team, Liga MX, and major local Mexican clubs. If a selected team has no current market, the scanner still shows closest Mexico/soccer markets instead of going blank.",
        "Español": "Escáner dedicado para Selección Mexicana, Liga MX y clubes mexicanos principales. Si un equipo seleccionado no tiene mercado actual, el escáner muestra mercados cercanos de México/futbol en vez de quedar vacío.",
    },
    "token": {"English": "The Odds API key", "Español": "Clave de The Odds API"},
    "token_help": {"English": "Paste your provider key. Do not share it publicly.", "Español": "Pega tu clave del proveedor. No la compartas públicamente."},
    "team": {"English": "Team", "Español": "Equipo"},
    "custom": {"English": "Custom team search", "Español": "Búsqueda manual de equipo"},
    "custom_help": {"English": "Optional. Overrides the dropdown. Example: Guadalajara, Chivas, America, Toluca, Mexico", "Español": "Opcional. Reemplaza el selector. Ejemplo: Guadalajara, Chivas, América, Toluca, México"},
    "league": {"English": "League/feed search", "Español": "Buscar liga/fuente"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de fuentes"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "scan": {"English": "Scan Mexico soccer markets", "Español": "Escanear mercados de futbol mexicano"},
    "no_games": {"English": "No Mexico soccer markets were found. Try All local Mexico teams, reduce regions to us/eu/uk, or try Upcoming all sports in the general scanner.", "Español": "No se encontraron mercados de futbol mexicano. Prueba Todos los equipos locales, reduce regiones a us/eu/uk o usa próximos eventos en el escáner general."},
    "no_exact": {"English": "No exact team match. This usually means the provider does not currently list that team. Showing closest soccer markets found.", "Español": "No hubo coincidencia exacta. Normalmente significa que el proveedor no tiene ese equipo actualmente. Mostrando mercados de futbol más cercanos."},
    "dashboard": {"English": "Mexico soccer dashboard", "Español": "Panel de futbol mexicano"},
    "feeds": {"English": "Feeds scanned", "Español": "Fuentes revisadas"},
    "events": {"English": "Events found", "Español": "Eventos encontrados"},
    "matches": {"English": "Team matches", "Español": "Coincidencias"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "best": {"English": "Best matches", "Español": "Mejores coincidencias"},
    "all": {"English": "All soccer markets", "Español": "Todos los mercados"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda"},
    "start": {"English": "Start", "Español": "Inicio"},
    "pick": {"English": "Market lean", "Español": "Lectura del mercado"},
    "probability": {"English": "Probability", "Español": "Probabilidad"},
    "best_price": {"English": "Best price", "Español": "Mejor precio"},
    "books": {"English": "Books", "Español": "Casas"},
    "quality": {"English": "Market data quality", "Español": "Calidad de datos"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg price", "Español": "Precio promedio"},
    "best_book": {"English": "Best book", "Español": "Mejor casa"},
    "range": {"English": "Book spread", "Español": "Diferencia entre casas"},
    "scorelines": {"English": "Likely scorelines", "Español": "Marcadores probables"},
    "score": {"English": "Score", "Español": "Marcador"},
    "read": {"English": "Read", "Español": "Lectura"},
    "estimated": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "note": {"English": "Market-only soccer scan. This is not a guaranteed pick.", "Español": "Escaneo futbolero solo de mercado. No es una selección garantizada."},
}

TEAM_ALIASES = {
    "All local Mexico teams": [],
    "Mexico national team": ["mexico", "méxico", "mex", "el tri", "seleccion mexicana", "selección mexicana"],
    "Club America": ["america", "américa", "club america", "club américa", "las aguilas", "águilas", "aguilas"],
    "Chivas / Guadalajara": ["chivas", "guadalajara", "cd guadalajara", "club deportivo guadalajara", "deportivo guadalajara", "guadalajara chivas", "chivas guadalajara", "chivas de guadalajara", "cd chivas", "rebaño", "rebano"],
    "Cruz Azul": ["cruz azul", "la maquina", "máquina", "maquina"],
    "Pumas UNAM": ["pumas", "unam", "pumas unam", "universidad nacional"],
    "Tigres UANL": ["tigres", "uanl", "tigres uanl", "club tigres"],
    "Monterrey / Rayados": ["monterrey", "rayados", "cf monterrey", "club de futbol monterrey"],
    "Toluca": ["toluca", "deportivo toluca", "diablos rojos", "diablos"],
    "Pachuca": ["pachuca", "tuzos", "club pachuca"],
    "Leon": ["leon", "león", "club leon", "club león", "la fiera"],
    "Santos Laguna": ["santos", "santos laguna", "laguneros"],
    "Atlas": ["atlas", "rojinegros", "atlas fc"],
    "Tijuana / Xolos": ["tijuana", "xolos", "club tijuana"],
    "Puebla": ["puebla", "club puebla", "la franja"],
    "Necaxa": ["necaxa", "rayos", "club necaxa"],
    "Queretaro": ["queretaro", "querétaro", "gallos", "gallos blancos"],
    "Juarez / Bravos": ["juarez", "juárez", "fc juarez", "fc juárez", "bravos"],
    "Mazatlan": ["mazatlan", "mazatlán", "mazatlan fc", "mazatlán fc", "cañoneros", "canoneros"],
    "Atletico San Luis": ["atletico san luis", "atlético san luis", "san luis", "atleti san luis"],
    "Atlante": ["atlante", "potros", "potros de hierro"],
    "Morelia": ["morelia", "atletico morelia", "atlético morelia", "monarcas"],
    "Leones Negros": ["leones negros", "udg", "universidad de guadalajara"],
    "Cancun FC": ["cancun", "cancún", "cancun fc", "cancún fc"],
    "Celaya": ["celaya", "toros celaya", "club celaya"],
    "Tapatio": ["tapatio", "tapatío"],
    "Mineros Zacatecas": ["mineros", "mineros zacatecas", "zacatecas"],
    "Venados": ["venados", "venados fc", "merida", "mérida"],
    "Alebrijes Oaxaca": ["alebrijes", "alebrijes oaxaca", "oaxaca"],
    "Correcaminos": ["correcaminos", "correcaminos uat", "uat"],
    "Dorados": ["dorados", "dorados sinaloa", "sinaloa"],
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
SOCCER_TERMS = ["soccer", "fifa", "world", "cup", "liga mx", "mexico", "mexican", "primera", "expansion", "expansión", "concacaf", "friendlies", "club friendlies", "copa mx"]


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def safe_error(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return "key rejected" if not IS_ES else "clave rechazada"
    if status == 422:
        return "region/feed unavailable" if not IS_ES else "región/fuente no disponible"
    if status == 429:
        return "quota or rate limit" if not IS_ES else "cuota o límite"
    return "request failed" if not IS_ES else "falló solicitud"


def sport_score(sport, query: str) -> float:
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    score = 0.0
    for term in SOCCER_TERMS:
        if clean(term) in text:
            score += 10.0
    for term in [clean(x) for x in query.split() if clean(x) and clean(x) != "auto"]:
        if term in text:
            score += 15.0
        else:
            score += SequenceMatcher(None, term, text).ratio()
    if any(word in text for word in ["winner", "championship", "outright"]):
        score -= 30.0
    return score


def aliases_for(label: str, custom: str) -> list[str]:
    if custom.strip():
        base = clean(custom)
        aliases = {base}
        for values in TEAM_ALIASES.values():
            cleaned_values = [clean(v) for v in values]
            if base in cleaned_values:
                aliases.update(cleaned_values)
        return [a for a in aliases if a]
    values = TEAM_ALIASES.get(label, [])
    if not values:
        all_values = []
        for team_label, team_values in TEAM_ALIASES.items():
            if team_label != "All local Mexico teams":
                all_values.extend(team_values)
        return [clean(v) for v in all_values]
    return [clean(v) for v in values]


def match_score(item, aliases: list[str]) -> float:
    if not aliases:
        return 1.0
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    best = 0.0
    for alias in aliases:
        for name in names:
            target = clean(name)
            if alias and (alias in target or target in alias):
                best = max(best, 1.0)
            else:
                best = max(best, SequenceMatcher(None, alias, target).ratio())
    return best


def top_non_draw(item):
    return next((outcome for outcome in item.outcomes if clean(outcome.name) != "draw"), item.outcomes[0])


def event_snapshot(item, score: float) -> dict:
    pick = top_non_draw(item)
    second = item.outcomes[1] if len(item.outcomes) > 1 else None
    gap = item.outcomes[0].normalized_probability - (second.normalized_probability if second else 0.0)
    overround = max(getattr(item, "market_overround", 0.0), 0.0)
    quality = max(0, min(100, round(48 + min(item.bookmaker_count, 12) * 3 + min(gap, 0.30) * 75 - overround * 100)))
    return {
        "Event": f"{item.away_team} at {item.home_team}",
        "Sport": item.sport_title,
        "Start": item.commence_time,
        "Pick": pick.name,
        "Probability": f"{pick.normalized_probability:.1%}",
        "Match": f"{score:.0%}",
        "Best price": round((getattr(pick, "best_price", None) or pick.average_price), 3),
        "Best book": getattr(pick, "best_bookmaker", None) or "",
        "Books": item.bookmaker_count,
        "Quality": quality,
        "_item": item,
        "_score": score,
        "_prob": pick.normalized_probability,
    }


def raw_market_table(item):
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


def scoreline_table(item):
    _, home_probability = raw_market_table(item)
    if home_probability is None:
        return []
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
    item = row["_item"]
    with st.expander(f"{row['Event']} | {row['Pick']} {row['Probability']} | Match {row['Match']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["Pick"])
        c2.metric(t("probability"), row["Probability"])
        c3.metric(t("best_price"), row["Best price"])
        c4.metric(t("quality"), f"{row['Quality']}/100")
        st.write(f"{t('start')}: {row['Start']}")
        rows = scoreline_table(item)
        if rows:
            st.write(t("scorelines"))
            st.dataframe(rows, use_container_width=True, hide_index=True)
        with st.expander(t("raw")):
            market_rows, _ = raw_market_table(item)
            st.dataframe(market_rows, use_container_width=True, hide_index=True)
        st.caption(t("note"))


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


st.title(t("title"))
st.caption(t("caption"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")
api_key = st.text_input(t("token"), value="", type="password").strip() or saved_key
if not api_key:
    st.info(t("token_help"))
    st.stop()

team_label = st.selectbox(t("team"), list(TEAM_ALIASES.keys()), index=0)
custom_team = st.text_input(t("custom"), "", help=t("custom_help"))
league_query = st.text_input(t("league"), "soccer mexico liga mx")
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=100, value=45, step=1)
max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50, step=1)

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked_sports = sorted(sports, key=lambda sport: sport_score(sport, league_query), reverse=True)[: int(max_feeds)]
ranked_sports = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + ranked_sports
selected_aliases = aliases_for(team_label, custom_team)
if selected_aliases:
    st.caption(("Searching aliases: " if not IS_ES else "Buscando alias: ") + ", ".join(selected_aliases[:22]))

if st.button(t("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for idx, sport in enumerate(ranked_sports):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_resilient(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((idx + 1) / max(1, len(ranked_sports)))
    status.empty()
    progress.empty()

    rows = []
    for event in all_events:
        score = match_score(event, selected_aliases)
        rows.append(event_snapshot(event, score))

    exact = [row for row in rows if row["_score"] >= 0.60]
    close = [row for row in rows if row["_score"] >= 0.30]
    if selected_aliases and exact:
        display_rows = exact
    elif selected_aliases and close:
        st.warning(t("no_exact"))
        display_rows = close
    else:
        display_rows = rows

    display_rows = sorted(display_rows, key=lambda row: (row["_score"], row["_prob"]), reverse=True)

    if not display_rows:
        st.info(t("no_games"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped[:40]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds"), len(ranked_sports))
    c2.metric(t("events"), len(rows))
    c3.metric(t("matches"), len(exact))
    c4.metric(t("skipped"), len(skipped))

    table = [{k: v for k, v in row.items() if not k.startswith("_")} for row in display_rows]
    st.download_button(t("download"), data="\n".join([",".join(table[0].keys())] + [",".join(str(v).replace(',', ' ') for v in row.values()) for row in table]), file_name="mexico_soccer_scan.csv", mime="text/csv")

    tabs = st.tabs([t("best"), t("all"), t("diagnostics")])
    with tabs[0]:
        for row in display_rows[:20]:
            display_event(row, expanded=row == display_rows[0])
    with tabs[1]:
        st.dataframe(table, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.write(f"{t('feeds')}: {len(ranked_sports)}")
        st.write(f"{t('events')}: {len(rows)}")
        st.write(f"{t('matches')}: {len(exact)}")
        if skipped:
            st.write(f"{t('skipped')}: {len(skipped)}")
            for title, reason in skipped[:40]:
                st.write(f"- {title}: {reason}")
