"""Optional NewsAPI context helpers for late risk signals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from .api_config import get_secret

API_URL = "https://newsapi.org/v2/everything"
RISK_TERMS = {
    "injury_news": ("injury", "injured", "out", "doubtful", "illness"),
    "lineup_news": ("lineup", "starter", "rotation", "bench", "rest"),
    "suspension_news": ("suspended", "suspension", "ban", "red card"),
    "travel_news": ("travel", "fatigue", "road", "short rest"),
    "coaching_news": ("coach", "manager", "tactics", "formation"),
    "motivation_news": ("must win", "qualified", "eliminated", "clinched", "motivation"),
    "weather_news": ("weather", "rain", "wind", "delay", "storm", "heat"),
}


def _empty(summary: str = "No relevant recent news found.") -> dict[str, Any]:
    return {
        "news_summary": summary,
        "injury_news": [],
        "lineup_news": [],
        "suspension_news": [],
        "travel_news": [],
        "coaching_news": [],
        "motivation_news": [],
        "weather_news": [],
        "confidence_adjustment": 0.0,
        "source": "newsapi",
        "warnings": [] if summary == "No relevant recent news found." else [summary],
    }


@lru_cache(maxsize=128)
def _fetch(query: str, days_back: int = 3) -> dict[str, Any]:
    key = get_secret("NEWSAPI_KEY")
    if not key:
        data = _empty("NEWSAPI_KEY missing; recent news context skipped.")
        return data
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).date().isoformat()
    params = urlencode({"q": query, "from": from_date, "language": "en", "sortBy": "publishedAt", "pageSize": 10})
    request = Request(f"{API_URL}?{params}", headers={"X-Api-Key": key})
    try:
        with urlopen(request, timeout=15) as response:  # nosec - fixed vendor API endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return _empty(f"NewsAPI request failed: {exc}")
    if payload.get("status") not in (None, "ok"):
        return _empty(f"NewsAPI returned status {payload.get('status')}: {payload.get('message', '')}")
    articles = payload.get("articles") or []
    summary = summarize_news_context(articles)
    flags = extract_news_risk_flags(articles)
    confidence = -0.05 if flags.get("injury_news") or flags.get("suspension_news") else -0.02 if any(flags.values()) else 0.0
    return {**flags, "news_summary": summary, "confidence_adjustment": confidence, "source": "newsapi", "warnings": []}


def fetch_recent_team_news(team: str, sport: str | None = None, days_back: int = 3) -> dict[str, Any]:
    return _fetch(f"{team} {sport or ''} injury lineup news", days_back)


def fetch_recent_player_news(player: str, sport: str | None = None, days_back: int = 3) -> dict[str, Any]:
    return _fetch(f"{player} {sport or ''} injury availability news", days_back)


def fetch_recent_match_news(game: str, teams: list[str] | tuple[str, ...] | None = None, days_back: int = 3) -> dict[str, Any]:
    query = game if not teams else f"{game} {' '.join(teams)} injury lineup news"
    return _fetch(query, days_back)


def _article_text(article: Mapping[str, Any]) -> str:
    return " ".join(str(article.get(key) or "") for key in ("title", "description", "content"))


def summarize_news_context(articles: list[Mapping[str, Any]]) -> str:
    if not articles:
        return "No relevant recent news found."
    summaries = []
    for article in articles[:5]:
        title = str(article.get("title") or "Untitled")
        source = article.get("source", {}) if isinstance(article.get("source"), Mapping) else {}
        source_name = source.get("name") or "source"
        summaries.append(f"{title} ({source_name})")
    return "; ".join(summaries)[:800]


def extract_news_risk_flags(articles: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    flags = {key: [] for key in RISK_TERMS}
    for article in articles or []:
        text = _article_text(article)
        lower = text.lower()
        title = str(article.get("title") or text[:160])
        for key, terms in RISK_TERMS.items():
            if any(term in lower for term in terms):
                flags[key].append(title)
    return {key: values[:5] for key, values in flags.items()}
