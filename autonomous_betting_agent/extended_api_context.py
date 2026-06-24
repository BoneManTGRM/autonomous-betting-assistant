from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .live_api_context import LiveAPIContextBuilder, _clean


@dataclass
class ExtendedLiveAPIContextBuilder(LiveAPIContextBuilder):
    """Adds optional contextual APIs without changing core pick logic.

    The extra sources are used only for event context/status fields. Failures are
    contained so Pro Predictor can keep producing rows when optional APIs are
    missing, rate-limited, or unavailable.
    """

    api_football_key: str = ""
    perplexity_key: str = ""
    newsapi_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    perplexity_base_url: str = "https://api.perplexity.ai"
    newsapi_base_url: str = "https://newsapi.org/v2"
    optional_api_timeout_seconds: float = 4.0
    _api_football_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _newsapi_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _perplexity_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _get_json(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[Any, str]:
        try:
            request = Request(url, headers=headers or {})
            with urlopen(request, timeout=self.optional_api_timeout_seconds) as response:  # noqa: S310 - configured trusted API URLs
                return json.loads(response.read().decode("utf-8")), "used"
        except HTTPError as exc:  # pragma: no cover - external API safety
            return {}, f"error_http_{exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:  # pragma: no cover - external API safety
            return {}, f"error: {type(exc).__name__}"
        except Exception as exc:  # pragma: no cover - external API safety
            return {}, f"error: {type(exc).__name__}"

    def _post_json(self, url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> tuple[Any, str]:
        try:
            body = json.dumps(payload).encode("utf-8")
            request = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
            with urlopen(request, timeout=self.optional_api_timeout_seconds) as response:  # noqa: S310 - configured trusted API URLs
                return json.loads(response.read().decode("utf-8")), "used"
        except HTTPError as exc:  # pragma: no cover - external API safety
            return {}, f"error_http_{exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:  # pragma: no cover - external API safety
            return {}, f"error: {type(exc).__name__}"
        except Exception as exc:  # pragma: no cover - external API safety
            return {}, f"error: {type(exc).__name__}"

    def _event_key(self, event: Any) -> str:
        return "|".join(
            _clean(value)
            for value in (
                getattr(event, "sport_key", ""),
                getattr(event, "home_team", ""),
                getattr(event, "away_team", ""),
                getattr(event, "commence_time", ""),
            )
        )

    def _is_soccer_event(self, event: Any) -> bool:
        text = _clean(f"{getattr(event, 'sport_key', '')} {getattr(event, 'sport_title', '')}")
        return "soccer" in text or "football" in text or "fifa" in text

    def _api_football_context(self, event: Any) -> dict[str, Any]:
        configured = bool(self.api_football_key)
        base = {
            "api_football_source_configured": "yes" if configured else "no",
            "api_football_source_used": "no",
            "api_football_context_status": "not_configured" if not configured else "skipped_not_soccer",
        }
        if not configured:
            return base
        if not self._is_soccer_event(event):
            return base
        key = self._event_key(event)
        if key in self._api_football_cache:
            return self._api_football_cache[key]
        home_team = str(getattr(event, "home_team", "") or "")
        away_team = str(getattr(event, "away_team", "") or "")
        headers = {"x-apisports-key": self.api_football_key}
        matches = 0
        statuses: list[str] = []
        for team in (home_team, away_team):
            if not team.strip():
                continue
            url = f"{self.api_football_base_url.rstrip('/')}/teams?{urlencode({'search': team})}"
            payload, status = self._get_json(url, headers=headers)
            statuses.append(status)
            if status == "used" and isinstance(payload, dict):
                response = payload.get("response")
                if isinstance(response, list):
                    matches += len(response[:3])
        status = "used" if matches else ("; ".join(statuses) if statuses else "no_team_query")
        result = {
            **base,
            "api_football_source_used": "yes" if matches else "no",
            "api_football_context_status": status,
            "api_football_team_lookup_count": matches,
            "api_football_context_note": "API-Football team lookup only; contextual enrichment, not pick creation.",
        }
        self._api_football_cache[key] = result
        return result

    def _newsapi_context(self, event: Any) -> dict[str, Any]:
        configured = bool(self.newsapi_key)
        base = {
            "newsapi_source_configured": "yes" if configured else "no",
            "newsapi_source_used": "no",
            "newsapi_context_status": "not_configured" if not configured else "not_run",
        }
        if not configured:
            return base
        key = self._event_key(event)
        if key in self._newsapi_cache:
            return self._newsapi_cache[key]
        home_team = str(getattr(event, "home_team", "") or "")
        away_team = str(getattr(event, "away_team", "") or "")
        query = " ".join(part for part in (home_team, away_team, "injury OR lineup OR news") if part).strip()
        if not query:
            return {**base, "newsapi_context_status": "no_query"}
        params = {"q": query, "pageSize": 3, "sortBy": "publishedAt", "language": "en", "apiKey": self.newsapi_key}
        url = f"{self.newsapi_base_url.rstrip('/')}/everything?{urlencode(params)}"
        payload, status = self._get_json(url)
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        clean_articles = [article for article in articles if isinstance(article, dict)][:3]
        headlines = [str(article.get("title", "")).strip() for article in clean_articles if article.get("title")]
        result = {
            **base,
            "newsapi_source_used": "yes" if headlines and status == "used" else "no",
            "newsapi_context_status": "used" if headlines and status == "used" else status,
            "newsapi_headline_count": len(headlines),
            "newsapi_context_summary": " | ".join(headlines)[:500],
            "newsapi_context_note": "NewsAPI headlines are contextual only and do not create picks.",
        }
        self._newsapi_cache[key] = result
        return result

    def _perplexity_context(self, event: Any) -> dict[str, Any]:
        configured = bool(self.perplexity_key)
        base = {
            "perplexity_source_configured": "yes" if configured else "no",
            "perplexity_source_used": "no",
            "perplexity_context_status": "not_configured" if not configured else "not_run",
        }
        if not configured:
            return base
        key = self._event_key(event)
        if key in self._perplexity_cache:
            return self._perplexity_cache[key]
        home_team = str(getattr(event, "home_team", "") or "")
        away_team = str(getattr(event, "away_team", "") or "")
        sport_title = str(getattr(event, "sport_title", "") or getattr(event, "sport_key", "") or "")
        if not (home_team or away_team):
            return {**base, "perplexity_context_status": "no_query"}
        prompt = (
            "Provide a concise contextual research summary for this sports event. "
            "Do not make a betting pick. Focus only on injuries, lineup/news risk, recent form, and market-moving context. "
            f"Sport: {sport_title}. Event: {away_team} at {home_team}."
        )
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "You provide cautious sports event context only. You never create picks."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 120,
            "temperature": 0.2,
        }
        url = f"{self.perplexity_base_url.rstrip('/')}/chat/completions"
        response, status = self._post_json(url, payload, headers={"Authorization": f"Bearer {self.perplexity_key}"})
        summary = ""
        if isinstance(response, dict):
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else {}
                if isinstance(message, dict):
                    summary = str(message.get("content", "")).strip()
        result = {
            **base,
            "perplexity_source_used": "yes" if summary and status == "used" else "no",
            "perplexity_context_status": "used" if summary and status == "used" else status,
            "perplexity_context_summary": summary[:650],
            "perplexity_context_note": "Perplexity is contextual research only; not a direct pick source.",
        }
        self._perplexity_cache[key] = result
        return result

    def context_for_event(self, event: Any, *, pick_name: str) -> dict[str, Any]:
        context = super().context_for_event(event, pick_name=pick_name)
        context.update(self._api_football_context(event))
        context.update(self._newsapi_context(event))
        context.update(self._perplexity_context(event))
        return context
