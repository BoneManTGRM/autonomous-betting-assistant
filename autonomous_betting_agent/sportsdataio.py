from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

import requests

DEFAULT_BASE_URL = "https://api.sportsdata.io"
DEFAULT_KEY_ENV = "SPORTSDATAIO_API_KEY"


class SportsDataIOError(RuntimeError):
    """Raised when SportsDataIO returns an error or cannot be called safely."""


@dataclass(frozen=True)
class SportsDataIOConfig:
    api_key: str
    sport: str = "nfl"
    subfeed: str = "scores"
    version: str = "v3"
    fmt: str = "json"
    base_url: str = DEFAULT_BASE_URL
    auth_mode: str = "header"
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        sport: str = "nfl",
        subfeed: str = "scores",
        version: str = "v3",
        fmt: str = "json",
        base_url: str = DEFAULT_BASE_URL,
        env_var: str = DEFAULT_KEY_ENV,
        auth_mode: str = "header",
        timeout_seconds: float = 30.0,
    ) -> "SportsDataIOConfig":
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            raise SportsDataIOError(f"Missing SportsDataIO API key. Set {env_var} or pass --api-key.")
        return cls(
            api_key=api_key,
            sport=sport,
            subfeed=subfeed,
            version=version,
            fmt=fmt,
            base_url=base_url,
            auth_mode=auth_mode,
            timeout_seconds=timeout_seconds,
        )


def _clean_segment(value: str) -> str:
    text = str(value or "").strip().strip("/")
    if not text:
        raise SportsDataIOError("Endpoint path, sport, subfeed, version and format cannot be blank.")
    return quote(text, safe="")


def _endpoint_path(endpoint: str) -> str:
    parts = [part for part in str(endpoint or "").strip().strip("/").split("/") if part]
    if not parts:
        raise SportsDataIOError("Endpoint path cannot be blank.")
    return "/".join(quote(part, safe="") for part in parts)


class SportsDataIOClient:
    """Small SportsDataIO HTTP client.

    SportsDataIO has league-specific feeds such as:

    https://api.sportsdata.io/v3/nfl/scores/json/{endpoint}
    https://api.sportsdata.io/v3/nfl/stats/json/{endpoint}

    This client intentionally supports arbitrary endpoints so the repo can work with
    whichever feeds are enabled on the user's SportsDataIO account.
    """

    def __init__(self, config: SportsDataIOConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def build_url(self, endpoint: str, *, sport: str | None = None, subfeed: str | None = None) -> str:
        sport_value = _clean_segment(sport or self.config.sport)
        subfeed_value = _clean_segment(subfeed or self.config.subfeed)
        version_value = _clean_segment(self.config.version)
        fmt_value = _clean_segment(self.config.fmt)
        endpoint_value = _endpoint_path(endpoint)
        return f"{self.config.base_url.rstrip('/')}/{version_value}/{sport_value}/{subfeed_value}/{fmt_value}/{endpoint_value}"

    def get(
        self,
        endpoint: str,
        *,
        sport: str | None = None,
        subfeed: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        query = dict(params or {})
        headers: dict[str, str] = {}
        if self.config.auth_mode == "query":
            query["key"] = self.config.api_key
        else:
            headers["Ocp-Apim-Subscription-Key"] = self.config.api_key

        response = self.session.get(
            self.build_url(endpoint, sport=sport, subfeed=subfeed),
            params=query,
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise SportsDataIOError(f"SportsDataIO request failed with HTTP {response.status_code}: {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise SportsDataIOError("SportsDataIO response was not valid JSON.") from exc

    def scores_by_date(self, day: str, *, sport: str | None = None) -> Any:
        return self.get(f"ScoresByDate/{day}", sport=sport, subfeed="scores")

    def games(self, season: str | int, *, sport: str | None = None) -> Any:
        return self.get(f"Games/{season}", sport=sport, subfeed="scores")

    def teams(self, *, sport: str | None = None) -> Any:
        return self.get("Teams", sport=sport, subfeed="scores")

    def players(self, *, sport: str | None = None) -> Any:
        return self.get("Players", sport=sport, subfeed="scores")

    def raw_endpoint(self, endpoint: str, *, sport: str | None = None, subfeed: str | None = None) -> Any:
        return self.get(endpoint, sport=sport, subfeed=subfeed)


def load_client_from_env(
    *,
    sport: str = "nfl",
    subfeed: str = "scores",
    version: str = "v3",
    fmt: str = "json",
    auth_mode: str = "header",
) -> SportsDataIOClient:
    return SportsDataIOClient(
        SportsDataIOConfig.from_env(
            sport=sport,
            subfeed=subfeed,
            version=version,
            fmt=fmt,
            auth_mode=auth_mode,
        )
    )


def write_json_payload(payload: Any, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def payload_row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return len(value)
        return 1
    return 0
