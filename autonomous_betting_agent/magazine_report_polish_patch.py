from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import quote_plus, urlencode

_PATCH_VERSION = "magazine_report_display_polish_v6_truth_guard_labels"

SOURCE_LABELS = {
    "Odds API": "Odds",
    "The Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}

UNVERIFIED_SOURCE_TOKENS = (
    "uploaded",
    "uploaded_row",
    "saved-handoff",
    "saved handoff",
    "handoff",
    "fallback",
    "cached",
    "ledger-history",
    "ledger history",
    "history only",
    "missing",
)

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


def _unverified_source_marker(row: Any) -> bool:
    data = _row(row)
    blob = " ".join(
        _clean(data.get(key)).lower().replace("_", "-")
        for key in (
            "report_source_mode",
            "source_mode",
            "report_source",
            "report_source_note",
            "report_source_label",
            "report_data_scope",
            "odds_status",
            "odds_api_status",
            "odds_source",
            "data_source",
            "verification_status",
            "report_truth_severity",
            "risk",
            "risk_level",
            "risk_label",
        )
    )
    return any(token in blob for token in UNVERIFIED_SOURCE_TOKENS)


def _live_odds_marker(row: Any) -> bool:
    if _unverified_source_marker(row):
        return False
    data = _row(row)
    status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    flags = {_clean(data.get(key)).lower() for key in ("odds_api_live", "the_odds_api_live", "odds_verified")}
    live_status = status in {"live", "live_api", "live_match", "odds_api_live_match"}
    live_source = source in {"live", "live_api", "the odds api", "odds api"}
    live_flag = bool(flags & {"1", "true", "yes", "verified", "live"})
    return live_status or live_source or live_flag


def _fallback_row(row: Any) -> bool:
    if _unverified_source_marker(row):
        return True
    data = _row(row)
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
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
    if "basketball" in text or "nba" in text or "wnba" in text:
        explicit.extend(["basketball_nba", "basketball_wnba"])
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
    if "spread" in text or "handicap" in text or "run line" in text:
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
    data["odds_verified"] = "true"
    data["report_source_mode"] = "current-run"
    data["report_truth_severity"] = "LIVE VERIFIED"
    data["verification_status"] = "LIVE VERIFIED"
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
                return ["Enabled APIs: " + " · ".join(checked[:6]) + "; no verified live match for this row."]
            return ["Enabled APIs: checked; no verified live match for this row."]
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


def _strict_live_verified(data: dict[str, Any]) -> bool:
    return _live_odds_marker(data)


def _strict_fallback_odds(data: dict[str, Any]) -> bool:
    return _fallback_row(data)


def _guarded_risk_items(row: Any) -> list[str]:
    if _fallback_row(row):
        return [
            "Saved row / price verification required.",
            "Confirm current sportsbook price before entry.",
            "Watchlist only until a live source match is confirmed.",
        ]
    return ["Recheck current price before entry.", "Cancel if line or news changes."]


def _guarded_team_items(row: Any, side: str = "") -> list[str]:
    if _fallback_row(row):
        return ["No live team snapshot returned.", "Team feed not matched to this row.", "Verify team/news context before entry."]
    return ["Live team snapshot requires source match.", "Verify current team/news context before entry."]


def _guarded_injury_items(row: Any, prefix: str = "") -> list[str]:
    if _fallback_row(row):
        return ["No verified lineup/injury update returned.", "Lineup/injury feed not verified for this row."]
    return ["Verify lineup/injury news before entry."]


def _guarded_truth_pairs(row: Any, lang: str = "en") -> list[tuple[str, str]]:
    data = _row(row)
    source_mode = _clean(data.get("report_source_mode") or data.get("source_mode") or data.get("report_source")).lower()
    odds_status = _clean(data.get("odds_status") or data.get("odds_source") or data.get("data_source") or "MISSING").upper()
    context_status = _clean(data.get("context_status") or data.get("context_source") or data.get("report_live_context_detected") or "VERIFY")
    if _fallback_row(data):
        if "uploaded" in odds_status.lower() or "uploaded" in source_mode:
            source_label = "Uploaded / saved row"
        elif "ledger" in source_mode or "history" in source_mode:
            source_label = "Proof ledger history"
        else:
            source_label = "Saved handoff rows"
        pairs = [
            ("REPORT SOURCE", source_label),
            ("DATA SCOPE", "Price verification required"),
            ("TRUTH", "VERIFY PRICE"),
            ("ODDS STATUS", odds_status),
            ("CONTEXT STATUS", context_status),
        ]
    elif _live_odds_marker(data):
        pairs = [
            ("REPORT SOURCE", "Live API refreshed report"),
            ("DATA SCOPE", "Current API-refreshed slate"),
            ("TRUTH", "LIVE VERIFIED"),
            ("ODDS STATUS", odds_status or "LIVE"),
            ("CONTEXT STATUS", context_status),
        ]
    else:
        pairs = [
            ("REPORT SOURCE", _clean(data.get("report_source_label") or data.get("report_source_mode") or "Report source unknown")),
            ("DATA SCOPE", _clean(data.get("report_data_scope") or "Current/fallback status unknown")),
            ("TRUTH", "VERIFY"),
            ("ODDS STATUS", odds_status),
            ("CONTEXT STATUS", context_status),
        ]
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch_contract as contract
        return [(contract._es(label, lang), contract._es(value, lang)) for label, value in pairs]
    except Exception:
        return pairs


def _guard_row_truth(data: dict[str, Any]) -> dict[str, Any]:
    if not _fallback_row(data):
        return data
    data["verification_status"] = "VERIFY PRICE"
    data["report_truth_severity"] = "VERIFY PRICE"
    data["report_truth_warning"] = "Saved/uploaded row requires live price verification."
    data["final_decision"] = "WATCHLIST"
    data["agent_decision"] = "WATCHLIST"
    data["recommendation"] = "WATCHLIST"
    data["risk"] = "VERIFY PRICE"
    data["risk_level"] = "VERIFY PRICE"
    data["risk_label"] = "VERIFY PRICE"
    data["live_verified_stake_units"] = "0.0"
    data["why_lose"] = "\n".join(_guarded_risk_items(data))
    data["chain_notes"] = "\n".join([
        "No verified parlay: source is saved/uploaded.",
        "Need exact event, market, line, selection, price, and timestamp.",
        "Add a second verified positive-EV leg before building a chain.",
    ])
    return data


def _install_sale_truth_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
    except Exception:
        return
    sale._live_verified = _strict_live_verified
    sale._fallback_odds = _strict_fallback_odds
    sale._truth_pairs = _guarded_truth_pairs
    original_force = getattr(sale, "_force_truthful_gate", None)
    if callable(original_force) and not getattr(original_force, "_ABA_STRICT_TRUTH_GUARD", False):
        def force_with_truth_guard(row: Any):
            data = original_force(row)
            return _guard_row_truth(data)
        force_with_truth_guard._ABA_STRICT_TRUTH_GUARD = True  # type: ignore[attr-defined]
        sale._force_truthful_gate = force_with_truth_guard
    sale.sale_ready_risk_items = _guarded_risk_items


def _install_renderer_truth_guard(renderer: Any) -> None:
    renderer._pairs = _guarded_truth_pairs
    renderer._risk_items = _guarded_risk_items
    renderer.risk_items = _guarded_risk_items
    renderer._team_items = _guarded_team_items
    renderer.team_items = _guarded_team_items
    renderer._injury_items = _guarded_injury_items
    renderer.injury_items = _guarded_injury_items
    renderer._ABA_TRUTH_GUARD_VERSION = _PATCH_VERSION


def _install_second_page_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_second_page_patch as second
    except Exception:
        return
    original_sections = getattr(second, "_page_two_sections", None)
    if not callable(original_sections) or getattr(original_sections, "_ABA_PAGE_TWO_REASON_GUARD", False):
        return

    def guarded_page_two_sections(data: dict[str, Any], lang: str):
        sections = list(original_sections(data, lang))
        if not _fallback_row(data):
            return sections
        try:
            _markets, diag = second.discover_markets(data)
        except Exception:
            diag = {"markets_discovered": 0, "markets_rejected": 0, "timestamp": "missing", "provider_called": "unknown", "cached_handoff_live_status": "saved-handoff"}
        reasons = [
            "BLOCKED · no verified parlay: source is saved/uploaded, not live matched.",
            f"Reason · markets discovered {diag.get('markets_discovered', 0)}; rejected {diag.get('markets_rejected', 0)}.",
            f"Reason · provider {diag.get('provider_called', 'unknown')} · timestamp {diag.get('timestamp', 'missing')}.",
            "Need exact event, market, line, selection, sportsbook, price, and timestamp.",
            "Wait for a second verified positive-EV leg before making a parlay.",
        ]
        quality = [
            f"Gate failed · source mode {diag.get('cached_handoff_live_status', 'saved-handoff')}.",
            "Gate failed · saved/uploaded rows cannot become VERIFIED.",
            "Gate required · live provider match + positive EV + fresh timestamp.",
            "Gate required · Reparodynamics must not block the market.",
        ]
        rewritten = []
        for title, items, color in sections:
            if title == "Parlay Builder":
                rewritten.append((title, [second._tr(x, lang) for x in reasons], color))
            elif title == "Quality Gate":
                rewritten.append((title, [second._tr(x, lang) for x in quality], color))
            else:
                rewritten.append((title, items, color))
        return rewritten

    guarded_page_two_sections._ABA_PAGE_TWO_REASON_GUARD = True  # type: ignore[attr-defined]
    second._page_two_sections = guarded_page_two_sections


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
        _guard_row_truth(row)

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
        _install_renderer_truth_guard(renderer)
        _restore_sale_ready_version_suffix(renderer)
    except Exception:
        pass
    _install_sale_truth_guard()
    _install_second_page_guard()
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
