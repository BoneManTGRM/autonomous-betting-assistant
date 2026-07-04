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
    """Adds optional contextual APIs.
    Core: balldontlie (team/player/injury snapshots, matchup notes).
    Perplexity restored (user context for injuries/lineups/form).
    api_football and newsapi removed (situational/redundant for WNBA focus).
    All failures contained; does not break core pick logic or reports.
    """

    perplexity_key: str = ""
    perplexity_base_url: str = "https://api.perplexity.ai"
    optional_api_timeout_seconds: float = 4.0
    _perplexity_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _balldontlie_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _get_json(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[Any, str]:
        try:
            request = Request(url, headers=headers or {})
            with urlopen(request, timeout=self.optional_api_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8")), "used"
        except HTTPError as exc:
            return {}, f"error_http_{exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {}, f"error: {type(exc).__name__}"
        except Exception as exc:
            return {}, f"error: {type(exc).__name__}"

    def _post_json(self, url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> tuple[Any, str]:
        try:
            body = json.dumps(payload).encode("utf-8")
            request = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
            with urlopen(request, timeout=self.optional_api_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8")), "used"
        except HTTPError as exc:
            return {}, f"error_http_{exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {}, f"error: {type(exc).__name__}"
        except Exception as exc:
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
            "Do not make a selection. Focus only on injuries, lineup/news risk, recent form, and market-moving context. "
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

    def _balldontlie_context(self, event: Any) -> dict[str, Any]:
        key = self._event_key(event)
        if key in self._balldontlie_cache:
            return self._balldontlie_cache[key]
        try:
            from .balldontlie_integration import enrich_row_with_balldontlie
            row = {
                "sport": getattr(event, "sport_title", "") or getattr(event, "sport_key", ""),
                "sport_key": getattr(event, "sport_key", ""),
                "event": f"{getattr(event, 'away_team', '')} at {getattr(event, 'home_team', '')}".strip(),
                "away_team": getattr(event, "away_team", ""),
                "home_team": getattr(event, "home_team", ""),
                "event_start_utc": getattr(event, "commence_time", ""),
                "event_date": str(getattr(event, "commence_time", ""))[:10],
            }
            enriched = enrich_row_with_balldontlie(row)
            status = str(enriched.get("balldontlie_status", "") or "")
            result = {
                "balldontlie_source_configured": "no" if status == "API_KEY_MISSING" else "yes",
                "balldontlie_source_used": "yes" if status == "LIVE" else "no",
                "balldontlie_status": status or "UNKNOWN",
            }
            for field in (
                "balldontlie_sport", "balldontlie_team_summary", "balldontlie_game_summary",
                "balldontlie_injury_summary", "balldontlie_odds_summary", "balldontlie_props_summary",
                "team_stats_summary", "injury_report", "lineup_status", "matchup_notes",
                "sports_context_summary", "player_prop_markets",
            ):
                if field in enriched:
                    result[field] = enriched[field]
        except Exception as exc:
            result = {
                "balldontlie_source_configured": "unknown",
                "balldontlie_source_used": "no",
                "balldontlie_status": f"error: {type(exc).__name__}",
            }
        self._balldontlie_cache[key] = result
        return result

    def context_for_event(self, event: Any, *, pick_name: str) -> dict[str, Any]:
        context = super().context_for_event(event, pick_name=pick_name)
        context.update(self._perplexity_context(event))
        context.update(self._balldontlie_context(event))
        return context
