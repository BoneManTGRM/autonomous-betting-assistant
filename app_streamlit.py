import os
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")
st.title("Autonomous Betting Agent")
st.caption("Enter the teams. The agent searches live market data, ranks likely outcomes, and estimates scorelines.")


def read_key(name: str) -> str:
    try:
        return str(st.secrets.get(name, ""))
    except Exception:
        return os.getenv(name, "")


def clean(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def match_score(query: str, candidate: str) -> float:
    query = clean(query)
    candidate = clean(candidate)
    if not query:
        return 0.0
    if query in candidate or candidate in query:
        return 1.0
    return SequenceMatcher(None, query, candidate).ratio()


def event_matches(item, team_one: str, team_two: str) -> bool:
    if not team_one and not team_two:
        return True
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    one_ok = not team_one or max(match_score(team_one, name) for name in names) >= 0.55
    two_ok = not team_two or max(match_score(team_two, name) for name in names) >= 0.55
    return one_ok and two_ok


def show_event(item) -> None:
    st.subheader(f"{item.away_team} at {item.home_team}")
    st.write(f"Start: {item.commence_time}")
    st.write(f"Most likely outcome: {item.favorite} ({item.favorite_probability:.1%})")

    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append(
            {
                "Outcome": outcome.name,
                "Avg market price": round(outcome.average_price, 3),
                "No-vig probability": f"{outcome.normalized_probability:.1%}",
                "Sources": outcome.source_count,
            }
        )
        if outcome.name == item.home_team:
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


api_key = read_key("THE_ODDS_API_KEY")
if not api_key:
    st.warning("Add THE_ODDS_API_KEY in Streamlit secrets to enable autonomous live search.")
    st.code('THE_ODDS_API_KEY = "paste-your-key-here"', language="toml")
    st.stop()

team_one = st.text_input("Team 1", "")
team_two = st.text_input("Team 2", "")
competition = st.text_input("Sport / competition", "soccer")

with st.expander("Advanced settings"):
    region_text = st.text_input("Regions", "us,eu,uk")
    max_events = st.number_input("Max games to scan", min_value=1, max_value=50, value=20, step=1)
    choose_feed = st.checkbox("Choose exact feed", value=False)

with st.spinner("Loading sport feeds"):
    sports = list_sports(api_key, include_all=False)
terms = [term.lower() for term in competition.split() if term.strip()]
choices = []
for sport_item in sports:
    haystack = f"{sport_item.key} {sport_item.group} {sport_item.title} {sport_item.description}".lower()
    if not terms or any(term in haystack for term in terms):
        choices.append(sport_item)
if not choices:
    choices = sports
labels = [f"{sport_item.title} | {sport_item.key}" for sport_item in choices]
if choose_feed:
    selected = st.selectbox("Feed", labels)
    selected_sports = [choices[labels.index(selected)]]
else:
    selected_sports = choices[:3]
    st.caption("Agent will scan the best matching feeds automatically. Use Advanced settings to pick one exact feed.")

if st.button("Run autonomous agent"):
    all_results = []
    with st.spinner("Searching games and building report"):
        for sport_item in selected_sports:
            try:
                all_results.extend(scan_market(api_key, sport_key=sport_item.key, regions=region_text, max_events=int(max_events)))
            except Exception as exc:
                st.warning(f"Skipped {sport_item.title}: {exc}")
    filtered = [item for item in all_results if event_matches(item, team_one, team_two)]
    if not filtered:
        st.info("No matching games found. Try fewer team-name words or a broader competition search like soccer, fifa, nba, nfl, mlb, or tennis.")
    for item in filtered:
        show_event(item)
