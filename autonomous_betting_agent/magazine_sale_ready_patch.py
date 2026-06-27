from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from autonomous_betting_agent import magazine_api_sources as api_sources

_APPLIED_FLAG = "_ABA_SALE_READY_MAGAZINE_PATCHED"
_RENDER_FLAG = "_ABA_SALE_READY_RENDER_WRAPPED"


def _row(value: Any) -> Mapping[str, Any]:
    return api_sources._row(value)


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _get(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            text = str(value).strip().replace("%", "").replace(",", "")
            num = float(text)
            if "%" in str(value) and abs(num) > 1:
                num /= 100
            return num
        except Exception:
            continue
    return None


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    negative = (edge is not None and edge < 0) or (ev is not None and ev < 0)
    missing = edge is None or ev is None
    return edge, ev, negative, missing


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    edge, ev, negative, missing = _edge_state(row)
    requested = _get(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="").strip().upper()
    if negative:
        return "WATCHLIST", "Do not play at the listed price. Recheck only if the line improves or new information changes the edge.", False
    if missing:
        return "RESEARCH ONLY", "Critical price or edge context is missing. Confirm the line, injury/news context, and value before publishing.", False
    if requested and not any(word in requested for word in ("PLAY", "BET", "SMALL", "STANDARD")):
        return requested, _get(row, "final_explanation", "action_reason", "recommendation_reason", default="Use only after independent review."), False
    if edge is not None and ev is not None and (edge < 0.015 or ev < 0.02):
        return "PLAY SMALL", "Thin positive edge. Use only if the line remains playable and key news does not change.", True
    return "PLAY", "Positive edge confirmed at the listed price. Recheck odds and key news before entry.", True


def _clean_provider_item(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    low = value.lower()
    if not value:
        return ""
    if low.startswith("sdio checked") or low.startswith("sportsdataio configured"):
        return "No SDIO event ID returned."
    if low.startswith("api-fb lookup checked") or low.startswith("api-football checked"):
        return "API-FB lookup checked; no fixture match."
    if low.startswith("api-fb lookup only"):
        return "API-FB lookup only; fixture not verified."
    if low.startswith("news checked") or low.startswith("newsapi checked"):
        if "injury" in low or "lineup" in low:
            return "No lineup/injury headline returned."
        return "No recent matching news returned."
    if "pennsylvania, united states of america" in low:
        value = value.replace("Pennsylvania, United States of America", "PA, USA")
    return value


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _normalize_weather_line(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if not value.lower().startswith("weather:"):
        return value
    body = value.split(":", 1)[1].strip().strip(".")
    body = re.split(r"\bLocation\s*:", body, maxsplit=1, flags=re.I)[0].strip(" .")
    body = re.sub(r"\bWeatherAPI:\s*", "", body, flags=re.I)
    temp_match = re.search(r"-?\d+(?:\.\d+)?\s*°\s*[CF]\b", body, re.I)
    wind_match = re.search(r"wind\s+-?\d+(?:\.\d+)?\s*(?:kph|mph|km/h|m/s)\b", body, re.I)
    temp = temp_match.group(0).replace(" ", "") if temp_match else ""
    wind = re.sub(r"\s+", " ", wind_match.group(0)).strip() if wind_match else ""
    condition_source = body
    if temp_match:
        condition_source = condition_source.replace(temp_match.group(0), " ")
    if wind_match:
        condition_source = condition_source.replace(wind_match.group(0), " ")
    condition_parts = [part.strip(" .") for part in re.split(r"[;,\.]\s*", condition_source) if part.strip(" .")]
    conditions = _dedupe(part for part in condition_parts if not re.search(r"-?\d+(?:\.\d+)?\s*°\s*[CF]\b", part, re.I) and "wind" not in part.lower())
    condition = conditions[0] if conditions else ""
    if condition:
        condition = condition[:1].lower() + condition[1:]
    ordered = [part for part in (temp, condition, wind) if part]
    return "Weather: " + ", ".join(_dedupe(ordered)) + "." if ordered else value


def _clean_matchup_item(text: str) -> str:
    value = _clean_provider_item(text)
    low = value.lower()
    if low.startswith("weather:"):
        return _normalize_weather_line(value)
    if low.startswith("location:"):
        location = value.split(":", 1)[1].strip(" .")
        return "Location: " + api_sources._shorten_location(location) + "."
    if low.startswith("api-fb lookup checked"):
        return "API-FB lookup checked; no fixture match."
    if low.startswith("api-fb lookup only"):
        return "API-FB lookup checked; no fixture match."
    if value == "Context unavailable.":
        return "No additional context returned."
    return value


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    items = [_clean_provider_item(item) for item in api_sources.team_items(row, side)]
    compact = {
        "No SDIO event ID returned.": "No SDIO event ID.",
        "API-FB lookup checked; no fixture match.": "API-FB: no fixture match.",
    }
    return _dedupe(compact.get(item, item) for item in items)[:3]


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    items = [_clean_provider_item(item) for item in api_sources.injury_items(row, prefix)]
    return _dedupe(items or ["No player/injury update returned."])[:2]


def sale_ready_matchup_items(row: Any) -> list[str]:
    items = [_clean_matchup_item(item) for item in api_sources.matchup_items(row)]
    return _dedupe(items)[:3]


def sale_ready_risk_items(row: Any) -> list[str]:
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return [
            "Negative edge at current price.",
            "Do not play unless price improves.",
            "Recheck odds and key news.",
        ]
    if missing:
        return [
            "Research only: edge incomplete.",
            "Confirm price before entry.",
            "Wait for verified context.",
        ]
    risk = _get(row, "risk", "risk_level", "risk_label", "profit_guard_status", default="VOLUME OK").replace("_", " ").upper()
    return [
        f"Risk status: {risk}.",
        "Recheck odds before entry.",
        "Avoid if key news changes.",
    ]


def sale_ready_chain_items(row: Any) -> list[str]:
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return [
            "Do not chain negative-EV picks.",
            "Avoid parlays unless edge turns positive.",
            "Recheck price before including.",
        ]
    if missing:
        return [
            "Do not combine unverified picks.",
            "Wait for complete edge data.",
            "Straight-only review.",
        ]
    return [
        "Straight only: research.",
        "Do not combine without verification.",
        "Wait for better context or price.",
    ]


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    key_tuple = tuple(keys)
    if any(key in key_tuple for key in ("risk", "risk_level", "risk_label", "profit_guard_status", "risk_note", "risk_notes")):
        return sale_ready_risk_items(row)[:limit]
    if any(key in key_tuple for key in ("chain_note", "chain_notes", "parlay_note", "parlay_notes", "combo_note")):
        return sale_ready_chain_items(row)[:limit]
    if "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        return sale_ready_matchup_items(row)[:limit]
    if "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        return sale_ready_injury_items(row, "away")[:limit]
    return sale_ready_team_items(row)[:limit]


def _patch_visuals(module: Any) -> None:
    current_render = getattr(module, "render_full_pick_magazine_page", None)
    if getattr(current_render, _RENDER_FLAG, False):
        return
    original_render = current_render
    original_hero = getattr(module, "_hero", None)
    original_headlines = getattr(module, "_draw_matchup_headlines", None)
    original_bullets = getattr(module, "_bullets_auto", None)

    def patched_hero(img: Any, background: Any, mode: str, opacity: float) -> None:
        loaded = module._load_image(background)
        mode_text = str(mode or "hero_right").lower()
        if loaded is not None and mode_text not in {"none", "full_page"}:
            draw = module.ImageDraw.Draw(img, "RGBA")
            box = module.HERO_IMAGE_BOX
            pad = 8
            draw.rounded_rectangle(box, radius=6, fill=module.CREAM + (255,), outline=module.BLACK + (215,), width=3)
            inner = (box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad)
            slot = module._cover(loaded, (inner[2] - inner[0], inner[3] - inner[1]), 0.28)
            slot = module.ImageEnhance.Color(slot).enhance(1.04)
            slot = module.ImageEnhance.Contrast(slot).enhance(1.10)
            img.alpha_composite(slot, inner[:2])
            draw.rectangle(inner, outline=module.BLACK + (140,), width=1)
            return
        if callable(original_hero):
            original_hero(img, background, mode, opacity)

    def patched_headline_context_lines(row: Any) -> list[str]:
        values: list[str] = []
        for key in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
            values += module._split(module._row(row).get(key))
        cleaned = [item for item in values if item and "context unavailable" not in item.lower()]
        return cleaned or ["No additional context returned."]

    def repaint_vs_and_context(draw: Any, row: Any, lang: str) -> None:
        box = module.VS_BADGE_BOX
        draw.rectangle((box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4), fill=module.PAPER)
        badge = (box[0], box[1] + 8, box[2] + 6, box[3] - 8)
        draw.rounded_rectangle(badge, radius=14, fill=module.BLACK, outline=module.CREAM, width=2)
        font = module._fit("VS", badge[2] - badge[0] - 10, 28, 14, True)
        tbox = draw.textbbox((0, 0), "VS", font=font)
        draw.text((badge[0] + ((badge[2] - badge[0]) - (tbox[2] - tbox[0])) / 2, badge[1] + ((badge[3] - badge[1]) - (tbox[3] - tbox[1])) / 2 - 1), "VS", font=font, fill=module.CREAM)
        ctx_box = module.CONTEXT_LINE_BOX
        context = module._tr(patched_headline_context_lines(row)[0], lang)
        draw.rectangle((ctx_box[0] - 2, ctx_box[1] - 2, ctx_box[2], ctx_box[3]), fill=module.PAPER)
        module._draw_small_text_box(draw, context, ctx_box, module.TEXT, 17, 11, False, 2)

    def patched_headlines(draw: Any, away_label: str, home_label: str, sport: str, row: Any, lang: str):
        result = original_headlines(draw, away_label, home_label, sport, row, lang) if callable(original_headlines) else {}
        repaint_vs_and_context(draw, row, lang)
        return result

    def patched_bullets(draw: Any, x: int, y: int, items: list[str], width: int, height: int, color: Any, start: int = 22, minimum: int = 10, limit: int | None = None, lang: str = "en") -> None:
        compact_items = _dedupe(items)
        if callable(original_bullets):
            original_bullets(draw, x, y, compact_items, width, height, color, start, max(minimum, 10), limit, lang)

    def repaint_evidence_strip(draw: Any) -> None:
        left_x, left_w = 20, 320
        draw.rectangle((left_x + 8, 1088, left_x + left_w - 8, 1120), fill=module.CREAM)
        draw.line((left_x + 12, 1088, left_x + left_w - 12, 1088), fill=module.BLACK + (135,), width=1)
        module._txt_auto(draw, left_x + 22, 1094, "Price check required before entry.", left_w - 44, 22, 13, 9, module.BLACK, True, 1)

    def draw_guidance_body(draw: Any, box: tuple[int, int, int, int], items: list[str], color: Any) -> None:
        draw.rectangle(box, fill=module.CREAM)
        y = box[1] + 10
        for item in items[:3]:
            draw.ellipse((box[0] + 12, y + 5, box[0] + 24, y + 17), fill=color)
            module._txt_auto(draw, box[0] + 32, y, item, box[2] - box[0] - 46, 30, 15, 11, module.TEXT, False, 2)
            y += 30

    def repaint_bottom_guidance(draw: Any, row: Any) -> None:
        draw_guidance_body(draw, (34, 1234, 326, 1348), sale_ready_risk_items(row), module.RED)
        draw_guidance_body(draw, (724, 1234, 1050, 1348), sale_ready_chain_items(row), module.BLUE)

    def repaint_final(img: Any, row: Any, lang: str) -> None:
        draw = module.ImageDraw.Draw(img, "RGBA")
        action, explanation, playable = sale_ready_recommendation(row)
        pick_text = module._tr(module._clean(module._pick(row), True), lang).upper()
        fy, fb = 1374, 1532
        accent = module.GREEN if playable else (239, 182, 58)
        side = module.GREEN if playable else module.BLUE
        outline = module.GREEN if playable else module.RED
        draw.rounded_rectangle((20, fy, 1060, fb), radius=14, fill=module.BLACK, outline=outline, width=3)
        draw.rectangle((20, fy, 250, fb), fill=side)
        draw.text((40, fy + 30), module._tr("FINAL", lang), font=module._font(30, True), fill=module.CREAM)
        rec = module._tr("RECOMMENDATION", lang)
        draw.text((40, fy + 76), rec, font=module._fit(rec, 190, 24, 12, True), fill=module.CREAM)
        draw.text((284, fy + 18), module._tr(action, lang).upper(), font=module._fit(action.upper(), 340, 58, 18, True), fill=accent)
        module._txt_auto(draw, 284, fy + 92, pick_text, 360, 34, 40, 10, module.CREAM, True, 1)
        module._txt_auto(draw, 670, fy + 36, module._tr(explanation, lang), 340, 88, 19, 10, module.CREAM, False, None)

    def patched_render(pick: Any, *args: Any, **kwargs: Any):
        img = original_render(pick, *args, **kwargs)
        lang = module._lang(pick, kwargs.get("language") if "language" in kwargs else (args[10] if len(args) >= 11 else None))
        draw = module.ImageDraw.Draw(img, "RGBA")
        repaint_evidence_strip(draw)
        repaint_bottom_guidance(draw, pick)
        repaint_final(img, pick, lang)
        return img

    def patched_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return module._png(module.render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    setattr(patched_render, _RENDER_FLAG, True)
    setattr(patched_png, _RENDER_FLAG, True)
    module._hero = patched_hero
    module._headline_context_lines = patched_headline_context_lines
    module._draw_matchup_headlines = patched_headlines
    module._bullets_auto = patched_bullets
    module.render_full_pick_magazine_page = patched_render
    module.render_full_pick_magazine_page_png = patched_png


def apply_magazine_sale_ready_patch(module: Any) -> Any:
    api_sources.apply_magazine_api_patch(module)
    module.team_items = sale_ready_team_items
    module.injury_items = sale_ready_injury_items
    module.matchup_items = sale_ready_matchup_items
    module.risk_items = sale_ready_risk_items
    module.chain_items = sale_ready_chain_items
    module._team_items = sale_ready_team_items
    module._injury_items = sale_ready_injury_items
    module._matchup_items = sale_ready_matchup_items
    module._risk_items = sale_ready_risk_items
    module._chain_items = sale_ready_chain_items
    module._items = _items_from_context
    module.sale_ready_recommendation = sale_ready_recommendation
    _patch_visuals(module)
    if not str(getattr(module, "MAGAZINE_STYLE_VERSION", "")).endswith("_sale_ready_risk_chain_v1"):
        module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_sale_ready_risk_chain_v1"
    setattr(module, _APPLIED_FLAG, True)
    return module
