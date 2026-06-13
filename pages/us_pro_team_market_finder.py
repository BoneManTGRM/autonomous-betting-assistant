import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="US Pro Team Market Finder", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "NBA / MLB / NFL Team Market Finder", "Español": "Buscador NBA / MLB / NFL"},
    "caption": {
        "English": "Strict team finder for every NBA, MLB, and NFL team. It searches odds-provider markets only. If a team has no current odds market, it will say so instead of showing unrelated games.",
        "Español": "Buscador estricto para todos los equipos NBA, MLB y NFL. Solo busca mercados del proveedor de odds. Si un equipo no tiene mercado actual, lo dirá sin mostrar juegos sin relación.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "league": {"English": "League", "Español": "Liga"},
    "team": {"English": "Team", "Español": "Equipo"},
    "custom": {"English": "Custom team search", "Español": "Búsqueda manual"},
    "sport_search": {"English": "Sport/feed search", "Español": "Buscar deporte/fuente"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de fuentes"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "scan": {"English": "Search selected team", "Español": "Buscar equipo seleccionado"},
    "dashboard": {"English": "Team Market Finder Dashboard", "Español": "Panel del Buscador de Equipos"},
    "selected": {"English": "Selected team", "Español": "Equipo seleccionado"},
    "no_team": {"English": "No current odds market was found for the selected team. This usually means the provider did not return that team in the scanned markets right now, not that the team is missing from the database.", "Español": "No se encontró mercado actual para el equipo seleccionado. Normalmente significa que el proveedor no devolvió ese equipo en los mercados escaneados ahora mismo, no que falte en la base de datos."},
    "feeds": {"English": "Feeds scanned", "Español": "Fuentes revisadas"},
    "events": {"English": "Markets returned", "Español": "Mercados devueltos"},
    "found": {"English": "Team markets found", "Español": "Mercados del equipo"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "matches": {"English": "Selected team matches", "Español": "Coincidencias del equipo"},
    "general": {"English": "General league markets found", "Español": "Mercados generales encontrados"},
    "diag": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "lean": {"English": "Market lean", "Español": "Lectura de mercado"},
    "prob": {"English": "Probability", "Español": "Probabilidad"},
    "price": {"English": "Best price", "Español": "Mejor precio"},
    "quality": {"English": "Market data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda"},
    "matched": {"English": "Matched", "Español": "Coincidió"},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]

TEAM_DATA = [
    # NBA
    ("NBA", "Atlanta Hawks", ["atlanta hawks", "hawks", "atlanta"]),
    ("NBA", "Boston Celtics", ["boston celtics", "celtics", "boston"]),
    ("NBA", "Brooklyn Nets", ["brooklyn nets", "nets", "brooklyn"]),
    ("NBA", "Charlotte Hornets", ["charlotte hornets", "hornets", "charlotte"]),
    ("NBA", "Chicago Bulls", ["chicago bulls", "bulls", "chicago"]),
    ("NBA", "Cleveland Cavaliers", ["cleveland cavaliers", "cavaliers", "cavs", "cleveland"]),
    ("NBA", "Dallas Mavericks", ["dallas mavericks", "mavericks", "mavs", "dallas"]),
    ("NBA", "Denver Nuggets", ["denver nuggets", "nuggets", "denver"]),
    ("NBA", "Detroit Pistons", ["detroit pistons", "pistons", "detroit"]),
    ("NBA", "Golden State Warriors", ["golden state warriors", "warriors", "golden state", "gs warriors", "gsw"]),
    ("NBA", "Houston Rockets", ["houston rockets", "rockets", "houston"]),
    ("NBA", "Indiana Pacers", ["indiana pacers", "pacers", "indiana"]),
    ("NBA", "LA Clippers", ["la clippers", "los angeles clippers", "clippers", "lac"]),
    ("NBA", "Los Angeles Lakers", ["los angeles lakers", "la lakers", "lakers", "lal"]),
    ("NBA", "Memphis Grizzlies", ["memphis grizzlies", "grizzlies", "memphis"]),
    ("NBA", "Miami Heat", ["miami heat", "heat", "miami"]),
    ("NBA", "Milwaukee Bucks", ["milwaukee bucks", "bucks", "milwaukee"]),
    ("NBA", "Minnesota Timberwolves", ["minnesota timberwolves", "timberwolves", "wolves", "minnesota"]),
    ("NBA", "New Orleans Pelicans", ["new orleans pelicans", "pelicans", "new orleans"]),
    ("NBA", "New York Knicks", ["new york knicks", "knicks", "ny knicks", "new york"]),
    ("NBA", "Oklahoma City Thunder", ["oklahoma city thunder", "okc thunder", "thunder", "okc"]),
    ("NBA", "Orlando Magic", ["orlando magic", "magic", "orlando"]),
    ("NBA", "Philadelphia 76ers", ["philadelphia 76ers", "76ers", "sixers", "philadelphia"]),
    ("NBA", "Phoenix Suns", ["phoenix suns", "suns", "phoenix"]),
    ("NBA", "Portland Trail Blazers", ["portland trail blazers", "trail blazers", "blazers", "portland"]),
    ("NBA", "Sacramento Kings", ["sacramento kings", "kings", "sacramento"]),
    ("NBA", "San Antonio Spurs", ["san antonio spurs", "spurs", "san antonio"]),
    ("NBA", "Toronto Raptors", ["toronto raptors", "raptors", "toronto"]),
    ("NBA", "Utah Jazz", ["utah jazz", "jazz", "utah"]),
    ("NBA", "Washington Wizards", ["washington wizards", "wizards", "washington"]),
    # MLB
    ("MLB", "Arizona Diamondbacks", ["arizona diamondbacks", "diamondbacks", "dbacks", "d-backs", "arizona"]),
    ("MLB", "Atlanta Braves", ["atlanta braves", "braves", "atlanta"]),
    ("MLB", "Baltimore Orioles", ["baltimore orioles", "orioles", "baltimore"]),
    ("MLB", "Boston Red Sox", ["boston red sox", "red sox", "bosox", "boston"]),
    ("MLB", "Chicago Cubs", ["chicago cubs", "cubs", "chicago"]),
    ("MLB", "Chicago White Sox", ["chicago white sox", "white sox", "chisox"]),
    ("MLB", "Cincinnati Reds", ["cincinnati reds", "reds", "cincinnati"]),
    ("MLB", "Cleveland Guardians", ["cleveland guardians", "guardians", "cleveland"]),
    ("MLB", "Colorado Rockies", ["colorado rockies", "rockies", "colorado"]),
    ("MLB", "Detroit Tigers", ["detroit tigers", "tigers", "detroit"]),
    ("MLB", "Houston Astros", ["houston astros", "astros", "houston"]),
    ("MLB", "Kansas City Royals", ["kansas city royals", "kc royals", "royals", "kansas city"]),
    ("MLB", "Los Angeles Angels", ["los angeles angels", "la angels", "angels", "anaheim angels"]),
    ("MLB", "Los Angeles Dodgers", ["los angeles dodgers", "la dodgers", "dodgers"]),
    ("MLB", "Miami Marlins", ["miami marlins", "marlins", "miami"]),
    ("MLB", "Milwaukee Brewers", ["milwaukee brewers", "brewers", "milwaukee"]),
    ("MLB", "Minnesota Twins", ["minnesota twins", "twins", "minnesota"]),
    ("MLB", "New York Mets", ["new york mets", "ny mets", "mets"]),
    ("MLB", "New York Yankees", ["new york yankees", "ny yankees", "yankees"]),
    ("MLB", "Oakland Athletics", ["oakland athletics", "athletics", "a's", "as", "oakland"]),
    ("MLB", "Philadelphia Phillies", ["philadelphia phillies", "phillies", "philadelphia"]),
    ("MLB", "Pittsburgh Pirates", ["pittsburgh pirates", "pirates", "pittsburgh"]),
    ("MLB", "San Diego Padres", ["san diego padres", "padres", "san diego"]),
    ("MLB", "San Francisco Giants", ["san francisco giants", "sf giants", "giants"]),
    ("MLB", "Seattle Mariners", ["seattle mariners", "mariners", "seattle"]),
    ("MLB", "St. Louis Cardinals", ["st louis cardinals", "st. louis cardinals", "cardinals", "st louis"]),
    ("MLB", "Tampa Bay Rays", ["tampa bay rays", "rays", "tampa bay"]),
    ("MLB", "Texas Rangers", ["texas rangers", "rangers", "texas"]),
    ("MLB", "Toronto Blue Jays", ["toronto blue jays", "blue jays", "jays", "toronto"]),
    ("MLB", "Washington Nationals", ["washington nationals", "nationals", "nats", "washington"]),
    # NFL
    ("NFL", "Arizona Cardinals", ["arizona cardinals", "cardinals", "az cardinals", "arizona"]),
    ("NFL", "Atlanta Falcons", ["atlanta falcons", "falcons", "atlanta"]),
    ("NFL", "Baltimore Ravens", ["baltimore ravens", "ravens", "baltimore"]),
    ("NFL", "Buffalo Bills", ["buffalo bills", "bills", "buffalo"]),
    ("NFL", "Carolina Panthers", ["carolina panthers", "panthers", "carolina"]),
    ("NFL", "Chicago Bears", ["chicago bears", "bears", "chicago"]),
    ("NFL", "Cincinnati Bengals", ["cincinnati bengals", "bengals", "cincinnati"]),
    ("NFL", "Cleveland Browns", ["cleveland browns", "browns", "cleveland"]),
    ("NFL", "Dallas Cowboys", ["dallas cowboys", "cowboys", "dallas"]),
    ("NFL", "Denver Broncos", ["denver broncos", "broncos", "denver"]),
    ("NFL", "Detroit Lions", ["detroit lions", "lions", "detroit"]),
    ("NFL", "Green Bay Packers", ["green bay packers", "packers", "green bay"]),
    ("NFL", "Houston Texans", ["houston texans", "texans", "houston"]),
    ("NFL", "Indianapolis Colts", ["indianapolis colts", "colts", "indianapolis"]),
    ("NFL", "Jacksonville Jaguars", ["jacksonville jaguars", "jaguars", "jags", "jacksonville"]),
    ("NFL", "Kansas City Chiefs", ["kansas city chiefs", "kc chiefs", "chiefs", "kansas city"]),
    ("NFL", "Las Vegas Raiders", ["las vegas raiders", "raiders", "lv raiders"]),
    ("NFL", "Los Angeles Chargers", ["los angeles chargers", "la chargers", "chargers", "lac"]),
    ("NFL", "Los Angeles Rams", ["los angeles rams", "la rams", "rams", "lar"]),
    ("NFL", "Miami Dolphins", ["miami dolphins", "dolphins", "miami"]),
    ("NFL", "Minnesota Vikings", ["minnesota vikings", "vikings", "minnesota"]),
    ("NFL", "New England Patriots", ["new england patriots", "patriots", "new england", "pats"]),
    ("NFL", "New Orleans Saints", ["new orleans saints", "saints", "new orleans"]),
    ("NFL", "New York Giants", ["new york giants", "ny giants", "giants"]),
    ("NFL", "New York Jets", ["new york jets", "ny jets", "jets"]),
    ("NFL", "Philadelphia Eagles", ["philadelphia eagles", "eagles", "philadelphia"]),
    ("NFL", "Pittsburgh Steelers", ["pittsburgh steelers", "steelers", "pittsburgh"]),
    ("NFL", "San Francisco 49ers", ["san francisco 49ers", "sf 49ers", "49ers", "niners"]),
    ("NFL", "Seattle Seahawks", ["seattle seahawks", "seahawks", "seattle"]),
    ("NFL", "Tampa Bay Buccaneers", ["tampa bay buccaneers", "buccaneers", "bucs", "tampa bay"]),
    ("NFL", "Tennessee Titans", ["tennessee titans", "titans", "tennessee"]),
    ("NFL", "Washington Commanders", ["washington commanders", "commanders", "washington"]),
]


def tr(key):
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def aliases_for(team_name, custom):
    if custom.strip():
        base = clean(custom)
        aliases = {base}
        for _, _, values in TEAM_DATA:
            cleaned = [clean(v) for v in values]
            if base in cleaned:
                aliases.update(cleaned)
        return sorted(aliases)
    for _, name, values in TEAM_DATA:
        if name == team_name:
            return sorted(clean(v) for v in values)
    return []


def alias_score(alias, name):
    alias = clean(alias)
    name = clean(name)
    if not alias or not name:
        return 0.0
    if len(alias) <= 3:
        return 1.0 if alias in set(name.split()) else 0.0
    if alias in name:
        return 1.0
    if len(name) >= 4 and name in alias:
        return 0.92
    ratio = SequenceMatcher(None, alias, name).ratio()
    return ratio if ratio >= 0.88 else 0.0


def team_match(event, aliases):
    names = [event.home_team, event.away_team] + [o.name for o in event.outcomes]
    best_score = 0.0
    best_text = ""
    for alias in aliases:
        for name in names:
            score = alias_score(alias, name)
            if score > best_score:
                best_score = score
                best_text = f"{alias} -> {name}"
    return best_score, best_text


def sport_score(sport, league, query):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    score = 0.0
    league_terms = {
        "NBA": ["basketball", "nba"],
        "MLB": ["baseball", "mlb"],
        "NFL": ["americanfootball", "nfl", "american football"],
        "All": ["basketball", "nba", "baseball", "mlb", "americanfootball", "nfl", "american football"],
    }[league]
    for term in league_terms:
        if clean(term) in text:
            score += 20
    for word in [clean(w) for w in query.split() if clean(w)]:
        if word in text:
            score += 10
    if any(w in text for w in ["winner", "championship", "outright", "super bowl", "world series"]):
        score -= 18
    return score


def safe_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return "key rejected"
    if status == 422:
        return "region/feed unavailable"
    if status == 429:
        return "quota or rate limit"
    return "request failed"


def scan_feed(api_key, sport_key, regions, max_events):
    attempts = [",".join(regions)] + regions
    seen = set()
    found = []
    errors = []
    for region in attempts:
        try:
            events = scan_market(api_key, sport_key, regions=region, max_events=max_events)
            for event in events:
                key = event.event_id or f"{event.sport_key}:{event.home_team}:{event.away_team}:{event.commence_time}"
                if key not in seen:
                    seen.add(key)
                    found.append(event)
            if found:
                return found, errors
        except Exception as exc:
            errors.append(f"{region}: {safe_error(exc)}")
    return found, errors


def top_outcome(event):
    return event.outcomes[0]


def snapshot(event, score, matched):
    top = top_outcome(event)
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = top.normalized_probability - (second.normalized_probability if second else 0)
    quality = max(0, min(100, round(48 + min(event.bookmaker_count, 12) * 3 + min(gap, 0.30) * 70)))
    return {
        "Event": f"{event.away_team} at {event.home_team}",
        "Sport": event.sport_title,
        "Start": event.commence_time,
        "Market lean": top.name,
        "Probability": f"{top.normalized_probability:.1%}",
        "Match": f"{score:.0%}",
        "Matched": matched,
        "Best price": round((getattr(top, "best_price", None) or top.average_price), 3),
        "Books": event.bookmaker_count,
        "Market data quality": quality,
        "_event": event,
        "_score": score,
        "_prob": top.normalized_probability,
    }


def market_table(event):
    return [{
        "Outcome": o.name,
        "Average price": round(o.average_price, 3),
        "Best price": round((getattr(o, "best_price", None) or o.average_price), 3),
        "Best book": getattr(o, "best_bookmaker", None) or "",
        "Probability": f"{o.normalized_probability:.1%}",
        "Books": o.source_count,
    } for o in event.outcomes]


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Market lean']} {row['Probability']} | Match {row['Match']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("lean"), row["Market lean"])
        c2.metric(tr("prob"), row["Probability"])
        c3.metric(tr("price"), row["Best price"])
        c4.metric(tr("quality"), f"{row['Market data quality']}/100")
        st.write(f"{tr('start')}: {row['Start']}")
        st.write(f"{tr('matched')}: {row['Matched']}")
        with st.expander(tr("raw")):
            st.dataframe(market_table(event), use_container_width=True, hide_index=True)


st.title(tr("title"))
st.caption(tr("caption"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")

api_key = st.text_input(tr("token"), type="password").strip() or saved_key
if not api_key:
    st.info("Paste a provider key." if not IS_ES else "Pega una clave del proveedor.")
    st.stop()

league = st.selectbox(tr("league"), ["NBA", "MLB", "NFL", "All"], index=0)
teams = [name for lg, name, _ in TEAM_DATA if league == "All" or lg == league]
team = st.selectbox(tr("team"), teams)
custom = st.text_input(tr("custom"), "")
default_query = {"NBA": "basketball nba", "MLB": "baseball mlb", "NFL": "americanfootball nfl", "All": "nba mlb nfl"}[league]
query = st.text_input(tr("sport_search"), default_query)
regions = st.multiselect(tr("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input(tr("max_feeds"), min_value=1, max_value=100, value=45)
max_events = st.number_input(tr("max_events"), min_value=1, max_value=50, value=50)

aliases = aliases_for(team, custom)
st.caption("Aliases: " + ", ".join(aliases[:20]))

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked = sorted(sports, key=lambda s: sport_score(s, league, query), reverse=True)[: int(max_feeds)]
ranked = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + ranked

if st.button(tr("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for idx, sport in enumerate(ranked):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_feed(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((idx + 1) / max(1, len(ranked)))
    status.empty()
    progress.empty()

    rows = []
    for event in all_events:
        score, matched = team_match(event, aliases)
        rows.append(snapshot(event, score, matched))

    team_rows = sorted([r for r in rows if r["_score"] >= 0.85], key=lambda r: (r["_score"], r["_prob"]), reverse=True)
    all_rows = sorted(rows, key=lambda r: r["_prob"], reverse=True)

    if not team_rows:
        st.error(f"{tr('selected')}: {custom.strip() or team} — {tr('no_team')}")
    else:
        st.success(f"{tr('selected')}: {custom.strip() or team} — {len(team_rows)} {tr('found')}")

    st.subheader(tr("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tr("feeds"), len(ranked))
    c2.metric(tr("events"), len(rows))
    c3.metric(tr("found"), len(team_rows))
    c4.metric(tr("skipped"), len(skipped))

    tabs = st.tabs([tr("matches"), tr("general"), tr("diag")])
    with tabs[0]:
        if not team_rows:
            st.warning(tr("no_team"))
        else:
            for row in team_rows[:20]:
                show_event(row, expanded=row == team_rows[0])
    with tabs[1]:
        visible = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_rows]
        if visible:
            st.dataframe(visible, use_container_width=True, hide_index=True)
        else:
            st.info("No markets returned." if not IS_ES else "No se devolvieron mercados.")
    with tabs[2]:
        st.write(f"Strict team threshold: 85%")
        st.write(f"Selected league: {league}")
        st.write(f"Selected team: {custom.strip() or team}")
        st.write(f"Aliases searched: {', '.join(aliases)}")
        st.write(f"Scanned feeds: {len(ranked)}")
        st.write(f"Returned markets: {len(rows)}")
        st.write(f"Selected-team markets found: {len(team_rows)}")
        if skipped:
            for title, reason in skipped[:50]:
                st.write(f"- {title}: {reason}")
