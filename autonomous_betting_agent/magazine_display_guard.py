from __future__ import annotations

import re
from typing import Any

PATCH_VERSION = "magazine_display_guard_v2_decimal_odds_richer_context"
GOLD = (241, 184, 45)


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


def _provider_confirmed(row: Any) -> bool:
    data = _row(row)
    status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    return status in {"live", "live_match", "live_api", "odds_api_live_match"} or source in {"the odds api", "odds api"}


def _needs_verification(row: Any) -> bool:
    if _provider_confirmed(row):
        return False
    data = _row(row)
    joined = " ".join(_clean(data.get(key)).lower() for key in ("odds_source", "data_source", "odds_status", "odds_api_status", "risk", "risk_label", "profit_guard_status"))
    return any(token in joined for token in ("uploaded", "fallback", "cached", "missing", "no live"))


def _generic(text: str) -> bool:
    low = _clean(text).lower()
    return not low or any(token in low for token in ("not returned", "data unavailable", "fallback report"))


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item)
        if text and not text.endswith("."):
            text += "."
        key = text.lower().rstrip(".")
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _trim(text: str, length: int = 88) -> str:
    text = _clean(text)
    if len(text) <= length:
        return text
    return (text[: length - 1].rsplit(" ", 1)[0] or text[: length - 1]).rstrip(".,;:") + "…"


def _short_context(data: dict[str, Any], limit: int = 3) -> list[str]:
    items: list[str] = []
    for key in (
        "weather_summary",
        "venue_note",
        "weather_location",
        "api_football_summary",
        "api_football_context",
        "newsapi_summary",
        "news_summary",
        "perplexity_summary",
        "perplexity_context",
        "sports_context_summary",
        "matchup_note",
    ):
        for item in _split(data.get(key)):
            if _generic(item):
                continue
            items.append(_trim(item, 78))
            if len(items) >= limit:
                return _dedupe(items)
    return []


def _prepared_row(row: Any) -> dict[str, Any]:
    data = _row(row)
    if _needs_verification(data):
        action = _clean(data.get("final_decision") or data.get("agent_decision") or data.get("recommendation") or data.get("consumer_action") or data.get("recommended_action")).upper()
        if "PLAY" in action and "NO PLAY" not in action:
            data["final_decision"] = "WATCHLIST"
            data["agent_decision"] = "WATCHLIST"
            data["recommended_action"] = "WATCHLIST"
            data["consumer_action"] = "WATCHLIST"
        data.setdefault("final_explanation", "Watchlist only until the current provider match is verified.")
        data.setdefault("action_reason", "Watchlist only until the current provider match is verified.")
        data["risk"] = data.get("risk") or "VERIFY CURRENT PRICE"
        data["risk_label"] = data.get("risk_label") or data["risk"]
    return data


def _state(row: Any) -> tuple[str, tuple[int, int, int], tuple[int, int, int], str]:
    data = _prepared_row(row)
    action = _clean(data.get("final_decision") or data.get("agent_decision") or data.get("recommendation") or data.get("consumer_action") or data.get("recommended_action") or "WATCHLIST").upper()
    note = _clean(data.get("final_explanation") or data.get("action_reason") or data.get("recommendation_reason"))
    if _needs_verification(data) or "WATCH" in action:
        return "WATCHLIST", GOLD, GOLD, note or "Watchlist only until the current provider match is verified."
    if "NO" in action and "PLAY" in action:
        return "NO PLAY", (225, 67, 62), (225, 67, 62), note or "Do not use at the current price."
    if "SMALL" in action:
        return "PLAY SMALL", GOLD, GOLD, note
    return "PLAY", (61, 205, 84), (61, 205, 84), note


def _decimal_odds_text(value: Any) -> str | None:
    raw = _clean(value).replace(",", "")
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        decimal = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        decimal = 1.0 + num / 100.0
    elif num > 1:
        decimal = num
    else:
        return None
    return f"{decimal:.2f}".rstrip("0").rstrip(".")


def _install_metric_overrides(module: Any) -> None:
    original_fmt = getattr(module, "_fmt", None)
    if callable(original_fmt) and not getattr(original_fmt, "_ABA_DECIMAL_ODDS_GUARD", False):
        def fmt_decimal_first(value: Any, kind: str = "") -> str:
            if kind == "odds":
                decimal = _decimal_odds_text(value)
                if decimal:
                    return decimal
            return original_fmt(value, kind)

        fmt_decimal_first._ABA_DECIMAL_ODDS_GUARD = True
        module._fmt = fmt_decimal_first

    original_cells = getattr(module, "magazine_metric_cells", None)
    if callable(original_cells) and not getattr(original_cells, "_ABA_RISK_COLOR_GUARD", False):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            cells = list(original_cells(odds, conf, edge, ev, units, risk))
            risk_text = _clean(risk).lower()
            if any(token in risk_text for token in ("fallback", "verify", "watch", "volume")):
                cells[-1] = (cells[-1][0], cells[-1][1], GOLD, cells[-1][3], cells[-1][4])
            return cells

        metric_cells._ABA_RISK_COLOR_GUARD = True
        module.magazine_metric_cells = metric_cells


