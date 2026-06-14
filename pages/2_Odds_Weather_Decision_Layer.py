from __future__ import annotations

import os
import unicodedata
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

from autonomous_betting_agent.ara_filters import apply_ara_decision_layer
from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.weatherapi import fetch_weather_snapshot

st.set_page_config(page_title="Odds + Weather Decision Layer", layout="wide")
st.title("Odds + Weather Decision Layer")
st.caption("Uses only The Odds API plus optional WeatherAPI. No additional providers are called.")


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def parse_game(text: str) -> tuple[str, str]:
    padded = f" {text.strip().lower()} "
    for sep in [" vs ", " v ", " versus ", " at ", " @ ", " contra "]:
        if sep in padded:
            left, right = padded.split(sep, 1)
            return left.strip().title(), right.strip().title()
    return "", ""


def match_score(query: str, candidate: str) -> float:
    query = clean(query)
    candidate = clean(candidate)
    if not query or not candidate:
        return 0.0
    if query in candidate or candidate in query:
        return 1.0
    return SequenceMatcher(None, query, candidate).ratio()


def event_score(item, team_one: str, team_two: str) -> float:
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    one = max(match_score(team_one, name) for name in names) if team_one else 0.0
    two = max(match_score(team_two, name) for name in names) if team_two else 0.0
    return (one + two) / 2.0 if team_one and team_two else max(one, two)


def sport_score(sport_item, query: str) -> float:
    haystack = clean(f"{sport_item.key} {sport_item.group} {sport_item.title} {sport_item.description}")
    query = clean(query)
    score = -30.0 if any(word in haystack for word in ["winner", "championship", "outright"]) else 0.0
    for word in query.split():
        if word in haystack:
            score += 8.0
    for popular in ["nba", "nfl", "mlb", "soccer", "nhl", "tennis", "mma", "ufc"]:
        if popular in haystack:
            score += 1.0
    return score


def event_row(item, weather_row: dict | None) -> dict:
    favorite = item.outcomes[0]
    draw_prob = next((outcome.normalized_probability for outcome in item.outcomes if clean(outcome.name) in {"draw", "empate"}), None)
    row = {
        "Event": f"{item.away_team} at {item.home_team}",
        "Sport": item.sport_title,
        "Start": item.commence_time,
        "Prediction": item.favorite,
        "Market probability": favorite.normalized_probability,
        "Classification": "Strong" if favorite.normalized_probability >= 0.60 else "Watch",
        "Data quality": min(100, 65 + item.bookmaker_count * 4),
        "Risk penalty": max(0.0, item.market_overround * 100),
        "Best price": favorite.best_price or favorite.average_price,
        "Books": item.bookmaker_count,
        "Draw probability": draw_prob,
        "result": "pending",
    }
    if weather_row:
        row.update(weather_row)
        row["is_outdoor"] = True
    return row


def explain_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "API key rejected"
    if status == 422:
        return "market or location not available"
    if status == 429:
        return "API quota or rate limit reached"
    return str(exc) or "request failed"


odds_key_default = os.getenv("THE_ODDS_API_KEY", "")
weather_key_default = os.getenv("WEATHERAPI_KEY", "")

with st.sidebar:
    odds_key = st.text_input("The Odds API key", value="", type="password") or odds_key_default
    weather_key = st.text_input("WeatherAPI key", value="", type="password") or weather_key_default
    game_text = st.text_input("Game", "Mexico vs South Korea")
    team_one_default, team_two_default = parse_game(game_text)
    sport_query = st.text_input("Sport search", "soccer")
    weather_location = st.text_input("Weather location / venue city", "")
    regions = st.multiselect("Book regions", ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "uk", "eu"])
    max_feeds = st.number_input("Max sport feeds", min_value=1, max_value=100, value=30)
    max_events = st.number_input("Max events per feed", min_value=1, max_value=50, value=25)
    run = st.button("Run odds + weather layer", type="primary")

if not run:
    st.info("Enter API keys and a game, then run the layer.")
    st.stop()

if not odds_key:
    st.error("Missing The Odds API key.")
    st.stop()

if not regions:
    st.error("Choose at least one odds region.")
    st.stop()

with st.spinner("Loading odds feeds"):
    try:
        sports = list_sports(odds_key, include_all=False)
    except Exception as exc:
        st.error(f"Could not load odds feeds: {explain_error(exc)}")
        st.stop()

ranked = sorted(sports, key=lambda item: sport_score(item, sport_query), reverse=True)[: int(max_feeds)]
results = []
skipped = []
with st.spinner("Scanning odds"):
    for sport in ranked:
        try:
            results.extend(scan_market(odds_key, sport_key=sport.key, regions=",".join(regions), max_events=int(max_events)))
        except Exception as exc:
            skipped.append((sport.title, explain_error(exc)))

team_one, team_two = parse_game(game_text)
scored = sorted([(event_score(item, team_one, team_two), item) for item in results], key=lambda pair: pair[0], reverse=True)
matches = [(score, item) for score, item in scored if score >= 0.55]
if not matches:
    st.warning("No strong match found. Showing closest available events.")
    matches = scored[:5]

if not matches:
    st.error("No events found from the selected feeds.")
    st.stop()

score, selected = matches[0]
weather_row = None
weather_snapshot = None
if weather_key and weather_location:
    with st.spinner("Loading WeatherAPI forecast"):
        try:
            weather_snapshot = fetch_weather_snapshot(weather_key, weather_location, selected.commence_time)
            weather_row = weather_snapshot.to_row()
        except Exception as exc:
            st.warning(f"Weather unavailable: {explain_error(exc)}")

row = event_row(selected, weather_row)
enriched = apply_ara_decision_layer(pd.DataFrame([row]))
record = enriched.iloc[0].to_dict()

st.subheader(f"{selected.away_team} at {selected.home_team}")
cols = st.columns(5)
cols[0].metric("Favorite", selected.favorite)
cols[1].metric("Market probability", f"{selected.favorite_probability:.1%}")
cols[2].metric("Best price", f"{record.get('Best price')}")
cols[3].metric("Decision", record.get("ara_live_decision", ""))
cols[4].metric("Proxy", record.get("ara_proxy_filter_decision", ""))

if weather_snapshot:
    st.write("Weather")
    st.dataframe([weather_snapshot.to_row()], use_container_width=True, hide_index=True)

st.write("Decision layer")
st.dataframe(enriched, use_container_width=True, hide_index=True)

st.write("Market probabilities")
st.dataframe([
    {
        "Outcome": outcome.name,
        "Average price": round(outcome.average_price, 3),
        "Best price": outcome.best_price,
        "No-vig probability": f"{outcome.normalized_probability:.1%}",
        "Books": outcome.source_count,
        "Best book": outcome.best_bookmaker,
    }
    for outcome in selected.outcomes
], use_container_width=True, hide_index=True)

if selected.spreads:
    st.write("Spreads")
    st.dataframe([line.__dict__ for line in selected.spreads[:20]], use_container_width=True, hide_index=True)
if selected.totals:
    st.write("Totals")
    st.dataframe([line.__dict__ for line in selected.totals[:20]], use_container_width=True, hide_index=True)

with st.expander("Diagnostics"):
    st.write(f"Matched game score: {score:.0%}")
    st.write(f"Scanned feeds: {len(ranked)}")
    st.write(f"Events found: {len(results)}")
    if skipped:
        st.write("Skipped feeds")
        st.dataframe([{"feed": feed, "reason": reason} for feed, reason in skipped[:25]], use_container_width=True, hide_index=True)
    st.write("Notes")
    st.write(record.get("ara_notes", ""))
