from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import builtins
import json
import os
import re
import time

PATCH_VERSION = "balldontlie_integration_v1"
TIMEOUT_SECONDS = 4.0
CACHE_TTL_SECONDS = 300
_SECRET_NAMES = ("BALLDONTLIE_API_KEY", "BDL_API_KEY", "BALLDONTLIE_KEY")
_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, Mapping) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _secret() -> str:
    getter = getattr(builtins, "get_secret", None)
    if callable(getter):
        try:
            value = str(getter(*_SECRET_NAMES) or "").strip()
            if value:
                return value
        except Exception:
            pass
    try:
        import streamlit as st  # type: ignore
        for name in _SECRET_NAMES:
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    for name in _SECRET_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _mask(value: str) -> str:
    return "" if not value else ("***" if len(value) <= 8 else f"{value[:4]}...{value[-4:]}")


def _sport_slug(row: Mapping[str, Any]) -> str:
    text = " ".join(_clean(row.get(k)).lower() for k in ("sport", "league", "competition", "event", "game", "matchup", "event_name"))
    if "wnba" in text:
        return "wnba"
    if "nba" in text or "basketball" in text:
        return "nba"
    if "mlb" in text or "baseball" in text:
        return "mlb"
    return ""


def _base_url(slug: str) -> str:
    if slug == "nba":
        return "https://api.balldontlie.io/v1"
    if slug in {"wnba", "mlb"}:
        return f"https://api.balldontlie.io/{slug}/v1"
    return ""


def _request_json(slug: str, path: str, params: Mapping[str, Any] | None = None) -> Any:
    key = _secret()
    if not key:
        return {"_error": "API_KEY_MISSING"}
    base = _base_url(slug)
    if not base:
        return {"_error": "SPORT_UNSUPPORTED"}
    query = ""
    if params:
        pieces: list[tuple[str, Any]] = []
        for name, value in params.items():
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    if item not in (None, ""):
                        pieces.append((name, item))
            else:
                pieces.append((name, value))
        if pieces:
            query = "?" + urlencode(pieces, doseq=True)
    url = base + path + query
    cache_key = (slug, url)
    cached = _CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    req = Request(url, headers={"Authorization": key, "User-Agent": "ABA-Signal-Pro/1.0"})
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed BALLDONTLIE API host
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        payload = {"_error": exc.__class__.__name__}
    _CACHE[cache_key] = (now, payload)
    return payload


def _data_list(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, Mapping)]
    if isinstance(data, Mapping):
        return [data]
    return []


