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

language = st.selectbox("Language", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Pro Predictor", "Español": "Predictor Pro"},
    "caption": {
        "English": "Main all-sports predictor. It ranks current markets, shows moneyline/spread/total data when available, penalizes weak data and draw/upset risk, tracks session movement, and separates strong reads from avoid spots. Research-only; no guaranteed winners.",
        "Español": "Panel principal de predicción deportiva. Ordena mercados actuales, muestra ganador/spread/total cuando están disponibles, castiga datos débiles y riesgo de empate o sorpresa, rastrea movimiento durante la sesión y separa lecturas fuertes de jugadas que conviene evitar. Solo para investigación; no garantiza ganadores.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "target": {"English": "Scan target", "Español": "Tipo de escaneo"},
    "all": {"English": "All sports", "Español": "Todos los deportes"},
    "league": {"English": "One league/sport", "Español": "Una liga o deporte"},
    "team": {"English": "One team/player", "Español": "Un equipo o jugador"},
    "sport_search": {"English": "Sport/feed search", "Español": "Buscar liga o feed"},
    "team_filter": {"English": "Team/player filter", "Español": "Filtro de equipo o jugador"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas de apuesta"},
    "controls": {"English": "Predictor controls", "Español": "Ajustes del predictor"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de feeds"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por feed"},
    "min_books": {"English": "Minimum books", "Español": "Mínimo de casas"},
    "min_probability": {"English": "Minimum market probability", "Español": "Probabilidad implícita mínima"},
    "scan": {"English": "Run Pro Predictor", "Español": "Ejecutar Predictor Pro"},
    "dashboard": {"English": "Predictor dashboard", "Español": "Panel del predictor"},
    "top": {"English": "Top ranked markets", "Español": "Mejores mercados ordenados"},
    "strong": {"English": "Strong reads", "Español": "Lecturas fuertes"},
    "watch": {"English": "Watch list", "Español": "Solo seguimiento"},
    "avoid": {"English": "Avoid / weak reads", "Español": "Evitar / lecturas débiles"},
    "movement": {"English": "Line movement", "Español": "Movimiento de línea"},
    "all_rows": {"English": "All ranked markets", "Español": "Todos los mercados ordenados"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "no_data": {"English": "No usable markets were returned. Try fewer regions, a broader sport search, or leave the team filter blank.", "Español": "No se encontraron mercados útiles. Prueba con menos regiones, una búsqueda deportiva más amplia o deja vacío el filtro de equipo."},
    "no_match": {"English": "No strong team/player match was found. The app will not pretend unrelated markets match.", "Español": "No se encontró una coincidencia confiable para ese equipo o jugador. La app no mostrará mercados sin relación como si fueran coincidencias."},
    "pick": {"English": "Prediction", "Español": "Predicción"},
    "market_prob": {"English": "Market probability", "Español": "Probabilidad implícita"},
    "score": {"English": "Predictor score", "Español": "Puntaje del predictor"},
    "risk": {"English": "Read", "Español": "Lectura"},
    "best_price": {"English": "Best price", "Español": "Mejor momio"},
    "quality": {"English": "Data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "moneyline": {"English": "Moneyline", "Español": "Ganador / moneyline"},
    "spread": {"English": "Point spread", "Español": "Spread / hándicap"},
    "total": {"English": "Game total", "Español": "Total del juego"},
    "download": {"English": "Download predictor CSV", "Español": "Descargar CSV del predictor"},
    "not_returned": {"English": "Not returned", "Español": "No disponible"},
    "event": {"English": "Event", "Español": "Evento"},
    "sport": {"English": "Sport", "Español": "Deporte"},
    "classification": {"English": "Classification", "Español": "Clasificación"},
    "risk_penalty": {"English": "Risk penalty", "Español": "Risk penalty"},
    "books": {"English": "Books", "Español": "Casas"},
    "draw_probability": {"English": "Draw probability", "Español": "Probabilidad de empate"},
    "match_score": {"English": "Match score", "Español": "Coincidencia"},
    "matched": {"English": "Matched", "Español": "Coincidió"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg price", "Español": "Momio promedio"},
    "best_book": {"English": "Best book", "Español": "Mejor casa"},
    "no_vig_probability": {"English": "No-vig probability", "Español": "Probabilidad sin margen"},
    "name": {"English": "Name", "Español": "Nombre"},
    "point": {"English": "Point", "Español": "Línea"},
    "session_movement": {"English": "Session movement", "Español": "Movimiento en esta sesión"},
    "no_strong": {"English": "No strong reads. That is a valid result.", "Español": "No hay lecturas fuertes. Eso también es un resultado válido."},
    "no_avoid": {"English": "No avoid spots after filters.", "Español": "No hay lecturas para evitar con estos filtros."},
    "no_movement": {"English": "Run another scan later in the same session to see movement.", "Español": "Ejecuta otro escaneo más tarde en esta misma sesión para ver movimiento."},
    "skipped_feeds": {"English": "Skipped feeds", "Español": "Feeds omitidos"},
    "markets": {"English": "Markets", "Español": "Mercados"},
    "skipped": {"English": "Skipped", "Español": "Omitidos"},
    "top_score": {"English": "Top score", "Español": "Puntaje máximo"},
    "feeds_scanned": {"English": "Feeds scanned", "Español": "Feeds escaneados"},
    "events_before_filters": {"English": "Events returned before filters", "Español": "Eventos devueltos antes de filtros"},
    "rows_after_filters": {"English": "Rows after filters", "Español": "Filas después de filtros"},
    "markets_requested": {"English": "Markets requested: h2h, spreads, totals", "Español": "Mercados solicitados: ganador, spread y total"},
    "scoring_note": {"English": "Scoring: market probability + data quality + market gap - sport/draw/thin-market/team-match risk.", "Español": "Puntaje: probabilidad implícita + calidad de datos + ventaja del mercado - riesgo por deporte, empate, mercado débil o mala coincidencia."},
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
    value = unicodedata.normalize("NFKD", str(value or ""))
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
        return "clave rechazada" if IS_ES else "key rejected"
    if status == 422:
        return "feed o región no disponible" if IS_ES else "region/feed unavailable"
    if status == 429:
        return "límite de cuota o velocidad" if IS_ES else "quota/rate limit"
    return "falló la solicitud" if IS_ES else "request failed"


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
        return "Lectura fuerte" if IS_ES else "Strong"
    if row["predictor_score"] < 55 or row["market_probability"] < 0.45:
        return "Evitar" if IS_ES else "Avoid"
    return "Seguimiento" if IS_ES else "Watch"


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
        t("outcome"): outcome.name,
        t("avg_price"): round(outcome.average_price, 3),
        t("best_price"): round((outcome.best_price or outcome.average_price), 3),
        t("best_book"): outcome.best_bookmaker or "",
        t("no_vig_probability"): f"{outcome.normalized_probability:.1%}",
        t("books"): outcome.source_count,
    } for outcome in event.outcomes]


def line_table(lines):
    return [{
        t("name"): line.name,
        t("point"): "" if line.point is None else line.point,
        t("avg_price"): round(line.average_price, 3),
        t("best_price"): round((line.best_price or line.average_price), 3),
        t("best_book"): line.best_bookmaker or "",
        t("books"): line.source_count,
    } for line in (lines or [])]


def headline_line(lines, label):
    rows = line_table(lines)
    if not rows:
        return f"{label}: {t('not_returned')}"
    first = rows[0]
    return f"{label}: {first[t('name')]} {first[t('point')]} @ {first[t('best_price')]}"


def safe_dataframe(rows, empty_message=None):
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption(empty_message or t("not_returned"))


def visible_row(row):
    return {
        t("event"): row["event"],
        t("sport"): row["sport"],
        t("start"): row["start"],
        t("pick"): row["prediction"],
        t("market_prob"): f"{row['market_probability']:.1%}",
        t("score"): row["predictor_score"],
        t("classification"): row["classification"],
        t("quality"): row["data_quality"],
        t("risk_penalty"): row["risk_penalty"],
        t("best_price"): round(row["best_price"], 3),
        t("best_book"): row["best_book"],
        t("books"): row["books"],
        t("draw_probability"): "" if row["draw_probability"] is None else f"{row['draw_probability']:.1%}",
        t("match_score"): f"{row['match_score']:.0%}",
        t("matched"): row["matched"],
    }


def display(row, expanded=False):
    event = row["event_object"]
    with st.expander(f"{row['event']} | {row['prediction']} {row['market_probability']:.1%} | {t('score')} {row['predictor_score']}/100 | {row['classification']}", expanded=expanded):
        st.info(f"{headline_line(event.spreads, t('spread'))} | {headline_line(event.totals, t('total'))}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["prediction"])
        c2.metric(t("market_prob"), f"{row['market_probability']:.1%}")
        c3.metric(t("score"), f"{row['predictor_score']}/100")
        c4.metric(t("risk"), row["classification"])
        st.write(f"{t('start')}: {row['start']}")
        st.write(f"{t('quality')}: {row['data_quality']}/100 | {t('risk_penalty')}: {row['risk_penalty']} | {t('books')}: {row['books']}")
        if row["price_move"] is not None:
            st.write(f"{t('session_movement')}: {t('best_price')} {row['price_move']:+.3f}, {t('market_prob')} {row['probability_move']:+.1%}")
        if row["matched"]:
            st.write(f"{t('matched')}: {row['matched']} | {t('match_score')}: {row['match_score']:.0%}")
        with st.expander(t("spread"), expanded=True):
            safe_dataframe(line_table(event.spreads))
        with st.expander(t("total")):
            safe_dataframe(line_table(event.totals))
        with st.expander(t("moneyline")):
            safe_dataframe(moneyline_table(event))


def csv_text(rows):
    visible = [visible_row(row) for row in rows]
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
    st.info("Pega tu clave del proveedor." if IS_ES else "Paste your provider key.")
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
        status.write(("Escaneando" if IS_ES else "Scanning") + f" {sport.title}...")
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
            with st.expander(t("skipped_feeds"), expanded=True):
                for title, reason in skipped[:60]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    memory = {}
    for row in rows:
        memory[row["key"]] = {"best_price": row["best_price"], "market_probability": row["market_probability"], "seen_at": datetime.now(timezone.utc).isoformat()}
    st.session_state.pro_predictor_memory = memory

    ranked = sorted(rows, key=lambda row: (row["predictor_score"], row["market_probability"], row["data_quality"]), reverse=True)
    strong = [row for row in ranked if (row["classification"] == "Strong" or row["classification"] == "Lectura fuerte")]
    watch = [row for row in ranked if (row["classification"] == "Watch" or row["classification"] == "Seguimiento")]
    avoid = [row for row in sorted(rows, key=lambda row: row["predictor_score"]) if (row["classification"] == "Avoid" or row["classification"] == "Evitar")]
    movers = sorted([row for row in ranked if row["price_move"] is not None], key=lambda row: abs(row["price_move"]), reverse=True)

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("markets"), len(rows))
    c2.metric(t("strong"), len(strong))
    c3.metric(t("skipped"), len(skipped))
    c4.metric(t("top_score"), f"{ranked[0]['predictor_score']}/100")

    st.download_button(t("download"), data=csv_text(ranked), file_name="pro_predictor.csv", mime="text/csv")

    tabs = st.tabs([t("top"), t("strong"), t("watch"), t("avoid"), t("movement"), t("all_rows"), t("diagnostics")])
    with tabs[0]:
        for row in ranked[:25]:
            display(row, expanded=row == ranked[0])
    with tabs[1]:
        if not strong:
            st.info(t("no_strong"))
        for row in strong[:25]:
            display(row)
    with tabs[2]:
        for row in watch[:25]:
            display(row)
    with tabs[3]:
        if not avoid:
            st.info(t("no_avoid"))
        for row in avoid[:25]:
            display(row)
    with tabs[4]:
        if not movers:
            st.info(t("no_movement"))
        for row in movers[:25]:
            display(row)
    with tabs[5]:
        safe_dataframe([visible_row(row) for row in ranked])
    with tabs[6]:
        st.write(f"{t('feeds_scanned')}: {len(selected_sports)}")
        st.write(f"{t('events_before_filters')}: {len(all_events)}")
        st.write(f"{t('rows_after_filters')}: {len(rows)}")
        st.write(t("markets_requested"))
        st.write(t("scoring_note"))
        if skipped:
            for title, reason in skipped[:60]:
                st.write(f"- {title}: {reason}")
