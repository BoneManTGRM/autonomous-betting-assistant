from __future__ import annotations

from typing import Any, Iterable
import re

from autonomous_betting_agent.report_public_quality import (
    build_full_market_label,
    is_manual_verified_input,
    is_saved_source,
    public_action_label,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_text,
    trim_complete_sentence,
)

VERSION = "active_magazine_export_guard_v5_saved_context_truth"
WATCH_VERIFY = "WATCHLIST / VERIFY PRICE"
_ERROR_PARTS = (("HTTP", "Error"), ("Trace", "back"), ("Request", "Exception"), ("Connection", "Error"), ("Read", "Timeout"))


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


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


def _first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
            return text
    return default


def _num(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = _first(data, key, default="")
        if not raw:
            continue
        try:
            return float(raw.replace("%", "").replace(",", ""))
        except Exception:
            continue
    return None


def _family(data: dict[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower().replace("_", " ") for k in ("market_type", "market", "market_name", "wager_type", "prediction", "pick", "selection"))
    sport = " ".join(_clean(data.get(k)).lower() for k in ("sport", "league", "event", "matchup"))
    line_text = " ".join(_clean(data.get(k)) for k in ("line", "point", "points", "spread_line", "run_line", "handicap", "line_point"))
    baseball_line = bool(re.search(r"(?<![\d.])([+-]?1(?:\.0)?|[+-]?1\.5)(?![\d.])", line_text + " " + text))
    if any(token in text for token in ("total", "over", "under")):
        return "total"
    if "run line" in text or (any(token in sport for token in ("mlb", "baseball")) and "spread" in text and baseball_line):
        return "run_line"
    if "puck line" in text:
        return "run_line"
    if any(token in text for token in ("spread", "handicap", "point spread")):
        return "spread"
    if any(token in text for token in ("moneyline", "winner", "h2h")):
        return "moneyline"
    return "pick"


def _line(data: dict[str, Any]) -> str:
    raw = _first(data, "total_line", "game_total_line", "spread_line", "run_line", "line_point", "line", "point", "points", "handicap", "threshold", "line_value", "market_line", "line_display", default="")
    if raw:
        try:
            num = float(raw.replace("+", "").replace(",", ""))
            return f"+{num:g}" if num > 0 and _family(data) != "total" else f"{num:g}"
        except Exception:
            return raw
    blob = " | ".join(_clean(data.get(k)) for k in ("prediction", "pick", "display_pick", "exact_bet", "matchup_note", "matchup_notes", "sports_context_summary") if _clean(data.get(k)))
    if _family(data) == "total":
        match = re.search(r"\b(?:over|under|total|set at)\D{0,36}(\d+(?:\.\d+)?)\b", blob, flags=re.I)
        return match.group(1) if match else ""
    match = re.search(r"(?<![A-Za-z0-9])([+-]\d+(?:\.\d+)?)(?![A-Za-z0-9])", blob)
    return match.group(1) if match else ""


def _negative_value(data: dict[str, Any]) -> bool:
    edge = _num(data, "model_market_edge", "edge", "raw_edge", "two_page_raw_edge")
    ev = _num(data, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "raw_EV", "two_page_raw_EV")
    if edge is not None and abs(edge) > 1 and abs(edge) <= 100:
        edge = edge / 100.0
    return edge is not None and ev is not None and (edge <= 0 or ev <= 0)


def _note(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if any((left + right).lower() in text.lower() for left, right in _ERROR_PARTS):
        return ""
    text = re.sub(r"\bWeather:\s*Weather:\s*", "Weather: ", text, flags=re.I)
    text = re.sub(r"\bContext:\s*Context:\s*", "Context: ", text, flags=re.I)
    text = sanitize_public_text(text)
    low = text.rstrip(" .,:;-").lower()
    if any(low.endswith(end) for end in ("where", "with", "with the", "who are", "because", "and", "or", "the", "in", "at", "for", "meaning", "against", "their", "of")):
        text = trim_complete_sentence(text)
    return text


def _clean_lines(items: Iterable[Any], fallback: list[str] | None = None, limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in items:
        text = _note(item)
        low = text.lower()
        if not text or "markets discovered" in low or "provider consensus_average" in low or "endpoint unknown" in low or "status code unknown" in low or "rows returned" in low:
            continue
        if text not in out:
            out.append(text)
    return (out or list(fallback or []))[:limit]


def _no_verified_row(data: dict[str, Any]) -> bool:
    blob = " ".join(_clean(data.get(k)).lower() for k in ("event", "game", "prediction", "pick", "final_decision", "recommendation", "report_verification_reason", "report_verification_class"))
    return "no verified buyer picks" in blob


def _source_placeholder(value: str) -> bool:
    text = _clean(value).lower()
    return any(token in text for token in ("uploaded", "cached", "saved", "handoff", "fallback", "manual"))


def _price(data: dict[str, Any]) -> str:
    return _first(data, "current_verified_price", "decimal_price", "decimal_odds", "best_price", "odds_at_pick", "american_odds", "odds_american", "odds", default="")


def _price_source(data: dict[str, Any]) -> str:
    source = _first(data, "odds_source", "price_source", "data_source", "provider", "api_source", "bookmaker", "sportsbook", "book", default="")
    return "" if _source_placeholder(source) else source


def _timestamp(data: dict[str, Any]) -> str:
    return _first(data, "odds_timestamp", "price_timestamp", "odds_updated_at", "line_timestamp", "locked_at_utc", "commence_time", "event_start_utc", default="")


def _price_line(data: dict[str, Any]) -> str:
    price = _first(data, "saved_display_price", default="") or _price(data)
    source = _first(data, "saved_price_source", default="") or _price_source(data)
    if price and source:
        return f"{price} from {source}"
    return price or source or "Stored price not found"


def _demonstration_mode(data: dict[str, Any]) -> bool:
    if data.get("demonstration_mode") is True:
        return True
    text = " ".join(
        _clean(data.get(key)).lower()
        for key in ("report_title", "report_data_scope", "report_truth_warning", "league")
    )
    return any(token in text for token in ("demonstration", "demo only", "validation fixture"))


def normalize_row(value: Any) -> dict[str, Any]:
    data = _row(value)
    for key in ("weather_summary", "venue_weather", "weather_risk", "weather_location", "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes", "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "sportsdataio_context", "api_football_summary", "line_movement_summary", "line_movement", "price_movement"):
        if key in data:
            cleaned = _note(data.get(key))
            if cleaned:
                data[key] = cleaned
    if _no_verified_row(data):
        data.update({
            "away_team": "No Verified Picks",
            "home_team": "Current Provider Check",
            "sport": "Report Verification",
            "league": "ABA Signal Pro",
            "market_type": "research only",
            "final_decision": "NO VERIFIED BUYER PICKS",
            "agent_decision": "NO VERIFIED BUYER PICKS",
            "recommendation": "NO VERIFIED BUYER PICKS",
            "consumer_action": "NO VERIFIED BUYER PICKS",
            "recommended_action": "NO VERIFIED BUYER PICKS",
            "risk": "RESEARCH ONLY",
            "risk_level": "RESEARCH ONLY",
            "risk_label": "RESEARCH ONLY",
            "profit_guard_status": "RESEARCH ONLY",
            "report_source": "no_verified_provider_gate",
            "report_source_label": "No verified current-provider picks",
            "report_data_scope": "No verified buyer picks",
            "report_truth_severity": "RESEARCH ONLY",
            "api_match_status": "Provider not matched",
            "provider_match_status": "Provider not matched",
            "odds_status": "NO_VERIFIED_BUYER_PICKS",
            "odds_verified": "false",
        })
        return data
    line = _line(data)
    fam = _family(data)
    if fam == "total":
        data["market_type"] = data["market"] = "game total"
    elif fam == "run_line":
        data["market_type"] = data["market"] = "run line"
    elif fam == "spread":
        data["market_type"] = data["market"] = "spread"
    if line:
        data["line"] = line
        data["point"] = line.lstrip("+")
        if fam == "total":
            data["total_line"] = line
        elif fam == "run_line":
            data["run_line"] = line
        elif fam == "spread":
            data["spread_line"] = line
    label = build_full_market_label(data)
    label = re.sub(r"\bSpread:\s*Point Spread:\s*", "Spread: ", label, flags=re.I)
    label = re.sub(r"\bRun Line:\s*Point Spread:\s*", "Run Line: ", label, flags=re.I)
    label = re.sub(r"\bSpread:\s*Spread:\s*", "Spread: ", label, flags=re.I)
    for key in ("aba_display_pick", "display_pick", "prediction", "pick", "exact_bet", "final_recommendation_label", "public_market_label", "verified_market_label", "full_market_label", "market_label", "trend_label"):
        data[key] = label
    negative = _negative_value(data)
    manual_verified = is_manual_verified_input(data)
    saved = is_saved_source(data)
    demo = _demonstration_mode(data)
    action = "DEMONSTRATION ONLY" if demo else ("NO " + "BET / PRICE REJECTED" if negative else (WATCH_VERIFY if saved else public_action_label(data)))
    for key in ("final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action"):
        data[key] = action
    data["risk"] = "DEMONSTRATION DATA" if demo else ("PRICE REJECTED" if negative else ("VERIFY CURRENT PRICE" if saved else "MANUALLY VERIFIED PRICE" if manual_verified else "VERIFIED PRICE"))
    data["risk_level"] = data["risk_label"] = data["profit_guard_status"] = data["risk"]
    data["final_explanation"] = "Demonstration only - not current betting advice." if demo else ("Negative edge or EV at current price." if negative else ("Saved row uses stored price/context. Recheck current provider price before publishing." if saved else public_recommendation_status(data)))
    data["action_reason"] = data["recommendation_reason"] = data["final_explanation"]
    if demo:
        data["report_source"] = "demonstration_fixture"
        data["report_source_label"] = _first(data, "report_source_label", default="Demonstration fixture")
        data["report_data_scope"] = _first(data, "report_data_scope", default="Demonstration only - not current betting advice")
        data["report_truth_severity"] = "DEMONSTRATION ONLY"
        data["verification_status"] = "DEMONSTRATION ONLY"
        data["odds_api_live"] = "false"
        data["the_odds_api_live"] = "false"
    elif saved:
        price = _price(data)
        source = _price_source(data)
        timestamp = _timestamp(data)
        if price:
            data["saved_display_price"] = price
        if source:
            data["saved_price_source"] = source
        if timestamp:
            data["saved_price_timestamp"] = timestamp
        data["report_source"] = "saved_context_row"
        data["report_source_label"] = "Saved row + provider context"
        data["report_data_scope"] = "Saved handoff with stored provider/context fields"
        data["report_truth_severity"] = "VERIFY CURRENT PRICE"
        data["verification_status"] = "Saved price only - current provider recheck required"
        data["api_match_status"] = "Current provider recheck required"
        data["provider_match_status"] = "Current provider recheck required"
        data["odds_api_status"] = _first(data, "odds_status", default="SAVED_PRICE_VERIFY_CURRENT")
        data["odds_verified"] = "false"
        data["odds_api_live"] = "false"
        data["the_odds_api_live"] = "false"
        data["report_truth_warning"] = public_source_warning(data)
    elif manual_verified:
        data["report_source"] = "manual_verified_input"
        data["report_source_label"] = "Operator-attested manual price"
        data["report_data_scope"] = "Manual sportsbook observation"
        data["report_truth_severity"] = "MANUALLY VERIFIED INPUT"
        data["verification_status"] = "Manual price observation - not an automated live API quote"
        data["api_match_status"] = "Manual input verified"
        data["provider_match_status"] = "Manual input verified"
        data["odds_verified"] = "manual"
        data["odds_api_live"] = "false"
        data["the_odds_api_live"] = "false"
    return data


def public_truth_pairs(row: Any, lang: str = "en") -> list[tuple[str, str]]:
    data = normalize_row(row)
    if _no_verified_row(data):
        return [("REPORT SOURCE", "No verified current-provider picks"), ("DATA SCOPE", "No verified buyer picks"), ("TRUTH", "RESEARCH ONLY"), ("ODDS STATUS", "NO_VERIFIED_BUYER_PICKS"), ("MATCHED", "Provider not matched")]
    odds_status = _clean(data.get("odds_status") or data.get("odds_source") or "VERIFY").upper()
    if _demonstration_mode(data):
        return [
            ("REPORT SOURCE", _first(data, "report_source_label", default="Demonstration fixture")),
            ("DATA SCOPE", _first(data, "report_data_scope", default="Demonstration only - not current betting advice")),
            ("TRUTH", "DEMONSTRATION ONLY"),
            ("ODDS STATUS", "DEMO PRICE - NOT LIVE API"),
            ("LIVE API", "Not used for this validation fixture"),
        ]
    if is_saved_source(data):
        pairs = [("REPORT SOURCE", "Saved row + provider context"), ("PRICE STATUS", "Verify current price"), ("SAVED PRICE", _price_line(data))]
        timestamp = _first(data, "saved_price_timestamp", default="") or _timestamp(data)
        if timestamp:
            pairs.append(("TIMESTAMP", timestamp))
        pairs.append(("MATCHED", "Current provider recheck required"))
        return pairs[:5]
    if is_manual_verified_input(data):
        return [
            ("REPORT SOURCE", "Operator-attested manual input"),
            ("PRICE STATUS", "Manually verified"),
            ("BOOK / PRICE", _price_line(data)),
            ("TIMESTAMP", _timestamp(data) or "Missing"),
            ("LIVE API", "Not used for this price"),
        ]
    return [("REPORT SOURCE", "Current provider row"), ("DATA SCOPE", "Current provider matched"), ("TRUTH", "VERIFIED PRICE"), ("ODDS STATUS", odds_status), ("MATCHED", "Provider matched")]


def _draw_overlay(module: Any, image: Any, row: dict[str, Any], language: str | None = None) -> Any:
    return image


def _clean_saved_page2_row(text: str) -> str:
    text = _clean(text)
    text = text.replace("Provider match required before verified status", "Current provider recheck required before verified status")
    text = text.replace("Provider match required", "Current provider recheck required")
    text = text.replace("Fresh timestamp required", "Fresh provider timestamp required")
    text = text.replace("Exact market line required", "Exact provider market line required")
    text = re.sub(r"Provider:\s*saved-source", "Current provider match: Recheck required", text, flags=re.I)
    text = re.sub(r"Timestamp:\s*\d{4}-\d{2}-\d{2}T[^\s]+", "Timestamp: saved row timestamp", text)
    return text


def _source_diagnostics(data: dict[str, Any]) -> list[str]:
    rows = ["Source type: Saved row with provider/context fields", "Current provider match: Recheck required"]
    price = _price_line(data)
    if price and price != "Stored price not found":
        rows.append("Stored price: " + price)
    timestamp = _first(data, "saved_price_timestamp", default="") or _timestamp(data)
    if timestamp:
        rows.append("Timestamp: " + timestamp)
    rows.append("Verification status: Saved price only")
    return rows[:5]


def install(module: Any) -> Any:
    current_page = getattr(module, "render_full_pick_magazine_page", None)
    if getattr(current_page, "_ABA_ACTIVE_EXPORT_GUARD_WRAPPER", "") == VERSION:
        return module
    original_page = module.render_full_pick_magazine_page
    original_pages = module.render_full_magazine_book_pages
    original_pairs = getattr(module, "_pairs", None)
    original_api_lines = getattr(module, "api_provenance_lines", None)
    original_matchup_items = getattr(module, "_matchup_items", None)

    def guarded_page(pick: Any, *args: Any, **kwargs: Any):
        row = normalize_row(pick)
        image = original_page(row, *args, **kwargs)
        language = kwargs.get("language") if kwargs else None
        if len(args) >= 11 and language is None:
            language = args[10]
        return _draw_overlay(module, image, row, language)
    guarded_page._ABA_ACTIVE_EXPORT_GUARD_WRAPPER = VERSION  # type: ignore[attr-defined]

    def guarded_pages(picks: Iterable[Any], *args: Any, **kwargs: Any):
        return original_pages([normalize_row(row) for row in list(picks)], *args, **kwargs)

    def guarded_api_lines(row: Any) -> list[str]:
        data = normalize_row(row)
        try:
            configured = " · ".join(module.configured_api_sources())
        except Exception:
            configured = ""
        if _no_verified_row(data):
            return ["Matched to this row: Provider not matched"]
        lines = ["Configured APIs: " + configured] if configured else []
        matched = "Current provider recheck required" if is_saved_source(data) else "Manual input verified" if is_manual_verified_input(data) else "Provider matched"
        lines.append("Matched to this row: " + matched)
        return lines

    def guarded_pairs(row: Any, lang: str):
        data = normalize_row(row)
        if _no_verified_row(data) or is_saved_source(data) or is_manual_verified_input(data):
            return public_truth_pairs(data, lang)
        pairs = [] if not callable(original_pairs) else list(original_pairs(data, lang))
        return [("CONFIGURED APIS" if str(label).upper() == "ACTIVE APIS" else label, value) for label, value in pairs][:5]

    def guarded_matchup(row: Any):
        data = normalize_row(row)
        rows = [] if not callable(original_matchup_items) else list(original_matchup_items(data))
        return _clean_lines(rows, ["Context was not returned for this event."], 3)

    module.render_full_pick_magazine_page = guarded_page
    module.render_full_magazine_book_pages = guarded_pages
    module.api_provenance_lines = guarded_api_lines if callable(original_api_lines) else guarded_api_lines
    module._active_note = lambda row: guarded_api_lines(row)[-1] + "."
    module._pairs = guarded_pairs
    module._matchup_items = guarded_matchup
    try:
        from autonomous_betting_agent import magazine_second_page_patch as page2
        original_discover = getattr(page2, "discover_markets", None)
        if callable(original_discover) and not getattr(original_discover, "_ABA_ACTIVE_EXPORT_DISCOVER", False):
            def guarded_discover(pick: Any):
                row = normalize_row(pick)
                markets, diag = original_discover(row)
                for market in markets:
                    if getattr(market, "edge", None) is not None and getattr(market, "ev", None) is not None and (market.edge <= 0 or market.ev <= 0):
                        market.badge = "NO " + "BET / PRICE REJECTED"
                        market.rejection_reason = "Requires positive edge and EV"
                    elif str(getattr(market, "badge", "")).upper() == "WATCHLIST":
                        market.badge = WATCH_VERIFY
                    if is_saved_source(row) and str(getattr(market, "rejection_reason", "")).strip():
                        market.rejection_reason = "Saved price only - current provider recheck required"
                if is_saved_source(row):
                    diag["provider_state"] = "Saved price only"
                    diag["provider_called"] = _price_source(row) or "saved-row"
                return markets, diag
            guarded_discover._ABA_ACTIVE_EXPORT_DISCOVER = True  # type: ignore[attr-defined]
            page2.discover_markets = guarded_discover
        original_sections = getattr(page2, "_page_two_sections", None)
        if callable(original_sections) and not getattr(original_sections, "_ABA_ACTIVE_EXPORT_SECTIONS", False):
            def guarded_sections(
                data: dict[str, Any],
                lang: str,
                *,
                parlays=None,
                diagnostics=None,
            ):
                row = normalize_row(data)
                sections = original_sections(
                    row,
                    lang,
                    parlays=parlays,
                    diagnostics=diagnostics,
                )
                if not is_saved_source(row):
                    return sections
                cleaned = []
                for title, rows, color in sections:
                    if title == "Source Diagnostics":
                        rows = _source_diagnostics(row)
                    else:
                        rows = [_clean_saved_page2_row(item) for item in rows]
                    cleaned.append((title, rows, color))
                return cleaned
            guarded_sections._ABA_ACTIVE_EXPORT_SECTIONS = True  # type: ignore[attr-defined]
            page2._page_two_sections = guarded_sections
    except Exception:
        pass
    module._ABA_ACTIVE_EXPORT_GUARD = VERSION
    return module