def _install_item_overrides(module: Any) -> None:
    def matchup_items(row: Any) -> list[str]:
        data = _prepared_row(row)
        context = _short_context(data, 3)
        if context:
            return _dedupe(context)[:3]
        if _needs_verification(data):
            return ["Watchlist until live odds/context match.", "Re-run live APIs before official use."]
        return ["Context is limited; recheck price and news before publishing."]

    def team_items(row: Any, side: str = "") -> list[str]:
        data = _prepared_row(row)
        items: list[str] = []
        for key in (
            f"{side}_team_form",
            f"{side}_team_record",
            f"{side}_recent_results",
            "team_stats_summary",
            "api_football_team_summary",
            "api_football_summary",
            "sports_context_summary",
            "news_summary",
            "newsapi_summary",
            "perplexity_summary",
            "perplexity_context",
        ):
            for item in _split(data.get(key)):
                if not _generic(item):
                    items.append(_trim(item, 78))
        if items:
            return _dedupe(items)[:3]
        return ["Provider team feed not matched to this row.", "Use as watchlist until confirmed."]

    def injury_items(row: Any, prefix: str = "") -> list[str]:
        data = _prepared_row(row)
        items: list[str] = []
        for key in (
            f"{prefix}_injuries",
            f"{prefix}_injury_report",
            f"{prefix}_lineup_status",
            f"{prefix}_player_notes",
            "injury_report",
            "lineup_status",
            "api_football_lineup_summary",
            "news_injury_summary",
            "news_summary",
            "newsapi_summary",
            "perplexity_summary",
            "perplexity_context",
            "sports_context_summary",
        ):
            for item in _split(data.get(key)):
                if not _generic(item):
                    items.append(_trim(item, 82))
        if items:
            return _dedupe(items)[:2]
        return ["Lineup feed not verified for this row.", "Check team news before use."]

    def risk_items(row: Any) -> list[str]:
        if _needs_verification(row):
            return ["Fallback data used.", "Verify live odds before entry.", "Do not use until price is confirmed."]
        return ["Recheck price before use.", "Avoid if key news changes."]

    def chain_items(row: Any) -> list[str]:
        data = _prepared_row(row)
        explicit: list[str] = []
        for key in ("chain_notes", "main_read", "add_on_legs", "parlay_notes", "live_betting_notes", "flash_market_notes", "prop_market_notes"):
            explicit.extend(_split(data.get(key)))
        if explicit and not _needs_verification(data):
            return _dedupe([_trim(item, 80) for item in explicit])[:3]
        if _needs_verification(data):
            return ["No parlay recommended.", "Not enough compatible selections.", "Verified odds are missing."]
        return ["Straight only unless compatible +EV legs exist.", "Do not combine without official verification."]

    module._matchup_items = matchup_items
    module.matchup_items = matchup_items
    module._team_items = team_items
    module.team_items = team_items
    module._injury_items = injury_items
    module.injury_items = injury_items
    module._risk_items = risk_items
    module.risk_items = risk_items
    module._chain_items = chain_items
    module.chain_items = chain_items


def _overlay_final(module: Any, image: Any, row: Any, language: str | None = None) -> Any:
    try:
        from PIL import ImageDraw
        img = image.convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")
        data = _prepared_row(row)
        lang = module._lang(data, language)
        action, action_color, side_color, note = _state(data)
        pick_text = module._tr(module._clean(module._pick(data), True), lang).upper()
        fy, fb = 1374, 1532
        black = getattr(module, "BLACK", (13, 14, 16))
        cream = getattr(module, "CREAM", (255, 248, 230))
        side_text = black if side_color == GOLD else cream
        draw.rounded_rectangle((20, fy, 1060, fb), radius=14, fill=black, outline=action_color, width=3)
        draw.rectangle((20, fy, 250, fb), fill=side_color)
        draw.text((40, fy + 30), module._tr("FINAL", lang), font=module._font(30, True), fill=side_text)
        rec = module._tr("RECOMMENDATION", lang)
        draw.text((40, fy + 76), rec, font=module._fit(rec, 190, 24, 12, True), fill=side_text)
        draw.text((284, fy + 18), module._tr(action, lang).upper(), font=module._fit(action, 340, 66, 18, True), fill=action_color)
        module._txt_auto(draw, 284, fy + 92, pick_text, 360, 34, 46, 8, cream, True, 1)
        module._txt_auto(draw, 670, fy + 38, module._tr(note, lang), 340, 82, 20, 8, cream, False, None)
        return img.convert("RGB")
    except Exception:
        return image


def install(module: Any | None = None) -> Any:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_DISPLAY_GUARD", "") == PATCH_VERSION:
        return module
    _install_metric_overrides(module)
    _install_item_overrides(module)
    original_page = getattr(module, "render_full_pick_magazine_page", None)
    if callable(original_page):
        def guarded_page(pick: Any, *args: Any, **kwargs: Any):
            data = _prepared_row(pick)
            image = original_page(data, *args, **kwargs)
            return _overlay_final(module, image, data, kwargs.get("language"))
        module.render_full_pick_magazine_page = guarded_page
    module._ABA_DISPLAY_GUARD = PATCH_VERSION
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
        original_apply = getattr(sale, "apply_magazine_sale_ready_patch", None)
        if callable(original_apply) and not getattr(original_apply, "_ABA_DISPLAY_GUARD", False):
            def apply_and_install(target: Any) -> Any:
                return install(original_apply(target))
            apply_and_install._ABA_DISPLAY_GUARD = True
            sale.apply_magazine_sale_ready_patch = apply_and_install
    except Exception:
        pass
    return module


install()
