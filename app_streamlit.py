import os
import unicodedata
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")
st.title("Autonomous Betting Agent")
st.caption("Paste a provider token, enter two teams, and let the agent search feeds, rank likely outcomes, and estimate scorelines.")

COUNTRY_ALIASES = {
    "mexico": ["mexico", "méxico", "mexican", "el tri"],
    "south korea": ["south korea", "korea republic", "republic of korea", "korea"],
    "usa": ["usa", "united states", "usmnt", "united states of america"],
    "united states": ["usa", "united states", "usmnt", "united states of america"],
    "england": ["england", "english"],
    "brazil": ["brazil", "brasil"],
    "germany": ["germany", "deutschland"],
    "spain": ["spain", "españa"],
    "argentina": ["argentina"],
    "france": ["france"],
    "japan": ["japan"],
}


def read_provider_token() -> str:
    try:
        return str(st.secrets.get("THE_ODDS_API_KEY", ""))
    except Exception:
        return os.getenv("THE_ODDS_API_KEY", "")


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def aliases(value: str) -> list[str]:
    base = clean(value)
    values = {base}
    for key, alias_list in COUNTRY_ALIASES.items():
        if base == clean(key) or base in [clean(alias) for alias in alias_list]:
            values.update(clean(alias) for alias in alias_list)
    return [item for item in values if item]


def is_known_country(value: str) -> bool:
    base = clean(value)
    for key, alias_list in COUNTRY_ALIASES.items():
        if base == clean(key) or base in [clean(alias) for alias in alias_list]:
            return True
    return False


def match_score(query: str, candidate: str) -> float:
    query = clean(query)
    candidate = clean(candidate)
    if not query or not candidate:
        return 0.0
    if query in candidate or candidate in query:
        return 1.0
    return SequenceMatcher(None, query, candidate).ratio()


def best_name_score(query: str, names: list[str]) -> float:
    if not query:
        return 1.0
    return max(match_score(alias, name) for alias in aliases(query) for name in names)


def event_score(item, team_one: str, team_two: str) -> float:
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    one_score = best_name_score(team_one, names)
    two_score = best_name_score(team_two, names)
    if team_one and team_two:
        return (one_score + two_score) / 2.0
    return max(one_score, two_score)


def sport_score(sport_item, competition: str, team_one: str, team_two: str) -> float:
    haystack = clean(f"{sport_item.key} {sport_item.group} {sport_item.title} {sport_item.description}")
    words = [clean(word) for word in competition.split() if clean(word)]
    score = 0.0
    for word in words:
        if word in haystack:
            score += 4.0
    national_matchup = is_known_country(team_one) and is_known_country(team_two)
    if national_matchup:
        for word in ["international", "world", "fifa", "cup", "friendlies", "concacaf", "uefa"]:
            if word in haystack:
                score += 6.0
        for domestic_word in ["serie", "division", "league", "liga", "campeonato", "superleague"]:
            if domestic_word in haystack and "international" not in haystack and "world" not in haystack:
                score -= 3.0
    return score


def explain_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "provider token was rejected"
    if status == 422:
        return "feed is not available for the selected market regions"
    if status == 429:
        return "provider quota or rate limit reached"
    return "provider request failed"


def show_event(item, score: float | None = None) -> None:
    st.subheader(f"{item.away_team} at {item.home_team}")
    if score is not None:
        st.write(f"Team-match confidence: {score:.0%}")
    st.write(f"Start: {item.commence_time}")
    st.write(f"Most likely outcome: {item.favorite} ({item.favorite_probability:.1%})")

    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append({"Outcome": outcome.name, "Avg market price": round(outcome.average_price, 3), "No-vig probability": f"{outcome.normalized_probability:.1%}", "Sources": outcome.source_count})
        if clean(outcome.name) == clean(item.home_team):
            home_probability = outcome.normalized_probability
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if home_probability is not None:
        home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
        score_rows = []
        for pick in estimate_scorelines(home_xg, away_xg):
            if pick.margin > 0:
                spread = f"{item.home_team} by {pick.margin}"
            elif pick.margin < 0:
                spread = f"{item.away_team} by {abs(pick.margin)}"
            else:
                spread = "Draw"
            score_rows.append({"Score": pick.label, "Spread": spread, "Probability": f"{pick.probability:.1%}"})
        st.write("Most likely scorelines / spread")
        st.dataframe(score_rows, use_container_width=True, hide_index=True)

    with st.expander("ARA cycle notes"):
        for note in item.cycle_notes:
            st.write(f"- {note}")
    st.caption("Research estimate only. This uses market data until team-stat, injury, lineup, and weather providers are added.")


saved_token = read_provider_token()
entry_token = st.text_input("Provider access token", value="", type="password")
provider_token = entry_token.strip() or saved_token
if not provider_token:
    st.info("Paste your own provider access token above. It is used only for this browser session unless the app owner configures one separately.")
    st.stop()

team_one = st.text_input("Team 1", "")
team_two = st.text_input("Team 2", "")
competition = st.text_input("Sport / competition", "international soccer")

with st.expander("Advanced settings"):
    selected_regions = st.multiselect("Market regions", ["us", "uk", "eu", "au"], default=["us", "eu", "uk"])
    max_feeds = st.number_input("Max feeds to scan", min_value=1, max_value=30, value=12, step=1)
    max_events = st.number_input("Max games per feed", min_value=1, max_value=50, value=30, step=1)
    show_nearest = st.checkbox("Show closest games if no exact match", value=True)

if st.button("Run autonomous agent", type="primary"):
    if not selected_regions:
        st.error("Choose at least one market region.")
        st.stop()

    with st.spinner("Loading and ranking sport feeds"):
        try:
            sports = list_sports(provider_token, include_all=False)
        except Exception as exc:
            st.error(f"Could not load sport feeds: {explain_error(exc)}")
            st.stop()

    ranked_sports = sorted(
        sports,
        key=lambda item: sport_score(item, competition, team_one, team_two),
        reverse=True,
    )
    candidate_sports = ranked_sports[: int(max_feeds)]
    region_text = ",".join(selected_regions)
    all_results = []
    skipped = []

    with st.spinner("Searching games and building report"):
        for sport_item in candidate_sports:
            try:
                all_results.extend(scan_market(provider_token, sport_key=sport_item.key, regions=region_text, max_events=int(max_events)))
            except Exception as exc:
                skipped.append((sport_item.title, explain_error(exc)))

    scored = sorted(
        [(event_score(item, team_one, team_two), item) for item in all_results],
        key=lambda pair: pair[0],
        reverse=True,
    )
    matches = [(score, item) for score, item in scored if score >= 0.55]

    st.write(f"Scanned {len(candidate_sports)} feeds and found {len(all_results)} games with market data.")
    if skipped:
        with st.expander(f"Skipped {len(skipped)} feeds"):
            for title, reason in skipped[:20]:
                st.write(f"- {title}: {reason}")

    if matches:
        for score, item in matches[:10]:
            show_event(item, score)
    else:
        st.info("No exact team match found. The provider may not have this game yet, or the team names may be listed differently.")
        if show_nearest and scored:
            st.write("Closest games found")
            for score, item in scored[:5]:
                show_event(item, score)
        else:
            st.write("Try competition terms like international soccer, fifa, world cup, concacaf, nba, nfl, mlb, tennis, or choose more market regions.")
