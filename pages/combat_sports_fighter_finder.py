import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="Combat Sports Fighter Finder", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Combat Sports Fighter Finder", "Español": "Buscador de Peleadores"},
    "caption": {
        "English": "Boxing, UFC, and MMA market finder. It searches provider-returned combat sports markets and matches fighter names strictly so unrelated events are not shown as matches.",
        "Español": "Buscador de mercados de boxeo, UFC y MMA. Busca mercados de deportes de combate devueltos por el proveedor y hace coincidencias estrictas por nombre para no mostrar peleas sin relación.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "mode": {"English": "Search mode", "Español": "Modo de búsqueda"},
    "all": {"English": "All combat markets", "Español": "Todos los mercados de combate"},
    "fighter": {"English": "One fighter", "Español": "Un peleador"},
    "fighter_name": {"English": "Fighter name", "Español": "Nombre del peleador"},
    "preset": {"English": "Known fighter shortcut", "Español": "Atajo de peleador conocido"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas de apuesta"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de feeds"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por feed"},
    "scan": {"English": "Scan combat markets", "Español": "Escanear mercados de combate"},
    "no_data": {"English": "No combat sports odds markets were returned. Try more regions, leave the fighter blank, or check whether the provider currently has boxing/UFC markets.", "Español": "No se devolvieron mercados de combate. Prueba más regiones, deja el peleador vacío o revisa si el proveedor tiene mercados de boxeo/UFC ahora mismo."},
    "no_match": {"English": "No current market matched that fighter. This usually means the provider did not return that fighter in the scanned markets right now.", "Español": "Ningún mercado actual coincidió con ese peleador. Normalmente significa que el proveedor no devolvió a ese peleador en los mercados escaneados ahora mismo."},
    "dashboard": {"English": "Combat dashboard", "Español": "Panel de combate"},
    "matches": {"English": "Fighter matches", "Español": "Coincidencias del peleador"},
    "all_markets": {"English": "All combat markets", "Español": "Todos los mercados de combate"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "pick": {"English": "Market lean", "Español": "Lectura del mercado"},
    "prob": {"English": "Probability", "Español": "Probabilidad"},
    "price": {"English": "Best price", "Español": "Mejor momio"},
    "quality": {"English": "Data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "moneyline": {"English": "Moneyline", "Español": "Ganador / moneyline"},
    "feeds_scanned": {"English": "Feeds scanned", "Español": "Feeds escaneados"},
    "markets_returned": {"English": "Markets returned", "Español": "Mercados devueltos"},
    "fighter_markets": {"English": "Fighter markets found", "Español": "Mercados del peleador"},
    "skipped": {"English": "Skipped feeds", "Español": "Feeds omitidos"},
    "not_available": {"English": "Not available", "Español": "No disponible"},
    "note": {"English": "This page can search any custom fighter name. The preset list only adds aliases for common names; it is not required for matching.", "Español": "Esta página puede buscar cualquier nombre escrito manualmente. La lista de atajos solo agrega alias de nombres comunes; no es necesaria para hacer coincidencias."},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]

# This list is intentionally broad but not claimed to be complete. Custom search still works for any fighter returned by the odds provider.
FIGHTER_ALIASES = {
    # UFC / MMA
    "Alex Pereira": ["alex pereira", "poatan"],
    "Jon Jones": ["jon jones", "bones jones", "bones"],
    "Tom Aspinall": ["tom aspinall", "aspinall"],
    "Islam Makhachev": ["islam makhachev", "makhachev"],
    "Ilia Topuria": ["ilia topuria", "topuria", "el matador"],
    "Sean O'Malley": ["sean o'malley", "sean omalley", "omalley", "sugar sean"],
    "Merab Dvalishvili": ["merab dvalishvili", "merab"],
    "Dricus Du Plessis": ["dricus du plessis", "du plessis", "ddp"],
    "Khamzat Chimaev": ["khamzat chimaev", "chimaev", "borz"],
    "Israel Adesanya": ["israel adesanya", "adesanya", "izzy", "stylebender"],
    "Robert Whittaker": ["robert whittaker", "whittaker", "bobby knuckles"],
    "Leon Edwards": ["leon edwards", "rocky edwards"],
    "Belal Muhammad": ["belal muhammad", "belal"],
    "Shavkat Rakhmonov": ["shavkat rakhmonov", "shavkat", "nomad"],
    "Kamaru Usman": ["kamaru usman", "usman", "nigerian nightmare"],
    "Colby Covington": ["colby covington", "covington"],
    "Max Holloway": ["max holloway", "holloway", "blessed"],
    "Alexander Volkanovski": ["alexander volkanovski", "volkanovski", "volk"],
    "Charles Oliveira": ["charles oliveira", "oliveira", "do bronx"],
    "Dustin Poirier": ["dustin poirier", "poirier", "diamond"],
    "Justin Gaethje": ["justin gaethje", "gaethje", "highlight"],
    "Conor McGregor": ["conor mcgregor", "mcgregor", "notorious"],
    "Michael Chandler": ["michael chandler", "chandler"],
    "Arman Tsarukyan": ["arman tsarukyan", "tsarukyan"],
    "Beneil Dariush": ["beneil dariush", "dariush"],
    "Jiri Prochazka": ["jiri prochazka", "prochazka"],
    "Jamahal Hill": ["jamahal hill", "hill", "sweet dreams"],
    "Magomed Ankalaev": ["magomed ankalaev", "ankalaev"],
    "Ciryl Gane": ["ciryl gane", "gane", "bon gamin"],
    "Sergei Pavlovich": ["sergei pavlovich", "pavlovich"],
    "Francis Ngannou": ["francis ngannou", "ngannou", "predator"],
    "Stipe Miocic": ["stipe miocic", "miocic"],
    "Brandon Moreno": ["brandon moreno", "moreno", "assassin baby"],
    "Alexandre Pantoja": ["alexandre pantoja", "pantoja"],
    "Brandon Royval": ["brandon royval", "royval"],
    "Deiveson Figueiredo": ["deiveson figueiredo", "figueiredo"],
    "Petr Yan": ["petr yan", "yan"],
    "Cory Sandhagen": ["cory sandhagen", "sandhagen"],
    "Marlon Vera": ["marlon vera", "chito vera", "vera"],
    "Aljamain Sterling": ["aljamain sterling", "sterling", "funk master"],
    "Amanda Nunes": ["amanda nunes", "nunes", "lioness"],
    "Valentina Shevchenko": ["valentina shevchenko", "shevchenko", "bullet"],
    "Zhang Weili": ["zhang weili", "weili", "magnum"],
    "Tatiana Suarez": ["tatiana suarez", "suarez"],
    "Alexa Grasso": ["alexa grasso", "grasso"],
    "Rose Namajunas": ["rose namajunas", "namajunas", "thug rose"],
    "Joanna Jedrzejczyk": ["joanna jedrzejczyk", "joanna"],
    "Kayla Harrison": ["kayla harrison", "harrison"],
    "Holly Holm": ["holly holm", "holm"],
    "Ronda Rousey": ["ronda rousey", "rousey"],
    # Boxing
    "Canelo Alvarez": ["canelo alvarez", "saul alvarez", "saúl álvarez", "canelo"],
    "Terence Crawford": ["terence crawford", "crawford", "bud crawford", "bud"],
    "Oleksandr Usyk": ["oleksandr usyk", "usyk"],
    "Tyson Fury": ["tyson fury", "fury", "gypsy king"],
    "Anthony Joshua": ["anthony joshua", "joshua", "aj"],
    "Deontay Wilder": ["deontay wilder", "wilder", "bronze bomber"],
    "Dmitry Bivol": ["dmitry bivol", "bivol"],
    "Artur Beterbiev": ["artur beterbiev", "beterbiev"],
    "Gervonta Davis": ["gervonta davis", "tank davis", "tank"],
    "Shakur Stevenson": ["shakur stevenson", "shakur"],
    "Ryan Garcia": ["ryan garcia", "king ry", "ryan"],
    "Devin Haney": ["devin haney", "haney", "dream"],
    "Teofimo Lopez": ["teofimo lopez", "teófimo lópez", "teofimo", "lopez"],
    "Vasiliy Lomachenko": ["vasiliy lomachenko", "vasyl lomachenko", "lomachenko", "loma"],
    "Naoya Inoue": ["naoya inoue", "inoue", "monster"],
    "Junto Nakatani": ["junto nakatani", "nakatani"],
    "Jesse Rodriguez": ["jesse rodriguez", "bam rodriguez", "bam"],
    "Roman Gonzalez": ["roman gonzalez", "román gonzález", "chocolatito"],
    "Juan Francisco Estrada": ["juan francisco estrada", "gallo estrada", "estrada"],
    "Errol Spence Jr": ["errol spence", "errol spence jr", "spence"],
    "Jaron Ennis": ["jaron ennis", "boots ennis", "boots"],
    "Vergil Ortiz Jr": ["vergil ortiz", "vergil ortiz jr", "ortiz jr"],
    "Sebastian Fundora": ["sebastian fundora", "fundora", "towering inferno"],
    "Tim Tszyu": ["tim tszyu", "tszyu"],
    "Jermell Charlo": ["jermell charlo", "charlo"],
    "Jermall Charlo": ["jermall charlo"],
    "David Benavidez": ["david benavidez", "benavidez", "mexican monster"],
    "David Morrell": ["david morrell", "morrell"],
    "Caleb Plant": ["caleb plant", "plant", "sweet hands"],
    "Jaime Munguia": ["jaime munguia", "jaime munguía", "munguia"],
    "Edgar Berlanga": ["edgar berlanga", "berlanga"],
    "Christian Mbilli": ["christian mbilli", "mbilli"],
    "Joseph Parker": ["joseph parker", "parker"],
    "Daniel Dubois": ["daniel dubois", "dubois"],
    "Zhilei Zhang": ["zhilei zhang", "big bang zhang", "zhang"],
    "Jai Opetaia": ["jai opetaia", "opetaia"],
    "Mairis Briedis": ["mairis briedis", "briedis"],
    "Katie Taylor": ["katie taylor", "taylor"],
    "Amanda Serrano": ["amanda serrano", "serrano"],
    "Claressa Shields": ["claressa shields", "shields", "gwoat"],
}


def t(key):
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def fighter_aliases(value: str) -> list[str]:
    base = clean(value)
    aliases = {base}
    for key, names in FIGHTER_ALIASES.items():
        cleaned = [clean(name) for name in names]
        if base == clean(key) or base in cleaned:
            aliases.update(cleaned)
    return sorted(alias for alias in aliases if alias)


def match_score(filter_text, event):
    if not filter_text.strip():
        return 1.0, "all"
    aliases = fighter_aliases(filter_text)
    names = [event.home_team, event.away_team] + [outcome.name for outcome in event.outcomes]
    best = 0.0
    matched = ""
    for alias in aliases:
        for name in names:
            a, n = clean(alias), clean(name)
            if not a or not n:
                score = 0.0
            elif a in n or n in a:
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
        return "feed or region unavailable" if not IS_ES else "feed o región no disponible"
    if status == 429:
        return "quota/rate limit" if not IS_ES else "límite de cuota o velocidad"
    return "request failed" if not IS_ES else "falló la solicitud"


def is_combat_sport(sport):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    combat_terms = ["boxing", "box", "ufc", "mma", "mixed martial", "pfl", "bellator", "combat", "fight"]
    return any(term in text for term in combat_terms) and not any(term in text for term in ["winner", "championship", "outright"])


def combat_score(sport):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    score = 0
    for term in ["ufc", "mma", "boxing", "mixed martial", "pfl", "bellator", "fight"]:
        if term in text:
            score += 10
    return score


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


def snapshot(event, score, matched):
    top = event.outcomes[0]
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = top.normalized_probability - (second.normalized_probability if second else 0)
    max_range = max((outcome.price_range or 0.0) for outcome in event.outcomes)
    quality = max(0, min(100, round(45 + min(event.bookmaker_count, 12) * 3.5 + min(gap, 0.30) * 80 - min(max_range, 1.5) * 6)))
    return {
        "Event": f"{event.away_team} at {event.home_team}",
        "Sport": event.sport_title,
        "Start": event.commence_time,
        "Pick": top.name,
        "Probability": f"{top.normalized_probability:.1%}",
        "Best price": round((top.best_price or top.average_price), 3),
        "Best book": top.best_bookmaker or "",
        "Books": event.bookmaker_count,
        "Data quality": quality,
        "Match": f"{score:.0%}",
        "Matched": matched,
        "_score": score,
        "_prob": top.normalized_probability,
        "_event": event,
    }


def market_table(event):
    return [{
        "Outcome": outcome.name,
        "Average price": round(outcome.average_price, 3),
        "Best price": round((outcome.best_price or outcome.average_price), 3),
        "Best book": outcome.best_bookmaker or "",
        "Probability": f"{outcome.normalized_probability:.1%}",
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


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Pick']} {row['Probability']} | Q{row['Data quality']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["Pick"])
        c2.metric(t("prob"), row["Probability"])
        c3.metric(t("price"), row["Best price"])
        c4.metric(t("quality"), f"{row['Data quality']}/100")
        st.write(f"{t('start')}: {row['Start']}")
        if row["Matched"]:
            st.write(f"Matched: {row['Matched']}")
        with st.expander(t("moneyline"), expanded=True):
            st.dataframe(market_table(event), use_container_width=True, hide_index=True)
        with st.expander("Spreads / totals", expanded=False):
            spreads = line_table(event.spreads)
            totals = line_table(event.totals)
            if spreads:
                st.write("Spread")
                st.dataframe(spreads, use_container_width=True, hide_index=True)
            if totals:
                st.write("Total")
                st.dataframe(totals, use_container_width=True, hide_index=True)
            if not spreads and not totals:
                st.caption(t("not_available"))


st.title(t("title"))
st.caption(t("caption"))
st.info(t("note"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")

api_key = st.text_input(t("token"), type="password").strip() or saved_key
if not api_key:
    st.info("Paste your provider key." if not IS_ES else "Pega tu clave del proveedor.")
    st.stop()

mode = st.radio(t("mode"), [t("all"), t("fighter")], horizontal=True)
known_names = [""] + sorted(FIGHTER_ALIASES.keys())
preset = st.selectbox(t("preset"), known_names, index=0)
manual = st.text_input(t("fighter_name"), preset)
fighter_query = manual.strip() if mode == t("fighter") else ""
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=80, value=40, step=1)
max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50, step=1)

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

combat_sports = sorted([sport for sport in sports if is_combat_sport(sport)], key=combat_score, reverse=True)
selected_sports = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + combat_sports[: int(max_feeds)]

if st.button(t("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for index, sport in enumerate(selected_sports):
        status.write(("Escaneando" if IS_ES else "Scanning") + f" {sport.title}...")
        events, errors = scan_feed(api_key, sport.key, regions, int(max_events))
        for event in events:
            event_text = clean(f"{event.sport_key} {event.sport_title} {event.home_team} {event.away_team} " + " ".join([o.name for o in event.outcomes]))
            if sport.key == "upcoming":
                if not any(term in event_text for term in ["ufc", "mma", "boxing", "box", "fight", "pfl", "bellator"]):
                    continue
            all_events.append(event)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((index + 1) / max(1, len(selected_sports)))
    status.empty()
    progress.empty()

    rows = []
    for event in all_events:
        score, matched = match_score(fighter_query, event)
        rows.append(snapshot(event, score, matched))

    if fighter_query:
        fighter_rows = [row for row in rows if row["_score"] >= 0.85]
        if not fighter_rows:
            st.warning(t("no_match"))
            display_rows = []
        else:
            display_rows = fighter_rows
    else:
        display_rows = rows

    display_rows = sorted(display_rows, key=lambda row: (row["_score"], row["_prob"], row["Data quality"]), reverse=True)

    if not display_rows:
        st.error(t("no_data"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped[:60]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds_scanned"), len(selected_sports))
    c2.metric(t("markets_returned"), len(rows))
    c3.metric(t("fighter_markets"), len(display_rows))
    c4.metric(t("skipped"), len(skipped))

    tabs = st.tabs([t("matches"), t("all_markets"), t("diagnostics")])
    with tabs[0]:
        for row in display_rows[:30]:
            show_event(row, expanded=row == display_rows[0])
    with tabs[1]:
        st.dataframe([{k: v for k, v in row.items() if not k.startswith("_")} for row in rows], use_container_width=True, hide_index=True)
    with tabs[2]:
        st.write("Combat feeds: " + ", ".join([sport.title for sport in combat_sports]) if combat_sports else "No dedicated combat feeds found.")
        st.write("Scanned: upcoming + dedicated combat feeds.")
        st.write("Custom fighter search works even if the fighter is not in the preset list, as long as the provider returns that name.")
        if fighter_query:
            st.write("Aliases used: " + ", ".join(fighter_aliases(fighter_query)))
        if skipped:
            for title, reason in skipped[:60]:
                st.write(f"- {title}: {reason}")
