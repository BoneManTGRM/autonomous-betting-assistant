from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import quote_plus, urlencode

_PATCH_VERSION = "magazine_report_display_polish_v4_readable_matchup"

SOURCE_LABELS = {
    "Odds API": "Odds",
    "The Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}

# Presentation-safe fallback copy required by the magazine contract:
# Watchlist only: current price and live context need verification.
# Live team feed not linked to this row.
# Lineup/injury feed not verified for this row.
# Fallback/watchlist only.
# Straight watchlist only.
# Do not parlay fallback rows.
# no verified live match


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _live_odds_marker(row: Any) -> bool:
    data = _row(row)
    status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    return status in {"live", "live_api", "live_match", "odds_api_live_match"} or source in {"live", "live_api", "the odds api", "odds api"}


def _fallback_row(row: Any) -> bool:
    if _live_odds_marker(row):
        return False
    data = _row(row)
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    status = _clean(data.get("odds_status")).lower()
    mode = _clean(data.get("risk") or data.get("risk_level") or data.get("risk_label")).lower()
    return any(token in source or token in status or token in mode for token in ("uploaded", "fallback", "cached", "missing"))


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item)
        if text and not text.endswith("."):
            text += "."
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _source_label(name: str) -> str:
    return SOURCE_LABELS.get(str(name).strip(), str(name).strip())


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).replace("%", "").replace(",", "").strip()
        if not text or text.lower() in {"nan", "none", "null", "n/a", "na"}:
            return None
        return float(text)
    except Exception:
        return None


