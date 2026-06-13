import os
import unicodedata
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="NBA Playoffs Predictor", layout="wide")

_translate_choice = st.selectbox("Translate page", ["English", "Español"], index=0)
language = _translate_choice
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "NBA Playoffs Predictor", "Español": "Predictor de Playoffs NBA"},
    "caption": {
        "English": "NBA-only scanner with moneyline, point spread, and totals when the provider returns them. It will not mix in college football, tennis, soccer, or other sports.",
        "Español": "Escáner exclusivo de NBA con ganador/moneyline, spread y total cuando el proveedor los devuelve. No mezcla futbol americano universitario, tenis, futbol u otros deportes.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "team": {"English": "Optional team filter", "Español": "Filtro opcional de equipo"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas de apuesta"},
    "events": {"English": "Max NBA events", "Español": "Máximo de eventos NBA"},
    "scan": {"English": "Scan NBA markets", "Español": "Escanear mercados NBA"},
    "none": {"English": "No NBA odds markets were returned. The NBA may not be offered by the provider at this moment, or your key/plan may not include it.", "Español": "No se devolvieron mercados NBA. Puede que el proveedor no ofrezca NBA ahora mismo, o que tu clave/plan no lo incluya."},
    "no_team": {"English": "No NBA market matched that team. Showing all NBA markets found instead.", "Español": "Ningún mercado NBA coincidió con ese equipo. Se mostrarán todos los mercados NBA encontrados."},
    "dashboard": {"English": "NBA dashboard", "Español": "Panel NBA"},
    "matches": {"English": "Team matches", "Español": "Coincidencias del equipo"},
    "all": {"English": "All NBA markets", "Español": "Todos los mercados NBA"},
    "diag": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "raw": {"English": "Moneyline table", "Español": "Tabla de ganador/moneyline"},
    "spread": {"English": "Point spread", "Español": "Spread / hándicap"},
    "totals": {"English": "Game total", "Español": "Total del juego"},
    "pick": {"English": "Market lean", "Español": "Lectura del mercado"},
    "prob": {"English": "Probability", "Español": "Probabilidad"},
    "price": {"English": "Best price", "Español": "Mejor momio"},
    "quality": {"English": "Data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "not_returned": {"English": "not returned", "Español": "no disponible"},
    "feeds_found": {"English": "NBA feeds found", "Español": "Feeds NBA encontrados"},
    "skipped": {"English": "Skipped", "Español": "Omitidos"},
    "markets_requested": {"English": "Markets requested: h2h, spreads, totals", "Español": "Mercados solicitados: ganador, spread y total"},
    "nba_only_note": {"English": "This page only scans NBA feeds. It does not use upcoming all-sports fallback, so college football cannot appear here.", "Español": "Esta página solo escanea feeds de NBA. No usa el fallback de todos los deportes, así que no puede aparecer futbol americano universitario aquí."},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
NBA_ALIASES = {
    "hawks": ["atlanta hawks", "hawks"], "celtics": ["boston celtics", "celtics"], "nets": ["brooklyn nets", "nets"],
    "hornets": ["charlotte hornets", "hornets"], "bulls": ["chicago bulls", "bulls"], "cavaliers": ["cleveland cavaliers", "cavaliers", "cavs"],
    "mavericks": ["dallas mavericks", "mavericks", "mavs"], "nuggets": ["denver nuggets", "nuggets"], "pistons": ["detroit pistons", "pistons"],
    "warriors": ["golden state warriors", "warriors", "gsw"], "rockets": ["houston rockets", "rockets"], "pacers": ["indiana pacers", "pacers"],
    "clippers": ["la clippers", "los angeles clippers", "clippers", "lac"], "lakers": ["los angeles lakers", "la lakers", "lakers", "lal"],
    "grizzlies": ["memphis grizzlies", "grizzlies"], "heat": ["miami heat", "heat"], "bucks": ["milwaukee bucks", "bucks"],
    "timberwolves": ["minnesota timberwolves", "timberwolves", "wolves"], "pelicans": ["new orleans pelicans", "pelicans"],
    "knicks": ["new york knicks", "knicks", "ny knicks"], "thunder": ["oklahoma city thunder", "okc thunder", "thunder"],
    "magic": ["orlando magic", "magic"], "76ers": ["philadelphia 76ers", "76ers", "sixers"], "suns": ["phoenix suns", "suns"],
    "trail blazers": ["portland trail blazers", "trail blazers", "blazers"], "kings": ["sacramento kings", "kings"],
    "spurs": ["san antonio spurs", "spurs"], "raptors": ["toronto raptors", "raptors"], "jazz": ["utah jazz", "jazz"],
    "wizards": ["washington wizards", "wizards"],
}


def t(key):
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def team_aliases(value: str) -> list[str]:
    base = clean(value)
    aliases = {base}
    for key, names in NBA_ALIASES.items():
        cleaned = [clean(name) for name in names]
        if base == clean(key) or base in cleaned:
            aliases.update(cleaned)
    return [a for a in aliases if a]


def match_score(filter_text, event):
    if not filter_text.strip():
        return 1.0, "all"
    aliases = team_aliases(filter_text)
    names = [event.home_team, event.away_team] + [o.name for o in event.outcomes]
    best = 0.0
    matched = ""
    for alias in aliases:
        for name in names:
            a, n = clean(alias), clean(name)
            if not a or not n:
                score = 0.0
            elif a in n:
                score = 1.0
            else:
                ratio = SequenceMatcher(None, a, n).ratio()
                score = ratio if ratio >= 0.88 else 0.0
            if score > best:
                best = score
                matched = f"{alias} -> {name}"
    return best, matched


def safe_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return "clave rechazada" if IS_ES else "key rejected"
    if status == 422:
        return "feed o región no disponible" if IS_ES else "region/feed unavailable"
    if status == 429:
        return "límite de cuota o velocidad" if IS_ES else "quota/rate limit"
    return "falló la solicitud" if IS_ES else "request failed"


def find_nba_sports(sports):
    found = []
    for sport in sports:
        text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
        if "basketball" in text and "nba" in text and not any(x in text for x in ["winner", "championship", "outright"]):
            found.append(sport)
    return found


def scan_resilient(api_key, sport_key, regions, max_events):
    attempts = [",".join(regions)] + regions
    seen = set()
    results = []
    errors = []
    for region in attempts:
        try:
            events = scan_market(api_key, sport_key, regions=region, max_events=max_events, markets="h2h,spreads,totals")
            for event in events:
                key = event.event_id or f"{event.sport_key}:{event.home_team}:{event.away_team}:{event.commence_time}"
                if key not in seen:
                    seen.add(key)
                    results.append(event)
            if results:
                return results, errors
        except Exception as exc:
            errors.append(f"{region}: {safe_error(exc)}")
    return results, errors


def snapshot(event, score, matched):
    top = event.outcomes[0]
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = top.normalized_probability - (second.normalized_probability if second else 0)
    max_range = max((o.price_range or 0.0) for o in event.outcomes)
    quality = max(0, min(100, round(45 + min(event.bookmaker_count, 12) * 3.5 + min(gap, 0.30) * 80 - min(max_range, 1.5) * 6)))
    return {"Event": f"{event.away_team} at {event.home_team}", "Sport": event.sport_title, "Start": event.commence_time, "Pick": top.name, "Probability": f"{top.normalized_probability:.1%}", "Best price": round((top.best_price or top.average_price), 3), "Best book": top.best_bookmaker or "", "Books": event.bookmaker_count, "Data quality": quality, "Match": f"{score:.0%}", "Matched": matched, "_score": score, "_prob": top.normalized_probability, "_event": event}


def market_table(event):
    return [{"Outcome": o.name, "Average price": round(o.average_price, 3), "Best price": round((o.best_price or o.average_price), 3), "Best book": o.best_bookmaker or "", "Probability": f"{o.normalized_probability:.1%}", "Books": o.source_count} for o in event.outcomes]


def line_table(lines):
    return [{"Name": line.name, "Point": "" if line.point is None else line.point, "Average price": round(line.average_price, 3), "Best price": round((line.best_price or line.average_price), 3), "Best book": line.best_bookmaker or "", "Books": line.source_count} for line in (lines or [])]


def headline_line(lines, market_name):
    rows = line_table(lines)
    if not rows:
        return f"{market_name}: {t('not_returned')}"
    first = rows[0]
    return f"{market_name}: {first['Name']} {first['Point']} @ {first['Best price']}"


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Pick']} {row['Probability']} | Q{row['Data quality']}", expanded=expanded):
        st.info(f"{headline_line(event.spreads, t('spread'))} | {headline_line(event.totals, t('totals'))}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["Pick"])
        c2.metric(t("prob"), row["Probability"])
        c3.metric(t("price"), row["Best price"])
        c4.metric(t("quality"), f"{row['Data quality']}/100")
        st.write(f"{t('start')}: {row['Start']}")
        if row["Matched"]:
            st.write(f"{t('matches')}: {row['Matched']}")
        with st.expander(t("spread"), expanded=True):
            spreads = line_table(event.spreads)
            if spreads:
                st.dataframe(spreads, use_container_width=True, hide_index=True)
            else:
                st.caption("Point spread was not returned for this event." if not IS_ES else "El spread no está disponible para este evento.")
        with st.expander(t("totals"), expanded=False):
            totals = line_table(event.totals)
            if totals:
                st.dataframe(totals, use_container_width=True, hide_index=True)
            else:
                st.caption("Game total was not returned for this event." if not IS_ES else "El total del juego no está disponible para este evento.")
        with st.expander(t("raw")):
            st.dataframe(market_table(event), use_container_width=True, hide_index=True)


st.title(t("title"))
st.caption(t("caption"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")

api_key = st.text_input(t("token"), type="password").strip() or saved_key
if not api_key:
    st.info("Paste your provider key." if not IS_ES else "Pega tu clave del proveedor.")
    st.stop()

team = st.text_input(t("team"), "")
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_events = st.number_input(t("events"), min_value=1, max_value=50, value=25, step=1)

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

nba_sports = find_nba_sports(sports)
st.caption(f"{t('feeds_found')}: " + (", ".join([s.title for s in nba_sports]) if nba_sports else "none"))

if st.button(t("scan"), type="primary"):
    if not nba_sports:
        st.error(t("none"))
        st.stop()

    all_events = []
    skipped = []
    for sport in nba_sports:
        events, errors = scan_resilient(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))

    rows = []
    for event in all_events:
        score, matched = match_score(team, event)
        rows.append(snapshot(event, score, matched))

    if team.strip():
        team_rows = [r for r in rows if r["_score"] >= 0.85]
        if not team_rows:
            st.warning(t("no_team"))
            display_rows = rows
        else:
            display_rows = team_rows
    else:
        display_rows = rows

    display_rows = sorted(display_rows, key=lambda r: (r["_score"], r["_prob"], r["Data quality"]), reverse=True)

    if not display_rows:
        st.error(t("none"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped:
                    st.write(f"- {title}: {reason}")
        st.stop()

    st.subheader(t("dashboard"))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("feeds_found"), len(nba_sports))
    c2.metric(t("all"), len(rows))
    c3.metric(t("skipped"), len(skipped))

    tabs = st.tabs([t("matches"), t("all"), t("diag")])
    with tabs[0]:
        for row in display_rows[:20]:
            show_event(row, expanded=row == display_rows[0])
    with tabs[1]:
        st.dataframe([{k: v for k, v in row.items() if not k.startswith("_")} for row in rows], use_container_width=True, hide_index=True)
    with tabs[2]:
        st.write(t("nba_only_note"))
        st.write(t("markets_requested"))
        st.write("NBA sport keys: " + ", ".join([s.key for s in nba_sports]))
        if skipped:
            for title, reason in skipped:
                st.write(f"- {title}: {reason}")
