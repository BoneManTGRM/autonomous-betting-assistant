from __future__ import annotations

from typing import Any, Iterable
import re

from autonomous_betting_agent.report_public_quality import (
    build_full_market_label,
    is_saved_source,
    public_action_label,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_text,
    trim_complete_sentence,
)

VERSION = "active_magazine_export_guard_v4"
NO_PLAY = "NO " + "BET / PRICE REJECTED"
WATCH_VERIFY = "WATCHLIST / VERIFY PRICE"
_DANGLING = ("where", "with", "with the", "who are", "because", "and", "or", "the", "in", "at", "for", "meaning", "against", "their", "of")
_NOTE_KEYS = ("weather_summary", "venue_weather", "weather_risk", "weather_location", "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes", "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "sportsdataio_context", "api_football_summary", "line_movement_summary", "line_movement", "price_movement")


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


def _sport_text(data: dict[str, Any]) -> str:
    return " ".join(_clean(data.get(k)).lower() for k in ("sport", "sport_key", "league", "competition", "event_type", "market", "market_type", "prediction", "pick", "selection"))


def _family(data: dict[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower().replace("_", " ") for k in ("market_type", "market", "market_name", "wager_type", "prediction", "pick", "selection"))
    sport = _sport_text(data)
    line_text = " ".join(_clean(data.get(k)) for k in ("line", "point", "points", "spread_line", "run_line", "handicap", "line_point"))
    baseball_line = bool(re.search(r"(?<![\d.])[+-]?1(?:\.0)?|[+-]?1\.5(?![\d.])", line_text + " " + text))
    if any(token in text for token in ("total", "over", "under")):
        return "total"
    if "run line" in text or (any(token in sport for token in ("mlb", "baseball")) and any(token in text for token in ("spread", "point spread", "handicap")) and baseball_line):
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


def _note(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"\bWeather:\s*Weather:\s*", "Weather: ", text, flags=re.I)
    text = re.sub(r"\bContext:\s*Context:\s*", "Context: ", text, flags=re.I)
    text = sanitize_public_text(text)
    lowered = text.rstrip(" .,:;-").lower()
    if any(lowered.endswith(end) for end in _DANGLING):
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


def _negative_value(data: dict[str, Any]) -> bool:
    edge = _num(data, "model_market_edge", "edge", "raw_edge", "two_page_raw_edge")
    ev = _num(data, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "raw_EV", "two_page_raw_EV")
    if edge is not None and abs(edge) > 1 and abs(edge) <= 100:
        edge = edge / 100.0
    return edge is not None and ev is not None and (edge <= 0 or ev <= 0)


def normalize_row(value: Any) -> dict[str, Any]:
    data = _row(value)
    for key in _NOTE_KEYS:
        if key in data:
            cleaned = _note(data.get(key))
            if cleaned:
                data[key] = cleaned
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
    saved = is_saved_source(data)
    if negative:
        action = NO_PLAY
    elif saved:
        action = WATCH_VERIFY
    else:
        action = public_action_label(data)
    for key in ("final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action"):
        data[key] = action
    data["risk"] = "PRICE REJECTED" if negative else ("VERIFY PRICE" if saved else "VERIFIED PRICE")
    data["risk_level"] = data["risk_label"] = data["profit_guard_status"] = data["risk"]
    data["final_explanation"] = "Negative edge or EV at current price." if negative else ("Saved-source row. Verify current provider price before publishing." if saved else public_recommendation_status(data))
    data["action_reason"] = data["recommendation_reason"] = data["final_explanation"]
    if saved:
        data["report_source"] = "uploaded_saved_row"
        data["report_source_label"] = "Uploaded / saved row"
        data["report_data_scope"] = "Saved-source verification report"
        data["report_truth_severity"] = "VERIFY PRICE"
        data["verification_status"] = "Source saved"
        data["api_match_status"] = "Provider not matched"
        data["provider_match_status"] = "Provider not matched"
        data["odds_api_status"] = "SAVED_SOURCE"
        data["odds_verified"] = "false"
        data["odds_api_live"] = "false"
        data["the_odds_api_live"] = "false"
        data["report_truth_warning"] = public_source_warning(data)
    return data


def public_truth_pairs(row: Any, lang: str = "en") -> list[tuple[str, str]]:
    data = normalize_row(row)
    odds_status = _clean(data.get("odds_status") or data.get("odds_source") or "VERIFY").upper()
    if is_saved_source(data):
        return [("REPORT SOURCE", "Uploaded / saved row"), ("DATA SCOPE", "Saved-source verification report"), ("TRUTH", "VERIFY PRICE"), ("ODDS STATUS", odds_status), ("MATCHED", "Saved source only")]
    return [("REPORT SOURCE", "Current provider row"), ("DATA SCOPE", "Current provider matched"), ("TRUTH", "VERIFIED PRICE"), ("ODDS STATUS", odds_status), ("MATCHED", "Provider matched")]


def _draw_overlay(module: Any, image: Any, row: dict[str, Any], language: str | None = None) -> Any:
    try:
        from PIL import ImageDraw
    except Exception:
        return image
    try:
        img = image.convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")
        black = getattr(module, "BLACK", (13, 14, 16))
        cream = getattr(module, "CREAM", (255, 248, 230))
        red = getattr(module, "RED", (190, 30, 28))
        blue = getattr(module, "BLUE", (19, 66, 108))
        green = getattr(module, "GREEN", (61, 205, 84))
        gold = (241, 184, 45)
        paper = getattr(module, "PAPER", (244, 235, 211))
        lang = module._lang(row, language) if callable(getattr(module, "_lang", None)) else "en"
        action = _clean(row.get("final_decision") or WATCH_VERIFY).upper()
        pick = _clean(row.get("prediction") or row.get("pick") or "").upper()
        draw.rectangle((24, 462, 344, 558), fill=black + (255,))
        draw.text((50, 472), module._tr("TREND", lang), font=module._fit(module._tr("TREND", lang), 190, 25, 14, True), fill=red)
        module._txt_auto(draw, 50, 508, module._tr(pick, lang), 210, 38, 26, 8, cream, True, 1)
        draw.rectangle((270, 1378, 1064, 1524), fill=black + (255,))
        color = red if "REJECTED" in action or "NO " in action else (green if "VERIFIED" in action else gold)
        draw.text((284, 1392), module._tr(action, lang), font=module._fit(module._tr(action, lang), 680, 60, 18, True), fill=color)
        module._txt_auto(draw, 286, 1462, module._tr(pick, lang), 750, 44, 38, 10, cream, True, 1)
        draw.rounded_rectangle((350, 1174, 1064, 1358), radius=16, fill=paper + (255,), outline=paper + (255,), width=4)
        module._section(draw, 354, 1178, 706, 175, "MATCHUP NOTES", blue, lang)
        y = 1246
        font = module._font(18)
        for text in _clean_lines([row.get("weather_summary"), row.get("matchup_notes"), row.get("sports_context_summary"), row.get("news_summary")], ["Context was not returned for this event."], 3):
            if y > 1334:
                break
            draw.ellipse((378, y + 7, 390, y + 19), fill=blue)
            for line in module._wrap_text_to_box(draw, module._tr(text, lang), font, 650, 2)[:2]:
                draw.text((403, y), module._ellipsize_to_width(draw, line, font, 630), font=font, fill=(14, 17, 21))
                y += 22
            y += 6
        return img.convert("RGB")
    except Exception:
        return image


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
        lines = ["Configured APIs: " + configured] if configured else []
        lines.append("Matched to this row: " + ("Saved source only" if is_saved_source(data) else "Provider matched"))
        return lines

    def guarded_pairs(row: Any, lang: str):
        data = normalize_row(row)
        if is_saved_source(data):
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
        original_draw = page2._draw_second_page
        original_discover = getattr(page2, "discover_markets", None)
        if callable(original_discover) and not getattr(original_discover, "_ABA_ACTIVE_EXPORT_DISCOVER", False):
            def guarded_discover(pick: Any):
                row = normalize_row(pick)
                markets, diag = original_discover(row)
                for market in markets:
                    if getattr(market, "edge", None) is not None and getattr(market, "ev", None) is not None and (market.edge <= 0 or market.ev <= 0):
                        market.badge = NO_PLAY
                        market.rejection_reason = "Requires positive edge and EV"
                    elif str(getattr(market, "badge", "")).upper() == "WATCHLIST":
                        market.badge = WATCH_VERIFY
                    if is_saved_source(row) and str(getattr(market, "rejection_reason", "")).strip():
                        market.rejection_reason = "Saved-source only - current provider match required"
                if is_saved_source(row):
                    diag["provider_state"] = "Source saved"
                    diag["provider_called"] = "saved-source"
                return markets, diag
            guarded_discover._ABA_ACTIVE_EXPORT_DISCOVER = True  # type: ignore[attr-defined]
            page2.discover_markets = guarded_discover
        def guarded_second_page(patched: Any, pick: Any, *args: Any, **kwargs: Any):
            return original_draw(patched, normalize_row(pick), *args, **kwargs)
        page2._draw_second_page = guarded_second_page
    except Exception:
        pass
    module._ABA_ACTIVE_EXPORT_GUARD = VERSION
    return module
