import csv
import io
import os
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="Pro Predictor", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Pro Predictor", "Español": "Predictor Pro"},
    "caption": {
        "English": "Main all-sports predictor. It ranks current markets, shows moneyline/spread/total data when available, penalizes weak data and draw/upset risk, tracks session movement, and separates strong reads from avoid spots. Research-only; no guaranteed winners.",
        "Español": "Predictor principal multideporte. Ordena mercados actuales, muestra moneyline/spread/total cuando está disponible, penaliza datos débiles y riesgo de empate/sorpresa, rastrea movimiento por sesión y separa lecturas fuertes de situaciones a evitar. Solo investigación; no garantiza ganadores.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "target": {"English": "Scan target", "Español": "Objetivo del escaneo"},
    "all": {"English": "All sports", "Español": "Todos los deportes"},
    "league": {"English": "One league/sport", "Español": "Una liga/deporte"},
    "team": {"English": "One team/player", "Español": "Un equipo/jugador"},
    "sport_search": {"English": "Sport/feed search", "Español": "Buscar deporte/fuente"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo/jugador"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas"},
    "controls": {"English": "Predictor controls", "Español": "Controles del predictor"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de fuentes"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "min_probability": {"English": "Minimum market probability", "Español": "Probabilidad mínima de mercado"},
    "scan": {"English": "Run Pro Predictor", "Español": "Ejecutar Predictor Pro"},
    "dashboard": {"English": "Predictor dashboard", "Español": "Panel del predictor"},
    "top": {"English": "Top ranked markets", "Español": "Mercados principales"},
    "strong": {"English": "Strong reads", "Español": "Lecturas fuertes"},
    "watch": {"English": "Watch list", "Español": "Lista de observación"},
    "avoid": {"English": "Avoid / weak reads", "Español": "Evitar / débiles"},
    "movement": {"English": "Line movement", "Español": "Movimiento de línea"},
    "all_rows": {"English": "All ranked markets", "Español": "Todos los mercados ordenados"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "no_data": {"English": "No usable markets were returned. Try fewer regions, a broader sport search, or leave the team filter blank.", "Español": "No se devolvieron mercados utilizables. Prueba menos regiones, una búsqueda más amplia o deja el filtro vacío."},
    "no_match": {"English": "No strong team/player match was found. The app will not pretend unrelated markets match.", "Español": "No se encontró coincidencia fuerte. La app no fingirá que mercados sin relación coinciden."},
    "pick": {"English": "Prediction", "Español": "Predicción"},
    "market_prob": {"English": "Market probability", "Español": "Probabilidad de mercado"},
    "score": {"English": "Predictor score", "Español": "Puntaje predictor"},
    "risk": {"English": "Read", "Español": "Lectura"},
    "best_price": {"English": "Best price", "Español": "Mejor precio"},
    "quality": {"English": "Data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "moneyline": {"English": "Moneyline", "Español": "Moneyline"},
    "spread": {"English": "Point spread", "Español": "Spread"},
    "total": {"English": "Game total", "Español": "Total del juego"},
    "download": {"English": "Download predictor CSV", "Español": "Descargar CSV del predictor"},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]
POPULAR_FEEDS = [
    "upcoming", "nba", "mlb", "nfl", "ncaaf", "ncaab", "soccer", "fifa", "world cup", "tennis", "nhl",
    "ufc", "mma", "boxing", "cricket", "rugby", "golf", "formula", "nascar",
]
ALIASES = {
    "mexico": ["mexico", "méxico", "mex", "el tri"],
    "chivas": ["chivas", "guadalajara", "cd guadalajara", "club deportivo guadalajara", "deportivo guadalajara"],
    "lakers": ["lakers", "los angeles lakers", "la lakers", "lal"],
    "knicks": ["knicks", "new york knicks", "ny knicks"],
    "spurs": ["spurs", "san antonio spurs"],
    "yankees": ["yankees", "new york yankees", "ny yankees"],
    "cowboys": ["cowboys", "dallas cowboys"],
}


def t(key):
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def alias_terms(value):
    base = clean(value)
    terms = {base}
    for key, values in ALIASES.items():
        cleaned = [clean(v) for v in values]
        if base == clean(key) or base in cleaned:
            terms.update(cleaned)
    return sorted(term for term in terms if term)


def strict_match(filter_text, event):
    if not filter_text.strip():
        return 1.0, "all"
    aliases = alias_terms(filter_text)
    names = [event.home_team, event.away_team] + [outcome.name for outcome in event.outcomes]
    best = 0.0
    matched = ""
    for alias in aliases:
        for name in names:
            a, n = clean(alias), clean(name)
            if not a or not n:
                score = 0.0
            elif len(a) <= 3:
                score = 1.0 if a in set(n.split()) else 0.0
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
        return "key rejected"
    if status == 422:
        return "region/feed unavailable"
    if status == 429:
        return "quota/rate limit"
    return "request failed"


def is_outright(sport):
    text = clean(f"{sport.key} {sport.title} {sport.description}")
    return any(term in text for term in ["winner", "championship", "outright"])


def sport_score(sport, query):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    query_terms = [clean(term) for term in query.split() if clean(term) and clean(term) != "auto"]
    score = -20.0 if is_outright(sport) else 0.0
    if query_terms:
        for term in query_terms:
            score += 15.0 if term in text else SequenceMatcher(None, term, text).ratio()
    else:
        for index, term in enumerate(POPULAR_FEEDS):
            if clean(term) in text:
                score += max(1.0, 12.0 - index * 0.35)
    return score


def sport_risk(event):
    text = clean(f"{event.sport_key} {event.sport_title}")
    if any(term in text for term in ["soccer", "fifa", "world cup"]):
        return 14
    if any(term in text for term in ["baseball", "mlb", "hockey", "nhl"]):
        return 10
    if any(term in text for term in ["tennis", "mma", "ufc", "boxing"]):
        return 7
    return 5


def scan_feed(api_key, sport_key, regions, max_events):
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


def top_non_draw(event):
    return next((outcome for outcome in event.outcomes if clean(outcome.name) != "draw"), event.outcomes[0])


def classify(row):
    if row["predictor_score"] >= 78 and row["market_probability"] >= 0.58 and row["data_quality"] >= 70:
        return "Strong"
    if row["predictor_score"] < 55 or row["market_probability"] < 0.45:
        return "Avoid"
    return "Watch"


def snapshot(event, match_score, matched, previous):
    pick = top_non_draw(event)
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    draw = next((o.normalized_probability for o in event.outcomes if clean(o.name) == "draw"), None)
    gap = event.outcomes[0].normalized_probability - (second.normalized_probability if second else 0.0)
    max_range = max((outcome.price_range or 0.0) for outcome in event.outcomes)
    overround = max(getattr(event, "market_overround", 0.0), 0.0)
    books = event.bookmaker_count
    best_price = pick.best_price or pick.average_price
    data_quality = max(0, min(100, round(45 + min(books, 12) * 3.2 + min(gap, 0.30) * 80 - overround * 110 - min(max_range, 1.5) * 6)))
    risk_penalty = sport_risk(event)
    if draw is not None:
        risk_penalty += int(draw * 30)
    if books < 3:
        risk_penalty += 10
    if match_score < 0.85:
        risk_penalty += 12
    predictor_score = max(0, min(100, round(data_quality + pick.normalized_probability * 35 + gap * 50 - risk_penalty)))
    key = f"{event.event_id}:{pick.name}"
    old = previous.get(key, {})
    price_move = None if "best_price" not in old else best_price - old["best_price"]
    prob_move = None if "market_probability" not in old else pick.normalized_probability - old["market_probability"]
    row = {
        "key": key,
        "event": f"{event.away_team} at {event.home_team}",
        "sport": event.sport_title,
        "start": event.commence_time,
        "prediction": pick.name,
        "market_probability": pick.normalized_probability,
        "predictor_score": predictor_score,
        "data_quality": data_quality,
        "risk_penalty": risk_penalty,
        "best_price": best_price,
        "best_book": pick.best_bookmaker or "",
        "books": books,
        "draw_probability": draw,
        "gap": gap,
        "price_move": price_move,
        "probability_move": prob_move,
        "match_score": match_score,
        "matched": matched,
        "event_object": event,
    }
    row["classification"] = classify(row)
    return row


def moneyline_table(event):
    return [{
        "Outcome": outcome.name,
        "Avg price": round(outcome.average_price, 3),
        "Best price": round((outcome.best_price or outcome.average_price), 3),
        "Best book": outcome.best_bookmaker or "",
        "No-vig probability": f"{outcome.normalized_probability:.1%}",
        "Books": outcome.source_count,
    } for outcome in event.outcomes]


def line_table(lines):
    return [{
        "Name": line.name,
        "Point": "" if line.point is None else line.point,
        "Average price": round(line.average_price, 3),
        "Best price": round((line.best_price or line.average_price), 3),
        "Best book": line.best_bookmaker or "",
        "Books": line.source_count,
    } for line in (lines or [])]


def headline_line(lines, label):
    rows = line_table(lines)
    if not rows:
        return f"{label}: not returned"
    first = rows[0]
    return f"{label}: {first['Name']} {first['Point']} @ {first['Best price']}"


def display(row, expanded=False):
    event = row["event_object"]
    with st.expander(f"{row['event']} | {row['prediction']} {row['market_probability']:.1%} | Score {row['predictor_score']}/100 | {row['classification']}", expanded=expanded):
        st.info(f"{headline_line(event.spreads, t('spread'))} | {headline_line(event.totals, t('total'))}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["prediction"])
        c2.metric(t("market_prob"), f"{row['market_probability']:.1%}")
        c3.metric(t("score"), f"{row['predictor_score']}/100")
        c4.metric(t("risk"), row["classification"])
        st.write(f"{t('start')}: {row['start']}")
        st.write(f"{t('quality')}: {row['data_quality']}/100 | Risk penalty: {row['risk_penalty']} | Books: {row['books']}")
        if row["price_move"] is not None:
            st.write(f"Session movement: price {row['price_move']:+.3f}, probability {row['probability_move']:+.1%}")
        if row["matched"]:
            st.write(f"Matched: {row['matched']} | Match score: {row['match_score']:.0%}")
        with st.expander(t("spread"), expanded=True):
            rows = line_table(event.spreads)
            st.dataframe(rows, use_container_width=True, hide_index=True) if rows else st.caption("Not returned")
        with st.expander(t("total")):
            rows = line_table(event.totals)
            st.dataframe(rows, use_container_width=True, hide_index=True) if rows else st.caption("Not returned")
        with st.expander(t("moneyline")):
            st.dataframe(moneyline_table(event), use_container_width=True, hide_index=True)


def csv_text(rows):
    visible = []
    for row in rows:
        visible.append({
            "Event": row["event"],
            "Sport": row["sport"],
            "Start": row["start"],
            "Prediction": row["prediction"],
            "Market probability": f"{row['market_probability']:.1%}",
            "Predictor score": row["predictor_score"],
            "Classification": row["classification"],
            "Data quality": row["data_quality"],
            "Risk penalty": row["risk_penalty"],
            "Best price": round(row["best_price"], 3),
            "Best book": row["best_book"],
            "Books": row["books"],
            "Draw probability": "" if row["draw_probability"] is None else f"{row['draw_probability']:.1%}",
            "Match score": f"{row['match_score']:.0%}",
        })
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(visible[0].keys()))
    writer.writeheader()
    writer.writerows(visible)
    return output.getvalue()


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

target = st.radio(t("target"), [t("all"), t("league"), t("team")], horizontal=True)
sport_query = st.text_input(t("sport_search"), "auto")
team_filter = st.text_input(t("team_filter"), "") if target == t("team") else ""
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"])

with st.expander(t("controls")):
    min_books = st.number_input(t("min_books"), min_value=1, max_value=25, value=1, step=1)
    min_probability = st.slider(t("min_probability"), min_value=0.0, max_value=1.0, value=0.0, step=0.01)

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked_sports = sorted(sports, key=lambda sport: sport_score(sport, sport_query), reverse=True)
ranked_sports = [sport for sport in ranked_sports if not is_outright(sport)] + [sport for sport in ranked_sports if is_outright(sport)]
max_feeds_default = 40 if target == t("all") else 70 if target == t("team") else 25
max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=120, value=max_feeds_default, step=1)
max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50 if target == t("team") else 25, step=1)
selected_sports = ranked_sports[: int(max_feeds)]
selected_sports = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + selected_sports

if "pro_predictor_memory" not in st.session_state:
    st.session_state.pro_predictor_memory = {}

if st.button(t("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for index, sport in enumerate(selected_sports):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_feed(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((index + 1) / max(1, len(selected_sports)))
    status.empty()
    progress.empty()

    previous = st.session_state.pro_predictor_memory
    rows = []
    for event in all_events:
        score, matched = strict_match(team_filter, event)
        rows.append(snapshot(event, score, matched, previous))

    rows = [row for row in rows if row["books"] >= int(min_books) and row["market_probability"] >= float(min_probability)]
    if team_filter.strip():
        matched_rows = [row for row in rows if row["match_score"] >= 0.85]
        if matched_rows:
            rows = matched_rows
        else:
            st.warning(t("no_match"))
            rows = []

    if not rows:
        st.info(t("no_data"))
        if skipped:
            with st.expander("Skipped feeds", expanded=True):
                for title, reason in skipped[:60]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    memory = {}
    for row in rows:
        memory[row["key"]] = {"best_price": row["best_price"], "market_probability": row["market_probability"], "seen_at": datetime.now(timezone.utc).isoformat()}
    st.session_state.pro_predictor_memory = memory

    ranked = sorted(rows, key=lambda row: (row["predictor_score"], row["market_probability"], row["data_quality"]), reverse=True)
    strong = [row for row in ranked if row["classification"] == "Strong"]
    watch = [row for row in ranked if row["classification"] == "Watch"]
    avoid = [row for row in sorted(rows, key=lambda row: row["predictor_score"]) if row["classification"] == "Avoid"]
    movers = sorted([row for row in ranked if row["price_move"] is not None], key=lambda row: abs(row["price_move"]), reverse=True)

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Markets", len(rows))
    c2.metric("Strong", len(strong))
    c3.metric("Skipped", len(skipped))
    c4.metric("Top score", f"{ranked[0]['predictor_score']}/100")

    st.download_button(t("download"), data=csv_text(ranked), file_name="pro_predictor.csv", mime="text/csv")

    tabs = st.tabs([t("top"), t("strong"), t("watch"), t("avoid"), t("movement"), t("all_rows"), t("diagnostics")])
    with tabs[0]:
        for row in ranked[:25]:
            display(row, expanded=row == ranked[0])
    with tabs[1]:
        if not strong:
            st.info("No strong reads. That is a valid result." if not IS_ES else "No hay lecturas fuertes. Eso es válido.")
        for row in strong[:25]:
            display(row)
    with tabs[2]:
        for row in watch[:25]:
            display(row)
    with tabs[3]:
        if not avoid:
            st.info("No avoid spots after filters." if not IS_ES else "No hay lecturas para evitar.")
        for row in avoid[:25]:
            display(row)
    with tabs[4]:
        if not movers:
            st.info("Run another scan later in the same session to see movement." if not IS_ES else "Ejecuta otro escaneo después para ver movimiento.")
        for row in movers[:25]:
            display(row)
    with tabs[5]:
        st.dataframe([{k: v for k, v in row.items() if k not in ["event_object", "key"]} for row in ranked], use_container_width=True, hide_index=True)
    with tabs[6]:
        st.write(f"Feeds scanned: {len(selected_sports)}")
        st.write(f"Events returned before filters: {len(all_events)}")
        st.write(f"Rows after filters: {len(rows)}")
        st.write("Markets requested: h2h, spreads, totals")
        st.write("Scoring: market probability + data quality + market gap - sport/draw/thin-market/team-match risk.")
        if skipped:
            for title, reason in skipped[:60]:
                st.write(f"- {title}: {reason}")