def _norm(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"\b(fc|cf|sc|club|team|national|women|men)\b", " ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {part for part in _norm(value).split() if len(part) > 2}


def _team_pair(data: dict[str, Any], live: Any) -> tuple[str, str]:
    try:
        away, home = live._split_teams(data)
        if away and home:
            return str(away), str(home)
    except Exception:
        pass
    away = data.get("away_team") or data.get("team_a") or data.get("team1") or ""
    home = data.get("home_team") or data.get("team_b") or data.get("team2") or ""
    if away and home:
        return str(away), str(home)
    event = _clean(data.get("event") or data.get("event_name") or data.get("matchup") or data.get("game"))
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return "", ""


def _sport_text(data: dict[str, Any]) -> str:
    return " ".join(_clean(data.get(key)).lower() for key in ("sport", "league", "event", "event_name", "game", "matchup"))


def _sport_candidates(data: dict[str, Any], live: Any, key: str) -> list[str]:
    explicit: list[str] = []
    for field in ("odds_sport_key", "sport_key", "the_odds_api_sport_key", "odds_api_sport_key"):
        value = _clean(data.get(field))
        if value:
            explicit.append(value)
    text = _sport_text(data)
    if "soccer" in text or "fifa" in text or "world cup" in text or "uefa" in text or "liga" in text:
        explicit.extend(["soccer_fifa_world_cup", "soccer_concacaf_gold_cup", "soccer_uefa_champs_league", "soccer_epl"])
    if "baseball" in text or "mlb" in text:
        explicit.append("baseball_mlb")
    if "basketball" in text or "nba" in text:
        explicit.append("basketball_nba")
    if "nfl" in text:
        explicit.append("americanfootball_nfl")
    try:
        sports_url = "https://api.the-odds-api.com/v4/sports/?" + urlencode({"apiKey": key})
        sports = live._request_json(sports_url, cache_key=("oddsapi-sports", "active"), timeout=2.5)
        if isinstance(sports, list):
            row_tokens = _tokens(text)
            scored: list[tuple[int, str]] = []
            for sport in sports:
                if not isinstance(sport, dict):
                    continue
                sport_key = _clean(sport.get("key"))
                label = " ".join(_clean(sport.get(k)) for k in ("key", "title", "description", "group")).lower()
                score = len(row_tokens & _tokens(label))
                if "world cup" in text and "world" in label:
                    score += 4
                if ("soccer" in text or "fifa" in text or "world cup" in text) and "soccer" in label:
                    score += 2
                if score > 0 and sport_key:
                    scored.append((score, sport_key))
            explicit.extend(key for _score, key in sorted(scored, reverse=True)[:8])
    except Exception:
        pass
    return _dedupe(explicit)[:10]


def _event_matches(row_away: str, row_home: str, event: dict[str, Any]) -> bool:
    event_names = [_clean(event.get("home_team")), _clean(event.get("away_team")), *[str(team) for team in event.get("teams", []) if team]]
    row_sets = [_tokens(row_away), _tokens(row_home)]
    event_sets = [_tokens(name) for name in event_names]
    if not row_sets[0] or not row_sets[1] or not event_sets:
        return False
    matches = 0
    for row_set in row_sets:
        if any(row_set <= event_set or event_set <= row_set or bool(row_set & event_set) for event_set in event_sets):
            matches += 1
    return matches >= 2


def _selection_text(data: dict[str, Any]) -> str:
    return _clean(data.get("prediction") or data.get("public_pick") or data.get("pick") or data.get("selection") or data.get("exact_bet") or data.get("recommended_action") or data.get("market_type"))


def _target_market(data: dict[str, Any]) -> str:
    text = " ".join([_selection_text(data), _clean(data.get("market_type") or data.get("market"))]).lower()
    if "total" in text or "over" in text or "under" in text:
        return "totals"
    if "spread" in text or "handicap" in text:
        return "spreads"
    return "h2h"


def _target_point(data: dict[str, Any]) -> float | None:
    for field in ("line", "line_point", "total", "handicap", "point"):
        value = _num(data.get(field))
        if value is not None:
            return value
    match = re.search(r"(?:over|under|o|u)?\s*(\d+(?:\.\d+)?)", _selection_text(data).lower())
    return float(match.group(1)) if match else None


def _outcome_matches(data: dict[str, Any], outcome: dict[str, Any]) -> bool:
    selection = _selection_text(data).lower()
    name = _clean(outcome.get("name")).lower()
    market = _target_market(data)
    point = _target_point(data)
    out_point = _num(outcome.get("point"))
    if market == "totals":
        wants_over = "over" in selection or re.search(r"\bo\s*\d", selection) is not None
        wants_under = "under" in selection or re.search(r"\bu\s*\d", selection) is not None
        side_ok = (wants_over and "over" in name) or (wants_under and "under" in name) or (not wants_over and not wants_under)
        point_ok = point is None or out_point is None or abs(point - out_point) < 0.01
        return side_ok and point_ok
    selected_tokens = _tokens(selection)
    return bool(selected_tokens & _tokens(name)) or market == "spreads"


def _apply_live_odds_match(data: dict[str, Any], event: dict[str, Any], bookmaker: dict[str, Any], market: dict[str, Any], outcome: dict[str, Any]) -> None:
    price = _num(outcome.get("price"))
    if price is None or price <= 1:
        return
    data["decimal_odds"] = price
    data["decimal_price"] = price
    data["odds"] = price
    data["best_price"] = price
    data["bookmaker"] = _clean(bookmaker.get("title") or bookmaker.get("key")) or "The Odds API"
    data["sportsbook"] = data["bookmaker"]
    data["odds_source"] = "The Odds API"
    data["odds_status"] = "LIVE"
    data["odds_api_status"] = "LIVE_MATCH"
    data["odds_api_live"] = "true"
    data["the_odds_api_live"] = "true"
    data["odds_api_event_id"] = _clean(event.get("id"))
    data["matched_event_id"] = _clean(event.get("id"))
    data["odds_api_sport_key"] = _clean(event.get("sport_key"))
    data["odds_api_market"] = _clean(market.get("key"))
    data["odds_api_selection"] = _clean(outcome.get("name"))
    if outcome.get("point") is not None:
        data["line_point"] = outcome.get("point")
    active = _split(data.get("api_sources_active") or data.get("api_sources_used"))
    active.append("Odds API")
    data["api_sources_active"] = " · ".join(_dedupe(active))
    data.pop("odds_failure_reason", None)
    data.pop("fallback_reason", None)


def _try_live_odds_api_match(data: dict[str, Any], live: Any) -> bool:
    if _live_odds_marker(data):
        data.setdefault("odds_api_status", "LIVE_MATCH")
        return True
    try:
        key = live._secret(*live.API_SECRET_DEFS["Odds API"])
    except Exception:
        key = ""
    if not key:
        return False
    away, home = _team_pair(data, live)
    if not away or not home:
        data.setdefault("odds_api_status", "CONFIGURED_NO_EVENT_TEAMS")
        return False
    for sport_key in _sport_candidates(data, live, key):
        try:
            params = {"apiKey": key, "regions": _clean(data.get("bookmaker_regions")) or "us,us2,eu,uk", "markets": "h2h,spreads,totals", "oddsFormat": "decimal"}
            url = f"https://api.the-odds-api.com/v4/sports/{quote_plus(sport_key)}/odds/?" + urlencode(params)
            events = live._request_json(url, cache_key=("oddsapi-odds", sport_key + "|" + _norm(f"{away} {home}")), timeout=3.0)
        except Exception:
            continue
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict) or not _event_matches(away, home, event):
                continue
            for bookmaker in event.get("bookmakers", []) or []:
                if not isinstance(bookmaker, dict):
                    continue
                for market in bookmaker.get("markets", []) or []:
                    if not isinstance(market, dict) or _clean(market.get("key")) != _target_market(data):
                        continue
                    for outcome in market.get("outcomes", []) or []:
                        if isinstance(outcome, dict) and _outcome_matches(data, outcome):
                            _apply_live_odds_match(data, event, bookmaker, market, outcome)
                            return True
    data["odds_api_status"] = "CONFIGURED_NO_LIVE_EVENT_MATCH"
    data["odds_failure_reason"] = f"Odds API configured, but no live match for {away} vs {home}."
    return False