def _norm(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"\b(the|fc|club|basketball|baseball|team)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _team_names(team: Mapping[str, Any]) -> set[str]:
    names = {
        _clean(team.get("full_name")), _clean(team.get("display_name")), _clean(team.get("short_display_name")),
        _clean(team.get("name")), _clean(team.get("abbreviation")), _clean(team.get("city")), _clean(team.get("location")),
    }
    if team.get("city") and team.get("name"):
        names.add(f"{team.get('city')} {team.get('name')}")
    if team.get("location") and team.get("name"):
        names.add(f"{team.get('location')} {team.get('name')}")
    return {_norm(name) for name in names if _clean(name)}


def _split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _clean(row.get("away_team") or row.get("team_a") or row.get("team1"))
    home = _clean(row.get("home_team") or row.get("team_b") or row.get("team2"))
    if away and home:
        return away, home
    event = _clean(row.get("event") or row.get("game") or row.get("matchup") or row.get("event_name"))
    for sep in (" vs ", " at ", " @ ", " v "):
        if sep in event.lower():
            parts = re.split(re.escape(sep), event, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
    return away, home


def _find_team(teams: Iterable[Mapping[str, Any]], name: str) -> Mapping[str, Any] | None:
    target = _norm(name)
    if not target:
        return None
    best: Mapping[str, Any] | None = None
    best_score = 0
    target_tokens = set(target.split())
    for team in teams:
        for candidate in _team_names(team):
            if not candidate:
                continue
            score = 0
            if candidate == target:
                score = 100
            elif candidate in target or target in candidate:
                score = 80
            else:
                overlap = len(target_tokens & set(candidate.split()))
                score = overlap * 10
            if score > best_score:
                best, best_score = team, score
    return best if best_score >= 10 else None


def _team_label(team: Mapping[str, Any] | None, fallback: str = "team") -> str:
    if not team:
        return fallback
    return _clean(team.get("full_name") or team.get("display_name") or ((str(team.get("city") or team.get("location") or "") + " " + str(team.get("name") or "")).strip()) or team.get("name") or fallback)


def _date_param(row: Mapping[str, Any]) -> str:
    for key in ("event_date", "date", "commence_time", "start_time", "event_start_utc", "game_date"):
        text = _clean(row.get(key))
        if not text:
            continue
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return match.group(0)
    return datetime.now(timezone.utc).date().isoformat()


def _fmt_injury(item: Mapping[str, Any]) -> str:
    player = item.get("player") if isinstance(item.get("player"), Mapping) else {}
    team = player.get("team") if isinstance(player.get("team"), Mapping) else item.get("team") if isinstance(item.get("team"), Mapping) else {}
    name = _clean(player.get("full_name") or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip() or item.get("player_name")) or "Player"
    status = _clean(item.get("status") or item.get("type") or "injury note")
    detail = _clean(item.get("short_comment") or item.get("detail") or item.get("long_comment"))
    team_name = _team_label(team, "team")
    base = f"{name} ({team_name}) {status}"
    if detail:
        base += f": {detail}"
    return base[:170]


def _injury_summary(slug: str, teams: list[Mapping[str, Any]]) -> tuple[str, dict[str, str]]:
    ids = [team.get("id") for team in teams if team and team.get("id")]
    if not ids:
        return "BALLDONTLIE: team match needed before injury lookup.", {}
    payload = _request_json(slug, "/player_injuries", {"team_ids[]": ids, "per_page": 8})
    if isinstance(payload, Mapping) and payload.get("_error"):
        return f"BALLDONTLIE injuries checked; {payload.get('_error')}.", {}
    injuries = _data_list(payload)
    if not injuries:
        return "BALLDONTLIE injuries checked; no active injury rows returned for matched teams.", {}
    by_team: dict[str, list[str]] = {}
    for item in injuries[:8]:
        player = item.get("player") if isinstance(item.get("player"), Mapping) else {}
        team = player.get("team") if isinstance(player.get("team"), Mapping) else {}
        team_name = _team_label(team, "team")
        by_team.setdefault(team_name, []).append(_fmt_injury(item))
    flat = [note for notes in by_team.values() for note in notes]
    return "BALLDONTLIE injuries: " + " | ".join(flat[:3]), {name: " | ".join(notes[:3]) for name, notes in by_team.items()}


def _game_summary(slug: str, row: Mapping[str, Any], teams: list[Mapping[str, Any]]) -> tuple[str, str, str]:
    date = _date_param(row)
    team_ids = [team.get("id") for team in teams if team and team.get("id")]
    payload = _request_json(slug, "/games", {"dates[]": [date], "team_ids[]": team_ids, "per_page": 10})
    if isinstance(payload, Mapping) and payload.get("_error"):
        return f"BALLDONTLIE games checked; {payload.get('_error')}.", "", ""
    games = _data_list(payload)
    if not games:
        return f"BALLDONTLIE games checked for {date}; no matched game returned.", "", ""
    game = games[0]
    home = game.get("home_team") if isinstance(game.get("home_team"), Mapping) else {}
    away = game.get("visitor_team") if isinstance(game.get("visitor_team"), Mapping) else game.get("away_team") if isinstance(game.get("away_team"), Mapping) else {}
    status = _clean(game.get("status") or game.get("period") or "scheduled")
    score = ""
    if game.get("home_score") is not None or game.get("away_score") is not None:
        score = f" score {game.get('away_score', '')}-{game.get('home_score', '')}"
    return f"BALLDONTLIE game matched: {_team_label(away)} at {_team_label(home)} · {status}{score}.", str(game.get("id") or ""), date


def _odds_summary(slug: str, game_id: str = "", date: str = "") -> str:
    params: dict[str, Any] = {"per_page": 5}
    if game_id:
        params["game_ids[]"] = [game_id]
    elif date:
        params["dates[]"] = [date]
    else:
        return "BALLDONTLIE odds lookup skipped; no game ID or date."
    payload = _request_json(slug, "/odds", params)
    if isinstance(payload, Mapping) and payload.get("_error"):
        return f"BALLDONTLIE odds checked; {payload.get('_error')}."
    odds = _data_list(payload)
    if not odds:
        return "BALLDONTLIE odds checked; no sportsbook odds rows returned."
    first = odds[0]
    vendor = _clean(first.get("vendor") or first.get("sportsbook") or first.get("book") or first.get("bookmaker")) or "book"
    market = _clean(first.get("market") or first.get("type") or first.get("bet_type") or first.get("name")) or "market"
    return f"BALLDONTLIE odds: {len(odds)} rows returned; first row {vendor} {market}."


def _props_markets(slug: str, game_id: str) -> tuple[str, list[dict[str, Any]]]:
    if not game_id:
        return "BALLDONTLIE props lookup skipped; no BALLDONTLIE game ID.", []
    payload = _request_json(slug, "/odds/player_props", {"game_id": game_id, "per_page": 10})
    if isinstance(payload, Mapping) and payload.get("_error"):
        return f"BALLDONTLIE player props checked; {payload.get('_error')}.", []
    props = _data_list(payload)
    if not props:
        return "BALLDONTLIE player props checked; no prop rows returned.", []
    markets: list[dict[str, Any]] = []
    for item in props[:10]:
        player = item.get("player") if isinstance(item.get("player"), Mapping) else {}
        name = _clean(player.get("full_name") or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip() or item.get("player_name"))
        market = _clean(item.get("prop_type") or item.get("market") or item.get("type") or "player prop")
        line = _clean(item.get("line") or item.get("value") or item.get("point") or item.get("threshold"))
        vendor = _clean(item.get("vendor") or item.get("sportsbook") or item.get("book") or "BALLDONTLIE")
        odds = item.get("odds") or item.get("price") or item.get("decimal_odds") or item.get("american_odds")
        markets.append({
            "provider": "BALLDONTLIE",
            "sportsbook": vendor,
            "provider_event_id": game_id,
            "market": market,
            "selection": f"{name} {market}".strip(),
            "line": line,
            "odds": odds,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_note": "BALLDONTLIE player prop row; ABA still requires prop-specific model probability before playable status.",
        })
    return f"BALLDONTLIE player props: {len(props)} prop rows returned; model probability still required before playable status.", markets


def _append_unique(existing: Any, addition: str) -> str:
    current = _clean(existing)
    if not current:
        return addition
    if addition.lower() in current.lower():
        return current
    return current + " | " + addition


def enrich_row_with_balldontlie(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    slug = _sport_slug(row)
    if not slug:
        row.setdefault("balldontlie_status", "SPORT_UNSUPPORTED")
        return row
    if not _secret():
        row.setdefault("balldontlie_status", "API_KEY_MISSING")
        row.setdefault("balldontlie_failure_reason", "BALLDONTLIE_API_KEY or BDL_API_KEY missing")
        return row
    teams_payload = _request_json(slug, "/teams", {"per_page": 100})
    if isinstance(teams_payload, Mapping) and teams_payload.get("_error"):
        row["balldontlie_status"] = "API_ERROR"
        row["balldontlie_failure_reason"] = str(teams_payload.get("_error"))
        return row
    teams = _data_list(teams_payload)
    away_name, home_name = _split_teams(row)
    away_team = _find_team(teams, away_name)
    home_team = _find_team(teams, home_name)
    matched_teams = [team for team in (away_team, home_team) if team]
    if not matched_teams:
        row["balldontlie_status"] = "NO_TEAM_MATCH"
        row["balldontlie_team_summary"] = f"BALLDONTLIE checked {slug.upper()}; no team match for {away_name or 'away'} / {home_name or 'home'}."
        return row
    row["balldontlie_status"] = "LIVE"
    row["balldontlie_sport"] = slug.upper()
    row["balldontlie_team_summary"] = f"BALLDONTLIE matched teams: {_team_label(away_team, away_name)} / {_team_label(home_team, home_name)}."
    game_summary, game_id, game_date = _game_summary(slug, row, matched_teams)
    injury_summary, injuries_by_team = _injury_summary(slug, matched_teams)
    odds_summary = _odds_summary(slug, game_id, game_date)
    props_summary, prop_markets = _props_markets(slug, game_id)
    row["balldontlie_game_summary"] = game_summary
    row["balldontlie_injury_summary"] = injury_summary
    row["balldontlie_odds_summary"] = odds_summary
    row["balldontlie_props_summary"] = props_summary
    row["sports_context_summary"] = _append_unique(row.get("sports_context_summary"), row["balldontlie_team_summary"] + " " + game_summary)
    row["team_stats_summary"] = _append_unique(row.get("team_stats_summary"), row["balldontlie_team_summary"])
    row["matchup_notes"] = _append_unique(row.get("matchup_notes"), game_summary)
    row["injury_report"] = _append_unique(row.get("injury_report"), injury_summary)
    row["lineup_status"] = _append_unique(row.get("lineup_status"), injury_summary)
    if away_team:
        away_label = _team_label(away_team, away_name)
        row["away_team_form"] = _append_unique(row.get("away_team_form"), f"BALLDONTLIE matched {away_label}; game/status context checked.")
        row["away_injuries"] = _append_unique(row.get("away_injuries"), injuries_by_team.get(away_label, injury_summary))
    if home_team:
        home_label = _team_label(home_team, home_name)
        row["home_team_form"] = _append_unique(row.get("home_team_form"), f"BALLDONTLIE matched {home_label}; game/status context checked.")
        row["home_injuries"] = _append_unique(row.get("home_injuries"), injuries_by_team.get(home_label, injury_summary))
    if prop_markets:
        existing = row.get("player_prop_markets")
        if isinstance(existing, list):
            row["player_prop_markets"] = existing + prop_markets
        else:
            row["player_prop_markets"] = prop_markets
    active = _clean(row.get("api_sources_active") or row.get("api_sources_used"))
    row["api_sources_active"] = _append_unique(active, "BALLDONTLIE") if active else "BALLDONTLIE"
    row["context_source"] = _append_unique(row.get("context_source"), "BALLDONTLIE")
    row["last_api_refresh_time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return row


def _patch_live_enrichment() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    if getattr(live, "_ABA_BALLDONTLIE_PATCH", "") == PATCH_VERSION:
        return
    try:
        live.API_SECRET_DEFS["BALLDONTLIE"] = _SECRET_NAMES
    except Exception:
        pass
    original_row = getattr(live, "enrich_row_with_live_api_data", None)
    original_rows = getattr(live, "enrich_rows_with_live_api_data", None)
    original_health = getattr(live, "check_api_health", None)

    def row_with_bdl(row_like: Any, *args: Any, **kwargs: Any):
        row = original_row(row_like, *args, **kwargs) if callable(original_row) else _row(row_like)
        return enrich_row_with_balldontlie(row)

    def rows_with_bdl(rows: list[Any] | tuple[Any, ...]):
        enriched = original_rows(rows) if callable(original_rows) else [_row(row) for row in rows]
        return [enrich_row_with_balldontlie(row) for row in enriched]

    def health_with_bdl(mask_secrets: bool = True):
        out = original_health(mask_secrets) if callable(original_health) else {}
        key = _secret()
        out["BALLDONTLIE"] = {"status": "CONFIGURED" if key else "API_KEY_MISSING", "key": _mask(key) if mask_secrets and key else ("present" if key else "")}
        return out

    live.enrich_row_with_live_api_data = row_with_bdl
    live.enrich_rows_with_live_api_data = rows_with_bdl
    live.check_api_health = health_with_bdl
    live._ABA_BALLDONTLIE_PATCH = PATCH_VERSION


def _patch_magazine_sources() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as magazine
    except Exception:
        return
    try:
        magazine.API_SECRET_DEFS["BALLDONTLIE"] = _SECRET_NAMES
    except Exception:
        pass
    try:
        if not any(item[0] == "BALLDONTLIE" for item in magazine.API_SOURCE_DEFS):
            magazine.API_SOURCE_DEFS = tuple(magazine.API_SOURCE_DEFS) + ((
                "BALLDONTLIE",
                ("balldontlie_status", "balldontlie_live", "balldontlie_enabled"),
                ("balldontlie_team_summary", "balldontlie_injury_summary", "balldontlie_game_summary", "balldontlie_props_summary"),
                ("player_prop_markets", "balldontlie_odds_summary"),
                False,
            ),)
    except Exception:
        pass


def install(module: Any | None = None) -> None:
    _patch_live_enrichment()
    _patch_magazine_sources()
    if module is not None:
        try:
            module.API_SECRET_DEFS["BALLDONTLIE"] = _SECRET_NAMES
        except Exception:
            pass
