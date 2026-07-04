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
    """Adds balldontlie context for team/player/injury snapshots and matchup notes.
    Focused on core APIs only: balldontlie (stats/injuries), odds (via api_clients), weather (via api_clients).
    Removed api_football, newsapi, perplexity to eliminate incomplete/optional data issues and simplify reports.
    All extra sources contained; failures do not break core pick logic.
    """

    optional_api_timeout_seconds: float = 4.0
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
        context.update(self._balldontlie_context(event))
        return context
