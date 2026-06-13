import os

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.title("Live market scanner")

try:
    saved_token = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_token = os.getenv("THE_ODDS_API_KEY", "")

entry_token = st.text_input("Provider access token", value="", type="password")
key = entry_token.strip() or saved_token

if not key:
    st.info("Paste your own provider access token above. It is used only for this browser session unless the app owner configures one separately.")
else:
    region_text = st.text_input("Regions", "us,eu,uk")
    search_text = st.text_input("Sport search", "soccer")
    max_events = st.number_input("Max events", min_value=1, max_value=50, value=15, step=1)
    sports = list_sports(key, include_all=False)
    terms = [x.lower() for x in search_text.split() if x.strip()]
    choices = []
    for item in sports:
        text = f"{item.key} {item.group} {item.title} {item.description}".lower()
        if not terms or any(term in text for term in terms):
            choices.append(item)
    if not choices:
        choices = sports
    labels = [f"{item.title} | {item.key}" for item in choices]
    selected = st.selectbox("Sport feed", labels)
    sport_key = choices[labels.index(selected)].key
    if st.button("Scan"):
        results = scan_market(key, sport_key, regions=region_text, max_events=int(max_events))
        for item in results:
            st.subheader(f"{item.away_team} at {item.home_team}")
            st.write(f"Most likely: {item.favorite} ({item.favorite_probability:.1%})")
            rows = []
            home_probability = None
            for outcome in item.outcomes:
                rows.append({"Outcome": outcome.name, "Price": round(outcome.average_price, 3), "Probability": f"{outcome.normalized_probability:.1%}"})
                if outcome.name == item.home_team:
                    home_probability = outcome.normalized_probability
            st.dataframe(rows, use_container_width=True, hide_index=True)
            if home_probability is not None:
                home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
                score_rows = []
                for pick in estimate_scorelines(home_xg, away_xg):
                    if pick.margin > 0:
                        margin = f"{item.home_team} by {pick.margin}"
                    elif pick.margin < 0:
                        margin = f"{item.away_team} by {abs(pick.margin)}"
                    else:
                        margin = "Draw"
                    score_rows.append({"Score": pick.label, "Spread": margin, "Probability": f"{pick.probability:.1%}"})
                st.write("Most likely scorelines / spread")
                st.dataframe(score_rows, use_container_width=True, hide_index=True)
            st.caption("Market-based scan only. Add injuries, lineups, weather and team ratings before trusting a pick.")