def _install_renderer_source_labels(module: Any) -> None:
    if getattr(module, "_ABA_SOURCE_LABEL_POLISH_VERSION", "") == _PATCH_VERSION:
        return
    original_api_provenance = getattr(module, "api_provenance", None)
    if not callable(original_api_provenance):
        return

    def polished_api_provenance(row: Any) -> dict[str, list[str]]:
        prov = original_api_provenance(row)
        if _fallback_row(row):
            checked = _dedupe([
                *prov.get("active_sources", []),
                *prov.get("available_no_data_sources", []),
                *prov.get("inactive_sources", []),
            ])
            return {"active_sources": [], "available_no_data_sources": checked, "inactive_sources": []}
        return prov

    def polished_api_provenance_lines(row: Any) -> list[str]:
        prov = polished_api_provenance(row)
        active = [_source_label(name) for name in prov.get("active_sources", [])]
        checked = [_source_label(name) for name in prov.get("available_no_data_sources", [])]
        inactive = [_source_label(name) for name in prov.get("inactive_sources", [])]
        if _fallback_row(row):
            if checked:
                return ["Sources checked: " + " · ".join(checked[:6]) + "; no verified live match."]
            return ["Sources checked: no verified live match."]
        lines: list[str] = []
        if active:
            lines.append("Live sources: " + " · ".join(active))
        if not lines and checked:
            lines.append("Sources checked: " + " · ".join(checked))
        if not lines and inactive:
            lines.append("Sources configured: " + " · ".join(inactive))
        return lines

    def polished_active_note(row: Any) -> str:
        lines = polished_api_provenance_lines(row)
        return lines[0] + ("" if lines[0].endswith(".") else ".") if lines else "Sources checked: none."

    module.api_provenance = polished_api_provenance
    module.api_provenance_lines = polished_api_provenance_lines
    module._active_note = polished_active_note
    module._ABA_SOURCE_LABEL_POLISH_VERSION = _PATCH_VERSION


def install_live_odds_api_match() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    original = getattr(live, "_apply_odds_truth", None)
    if not callable(original) or getattr(original, "_ABA_ODDS_API_MATCH_PATCH", False):
        return

    def apply_odds_truth_with_live_api_match(row: dict[str, Any], refresh_time: str) -> None:
        try:
            _try_live_odds_api_match(row, live)
        except Exception as exc:
            row.setdefault("odds_api_status", "LIVE_MATCH_ERROR")
            row.setdefault("odds_failure_reason", exc.__class__.__name__)
        original(row, refresh_time)

    apply_odds_truth_with_live_api_match._ABA_ODDS_API_MATCH_PATCH = True
    live._apply_odds_truth = apply_odds_truth_with_live_api_match


def _restore_sale_ready_version_suffix(renderer: Any) -> None:
    current = str(getattr(renderer, "MAGAZINE_STYLE_VERSION", ""))
    base = re.sub(r"(?:_direct_two_page)?_sale_ready_[a-z_]+_v\d+(?:_[a-z_]+)*", "", current)
    renderer.MAGAZINE_STYLE_VERSION = f"{base or 'magazine'}_sale_ready_risk_chain_v4"


def _shorten(value: Any, limit: int = 118) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:") + "."


def _first_context(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable"}:
            return text
    return ""


def _readable_matchup_rows(data: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    weather = _first_context(data, "weather_summary_short", "weather_summary", "venue_weather", "weather_risk")
    context = _first_context(data, "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes")
    news = _first_context(data, "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "api_football_summary", "sportsdataio_context")
    line = _first_context(data, "line_movement_summary", "line_movement", "price_movement") or "Line: verify current market before entry"
    status = _first_context(data, "verification_status", "report_truth_severity") or "VERIFY SOURCE"
    target = _first_context(data, "target_stake_units", "recommended_stake_units", "units") or "0.0"
    live = _first_context(data, "live_verified_stake_units") or "0.0"
    if weather:
        rows.append("Weather: " + _shorten(weather, 112))
    if context:
        rows.append("Context: " + _shorten(context, 122))
    if news and news != context:
        rows.append("News: " + _shorten(news, 108))
    rows.append(f"Verify: {status} · target {target}u · live {live}u.")
    rows.append(_shorten(line, 112))
    return rows[:5]


def install_sale_ready_polish() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as renderer
        _install_renderer_source_labels(renderer)
        _restore_sale_ready_version_suffix(renderer)
    except Exception:
        pass
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
        sale._expanded_context_rows = _readable_matchup_rows
        sale._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION
    except Exception:
        pass


def install() -> None:
    install_live_odds_api_match()
    install_sale_ready_polish()


install()
