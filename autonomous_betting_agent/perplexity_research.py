"""Optional Perplexity research context helpers.

The research layer is a supporting signal only and must not create a BET by
itself. Missing keys return neutral context.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.request import Request, urlopen
import json

from .api_config import get_secret

API_URL = "https://api.perplexity.ai/chat/completions"
NEGATIVE_TERMS = ("injury", "injured", "out", "doubtful", "suspended", "rotation", "rest", "travel", "weather", "illness")
POSITIVE_TERMS = ("confirmed lineup", "full strength", "healthy", "available", "motivated", "must win")


def _empty(summary: str = "") -> dict[str, Any]:
    return {
        "research_summary": summary,
        "injury_flags": [],
        "lineup_flags": [],
        "travel_flags": [],
        "weather_flags": [],
        "motivation_flags": [],
        "public_sentiment_flags": [],
        "confidence_adjustment": 0.0,
        "source": "perplexity",
        "warnings": [] if summary else ["PERPLEXITY_API_KEY missing; research context skipped."],
    }


@lru_cache(maxsize=128)
def _ask(prompt: str) -> dict[str, Any]:
    key = get_secret("PERPLEXITY_API_KEY")
    if not key:
        return _empty()
    body = json.dumps({
        "model": "sonar-small-online",
        "messages": [
            {"role": "system", "content": "Summarize sports context concisely. Do not provide betting guarantees."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }).encode("utf-8")
    request = Request(API_URL, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:  # nosec - fixed vendor API endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        data = _empty()
        data["warnings"] = [f"Perplexity request failed: {exc}"]
        return data
    text = ""
    try:
        text = payload["choices"][0]["message"]["content"]
    except Exception:
        text = ""
    data = summarize_research_for_report(text)
    data["raw"] = text
    return data


def research_match_context(game: str, league: str | None = None, teams: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    team_text = ", ".join(teams or [])
    return _ask(f"Research concise match context, injuries, lineups, motivation, travel, weather, and public narrative for {game}. League: {league or ''}. Teams: {team_text}.")


def research_injury_context(team_or_player: str, sport: str | None = None) -> dict[str, Any]:
    return _ask(f"Research recent injury, availability, and suspension context for {team_or_player} in {sport or 'sports'}. Keep it concise.")


def research_lineup_context(game: str, league: str | None = None) -> dict[str, Any]:
    return _ask(f"Research expected and confirmed lineup news for {game} in {league or 'the relevant league'}. Keep it concise.")


def research_game_script_context(game: str, league: str | None = None) -> dict[str, Any]:
    return _ask(f"Research whether the projected game script for {game} in {league or 'the relevant league'} supports favorite control, pressure, corners, cards, tempo, or upset risk. Keep it concise.")


def _flag_lines(text: str, terms: tuple[str, ...]) -> list[str]:
    lines = [line.strip(" -•") for line in text.splitlines() if line.strip()]
    matches = [line for line in lines if any(term in line.lower() for term in terms)]
    if not matches and any(term in text.lower() for term in terms):
        matches = [text[:240]]
    return matches[:5]


def summarize_research_for_report(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return _empty("No research context available.")
    flags = extract_research_flags(text)
    negative_count = sum(len(flags[key]) for key in ("injury_flags", "lineup_flags", "travel_flags", "weather_flags"))
    positive = any(term in text.lower() for term in POSITIVE_TERMS)
    confidence = -0.04 if negative_count >= 2 else -0.02 if negative_count else 0.02 if positive else 0.0
    return {**flags, "research_summary": text[:700], "confidence_adjustment": confidence, "source": "perplexity", "warnings": []}


def extract_research_flags(raw_text: str) -> dict[str, list[str]]:
    text = raw_text or ""
    return {
        "injury_flags": _flag_lines(text, ("injury", "injured", "out", "doubtful", "illness")),
        "lineup_flags": _flag_lines(text, ("lineup", "rotation", "rest", "starter", "bench")),
        "travel_flags": _flag_lines(text, ("travel", "fatigue", "short rest", "road")),
        "weather_flags": _flag_lines(text, ("weather", "rain", "wind", "delay", "heat")),
        "motivation_flags": _flag_lines(text, ("must win", "motivation", "qualified", "eliminated", "clinched")),
        "public_sentiment_flags": _flag_lines(text, ("public", "hype", "popular", "narrative", "overreaction")),
    }
