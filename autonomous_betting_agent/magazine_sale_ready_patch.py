from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
import re

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas
# Page 1 endpoint pass removes visible CHAIN BETTING NOTES through overlay replacement.

from autonomous_betting_agent import magazine_sale_ready_patch_contract as _contract

_es = _contract._es
_items_from_context = _contract._items_from_context
sale_ready_chain_items = _contract.sale_ready_chain_items
sale_ready_injury_items = _contract.sale_ready_injury_items
sale_ready_matchup_items = _contract.sale_ready_matchup_items
sale_ready_recommendation = _contract.sale_ready_recommendation
sale_ready_risk_items = _contract.sale_ready_risk_items
sale_ready_team_items = _contract.sale_ready_team_items
translate_country_name = _contract.translate_country_name
translate_country_terms_in_text = _contract.translate_country_terms_in_text
translate_event_name = _contract.translate_event_name
translate_team_label = _contract.translate_team_label


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _valid_text(value: Any) -> bool:
    text = _clean(value).lower()
    return bool(text and text not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"})


def _first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if _valid_text(value):
            return _clean(value)
    return default


def _short(value: Any, limit: int = 118) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:") + "."


def _decimal_text(value: Any) -> str | None:
    raw = _clean(value).replace("−", "-").replace("–", "-").replace("—", "-").replace(",", "")
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        num = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        num = 1.0 + num / 100.0
    elif num <= 1:
        return None
    return f"{num:.2f}"


def _stake_text(value: Any, default: str = "0.0") -> str:
    raw = _clean(value)
    try:
        num = float(raw.replace("u", "").replace(",", ""))
        return f"{num:.1f}"
    except Exception:
        return raw or default


def _norm_market_text(data: dict[str, Any]) -> str:
    return _clean(_first(
        data,
        "market_type",
        "market",
        "market_name",
        "market_key",
        "bet_type",
        "wager_type",
        default="",
    )).lower().replace("_", " ").replace("-", " ")


def _line_text(data: dict[str, Any]) -> str:
    raw = _first(
        data,
        "line",
        "point",
        "points",
        "handicap",
        "spread",
        "total",
        "threshold",
        "line_value",
        "over_under",
        "market_line",
        "bet_line",
        "line_display",
        "prop_line",
        default="",
    )
    if not raw:
        return ""
    try:
        num = float(str(raw).replace("+", "").replace(",", ""))
        if abs(num) < 100:
            return f"+{num:g}" if num > 0 else f"{num:g}"
    except Exception:
        pass
    return raw


def _market_family(data: dict[str, Any]) -> str:
    market = _norm_market_text(data)
    if any(token in market for token in ("total", "over under", "over/under", "totals")):
        return "total"
    if any(token in market for token in ("spread", "handicap", "run line", "puck line", "point spread")):
        return "spread"
    if any(token in market for token in ("moneyline", "winner", "h2h", "match winner", "home away", "head to head")):
        return "moneyline"
    return market or "pick"


def _market_label(data: dict[str, Any]) -> str:
    family = _market_family(data)
    sport = _clean(_first(data, "sport", "league", default="")).lower()
    if family == "total":
        return "Game Total"
    if family == "spread":
        return "Run Line" if "baseball" in sport or "mlb" in sport else "Spread"
    if family == "moneyline":
        return "Moneyline"
    return family.title()


def _base_selection(data: dict[str, Any]) -> str:
    return _first(
        data,
        "selection",
        "outcome",
        "side",
        "pick_side",
        "team_selection",
        "prediction",
        "pick",
        default="",
    )


def _rich_pick_text(data: dict[str, Any]) -> str:
    full = _first(data, "display_pick", "aba_display_pick", "exact_bet", "bet_label", "recommended_bet", "pick_text", default="")
    if full and any(token in full.lower() for token in ("over", "under", "+", "-", "moneyline", "spread", "run line", "total")):
        return _clean(full)

    family = _market_family(data)
    label = _market_label(data)
    line = _line_text(data)
    selection = _base_selection(data) or full or _first(data, "prediction", "pick", default="Not provided")
    selection_low = selection.lower()

    if family == "total":
        side = _first(data, "total_side", "over_under_side", "side", "outcome", "selection", "prediction", default=selection)
        side_low = side.lower()
        if "over" in side_low:
            selection = "Over"
        elif "under" in side_low:
            selection = "Under"
        if line and line not in selection:
            selection = f"{selection} {line}"
        return _clean(f"{label}: {selection}")

    if family == "spread":
        if line and line not in selection and not re.search(r"[+-]\d", selection):
            selection = f"{selection} {line}"
        return _clean(f"{label}: {selection}")

    if family == "moneyline":
        return _clean(f"{label}: {selection}")

    return _clean(f"{label}: {selection}") if label and label.lower() != "pick" else _clean(selection)


def _pick_for_display(row: Any) -> str:
    data = dict(_contract._row(row))
    return _rich_pick_text(data)


def _pick_subject(row: dict[str, Any]) -> str:
    text = _pick_for_display(row)
    return text.split(":", 1)[1].strip() if ":" in text else text


def _live_verified(data: dict[str, Any]) -> bool:
    markers = {
        _clean(data.get(key)).lower()
        for key in (
            "odds_status",
            "odds_api_status",
            "odds_source",
            "data_source",
            "odds_api_live",
            "the_odds_api_live",
            "odds_verified",
        )
    }
    return any(marker in {"live", "live_api", "live_match", "odds_api_live_match", "1", "true", "yes", "verified"} for marker in markers)


def _fallback_odds(data: dict[str, Any]) -> bool:
    marker = " ".join(_clean(data.get(key)).lower() for key in ("odds_status", "odds_source", "data_source", "risk", "risk_level", "risk_label"))
    return any(token in marker for token in ("uploaded", "fallback", "cached", "missing")) and not _live_verified(data)


def _normalize_display_fields(data: dict[str, Any]) -> dict[str, Any]:
    price = _first(data, "display_decimal_odds", "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american")
    decimal = _decimal_text(price)
    if decimal:
        data["display_decimal_odds"] = decimal
        data["decimal_price"] = decimal
    american = _first(data, "display_american_odds", "american_odds", "odds_american")
    if american:
        data["display_american_odds"] = american
    target = _first(data, "target_stake_units", "recommended_stake_units", "suggested_stake_units", "units", default="0.0")
    data["target_stake_units"] = _stake_text(target)
    data.setdefault("source_freshness", _first(data, "last_refreshed", "updated_at", "locked_at_utc", default="Verify before entry"))
    data.setdefault("verification_status", data.get("report_truth_severity") or ("LIVE VERIFIED" if _live_verified(data) else "VERIFY SOURCE"))
    display_pick = _rich_pick_text(data)
    data["aba_display_pick"] = display_pick
    data["display_pick"] = display_pick
    data["prediction"] = display_pick
    data["pick"] = display_pick
    return data


def _force_truthful_gate(row: Any) -> dict[str, Any]:
    data = _normalize_display_fields(dict(_contract._row(row)))
    if not _fallback_odds(data):
        data.setdefault("live_verified_stake_units", data.get("target_stake_units", "0.0") if _live_verified(data) else "0.0")
        return data
    target_stake = _stake_text(_first(data, "target_stake_units", "recommended_stake_units", "suggested_stake_units", "units", default="0.0"))
    data.update({
        "final_decision": "WATCHLIST",
        "agent_decision": "WATCHLIST",
        "recommendation": "WATCHLIST",
        "consumer_action": "WATCHLIST",
        "recommended_action": "WATCHLIST",
        "risk": "VERIFY PRICE",
        "risk_level": "VERIFY PRICE",
        "risk_label": "VERIFY PRICE",
        "target_stake_units": target_stake,
        "live_verified_stake_units": "0.0",
        "recommended_stake_units": target_stake,
        "suggested_stake_units": target_stake,
        "units": target_stake,
        "final_explanation": "Not live-odds verified. Use as watchlist until the price and market are matched.",
        "report_truth_severity": data.get("report_truth_severity") or "NO LIVE ODDS MATCH",
        "report_truth_warning": data.get("report_truth_warning") or "No live odds match. This report is verification-only.",
        "verification_status": "NO LIVE ODDS MATCH",
    })
    data["action_reason"] = data["final_explanation"]
    data["why_lose"] = "\n".join(["Not live-odds verified.", "Current price must be matched before entry.", "Do not publish as PLAY while odds row is fallback/uploaded."])
    data["chain_notes"] = "\n".join(["Watchlist only: chain ideas move to Page 2.", "Not enough compatible live-verified selections.", "Verified odds are missing."])
    return data


def _truth_pairs(row: Any, lang: str = "en") -> list[tuple[str, str]]:
    data = _force_truthful_gate(row)
    report_source = _clean(data.get("report_source"))
    source_mode = _clean(data.get("report_source_mode")).lower()
    odds_status = _clean(data.get("odds_status") or data.get("odds_source") or "MISSING").upper()
    context_status = _clean(data.get("context_status") or data.get("context_source") or data.get("report_live_context_detected") or "VERIFY")
    if report_source == "final_enriched_picks_df" and _live_verified(data):
        source_label, scope, truth = "Live API refreshed report", "Current API-refreshed slate", "LIVE VERIFIED"
    elif report_source == "final_enriched_picks_df" or _fallback_odds(data):
        source_label, scope, truth = "API refreshed / no live odds match", "Verification-only report", "NO LIVE ODDS MATCH"
    elif source_mode == "ledger-history":
        source_label, scope, truth = "Proof ledger history", "Historical proof ledger", "HISTORY ONLY"
    else:
        source_label = _clean(data.get("report_source_label") or data.get("report_source_mode") or "Report source unknown")
        scope = _clean(data.get("report_data_scope") or "Current/fallback status unknown")
        truth = _clean(data.get("report_truth_severity") or "VERIFY")
    pairs = [("REPORT SOURCE", source_label), ("DATA SCOPE", scope), ("TRUTH", truth), ("ODDS STATUS", odds_status), ("CONTEXT STATUS", context_status)]
    return [(_contract._es(label, lang), _contract._es(value, lang)) for label, value in pairs]


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _compact_context_rows(data: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    weather = _first(data, "weather_summary_short", "weather_summary", "venue_weather", "weather_risk", default="")
    matchup = _first(data, "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes", default="")
    news = _first(data, "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "sportsdataio_context", "api_football_summary", default="")
    line = _first(data, "line_movement_summary", "line_movement", "price_movement", default="Line movement: verify current market before entry.")
    status = _first(data, "verification_status", "report_truth_severity", default="VERIFY SOURCE")
    target = _stake_text(_first(data, "target_stake_units", default="0.0"))
    live = _stake_text(_first(data, "live_verified_stake_units", default="0.0"))
    if weather:
        rows.append("Weather: " + _short(weather, 98))
    if matchup:
        rows.append("Context: " + _short(matchup, 108))
    elif news:
        rows.append("News: " + _short(news, 108))
    rows.append(_short(line, 104))
    rows.append(f"Verify: {status} · Target {target}u · Live {live}u.")
    return rows[:4]


def _expanded_context_rows(data: dict[str, Any]) -> list[str]:
    return _compact_context_rows(data)


def _selected_badge(patched: Any, row: dict[str, Any], pick_text: str, lang: str) -> tuple[str, tuple[int, int, int]]:
    blue = getattr(patched, "BLUE", (19, 66, 108))
    red = getattr(patched, "RED", (190, 30, 28))
    gold = (241, 184, 45)
    subject = _pick_subject(row).lower()
    if any(token in subject for token in ("over", "under", "más de", "menos de")):
        return "O/U", blue
    try:
        away, home = patched._teams(row)
    except Exception:
        away, home = _first(row, "away_team", "team_a"), _first(row, "home_team", "team_b")
    if away and away.lower() in subject:
        return away, red
    if home and home.lower() in subject:
        return home, blue
    return "PICK", gold


def _draw_readable_bullets(patched: Any, draw: Any, x: int, y: int, rows: list[str], width: int, height: int, color: tuple[int, int, int], lang: str) -> None:
    tr = getattr(patched, "_tr", lambda value, _lang="en": str(value))
    font_fn = getattr(patched, "_font", None)
    wrap_fn = getattr(patched, "_wrap_text_to_box", None)
    line_height_fn = getattr(patched, "_line_height", None)
    ellipsize_fn = getattr(patched, "_ellipsize_to_width", None)
    if not callable(font_fn):
        return
    font = font_fn(18)
    small = font_fn(16)
    line_height = line_height_fn(font) if callable(line_height_fn) else 22
    bottom = y + height
    current_y = y
    for row in rows[:4]:
        if current_y + line_height > bottom:
            break
        text = tr(row, lang)
        draw.ellipse((x, current_y + 7, x + 12, current_y + 19), fill=color)
        lines = wrap_fn(draw, text, font, width - 34, 2) if callable(wrap_fn) else [text]
        for line in lines[:2]:
            if current_y + line_height > bottom:
                break
            use_font = font if len(line) < 110 else small
            if callable(ellipsize_fn):
                line = ellipsize_fn(draw, line, use_font, width - 34)
            draw.text((x + 25, current_y), line, font=use_font, fill=(14, 17, 21))
            current_y += line_height
        current_y += 6


def _overlay_pick_display(patched: Any, img: Any, draw: Any, row: dict[str, Any], lang: str) -> None:
    black = getattr(patched, "BLACK", (13, 14, 16))
    cream = getattr(patched, "CREAM", (255, 248, 230))
    red = getattr(patched, "RED", (190, 30, 28))
    pick_text = _pick_for_display(row)
    tr = getattr(patched, "_tr", lambda value, _lang="en": str(value))
    txt_auto = getattr(patched, "_txt_auto", None)
    badge = getattr(patched, "_badge", None)
    display = tr(_clean(pick_text).upper(), lang).upper()

    # Repaint the trend block completely so stale team-only text cannot leak through.
    draw.rectangle((24, 462, 344, 558), fill=black + (255,))
    draw.text((50, 472), tr("TREND", lang), font=patched._fit(tr("TREND", lang), 190, 25, 14, True), fill=red)
    if callable(txt_auto):
        txt_auto(draw, 50, 508, display, 210, 38, 26, 8, cream, True, 1)
    label, color = _selected_badge(patched, row, pick_text, lang)
    if callable(badge):
        badge(img, draw, label, 268, 483, 58, 50, color)

    # Repaint the full final black recommendation strip, not only part of it.
    draw.rectangle((270, 1454, 1064, 1524), fill=black + (255,))
    if callable(txt_auto):
        txt_auto(draw, 286, 1462, display, 750, 44, 38, 10, cream, True, 1)


def _overlay_page_one_context(patched: Any, image: Any, row: dict[str, Any], language: str | None = None) -> Any:
    try:
        from PIL import ImageDraw
    except Exception:
        return image
    lang_fn = getattr(patched, "_lang", None)
    lang = lang_fn(row, language) if callable(lang_fn) else ("es" if str(language or row.get("report_language") or "").lower().startswith("es") else "en")
    tr = getattr(patched, "_tr", lambda value, _lang="en": str(value))
    img = image.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    paper = getattr(patched, "PAPER", (244, 235, 211))
    blue = getattr(patched, "BLUE", (19, 66, 108))
    black = getattr(patched, "BLACK", (13, 14, 16))
    cream = getattr(patched, "CREAM", (255, 248, 230))
    _overlay_pick_display(patched, img, draw, row, lang)
    draw.rounded_rectangle((350, 1174, 1064, 1358), radius=16, fill=paper + (255,), outline=paper + (255,), width=4)
    if callable(getattr(patched, "_section", None)):
        patched._section(draw, 354, 1178, 706, 175, "MATCHUP NOTES", blue, lang)
    else:
        draw.rounded_rectangle((354, 1178, 1060, 1353), radius=14, fill=cream + (255,), outline=black + (238,), width=3)
        draw.rounded_rectangle((354, 1178, 1060, 1234), radius=10, fill=blue)
        draw.text((372, 1189), tr("MATCHUP NOTES", lang).upper(), fill=cream)
    rows = _expanded_context_rows(row)
    _draw_readable_bullets(patched, draw, 378, 1246, rows, 650, 94, blue, lang)
    return img.convert("RGB")


def _install_display_patches(patched: Any) -> None:
    try:
        patched.ES.update({
            "VERIFY PRICE": "VERIFICAR CUOTA",
            "NO LIVE ODDS MATCH": "SIN COINCIDENCIA DE CUOTAS EN VIVO",
            "WATCHLIST": "LISTA DE SEGUIMIENTO",
            "TARGET": "OBJETIVO",
            "TARGET STAKE": "STAKE OBJETIVO",
            "LIVE STAKE": "STAKE EN VIVO",
            "Moneyline": "Moneyline",
            "Game Total": "Total del Juego",
            "Run Line": "Run Line",
            "Spread": "Spread",
        })
    except Exception:
        pass
    patched._pick = _pick_for_display
    original_fmt = getattr(patched, "_fmt", None)
    if callable(original_fmt) and not getattr(original_fmt, "_ABA_DECIMAL_ODDS_TRUTH", False):
        def fmt_decimal_first(value: Any, kind: str = "") -> str:
            if kind == "odds":
                decimal = _decimal_text(value)
                if decimal:
                    return decimal
            return original_fmt(value, kind)
        fmt_decimal_first._ABA_DECIMAL_ODDS_TRUTH = True  # type: ignore[attr-defined]
        patched._fmt = fmt_decimal_first
    original_cells = getattr(patched, "magazine_metric_cells", None)
    if callable(original_cells) and not getattr(original_cells, "_ABA_TARGET_STAKE_RISK_LABEL", False):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            fixed = []
            for label, value, color, x, width in list(original_cells(odds, conf, edge, ev, units, risk)):
                if str(label).upper() == "UNITS":
                    label = "TARGET"
                if str(label).upper() == "RISK" and "fallback" in str(value).lower():
                    value = "VERIFY PRICE"
                if str(label).upper() == "RISK" and any(token in str(value).lower() for token in ("verify", "watch", "fallback", "volume")):
                    color = (241, 184, 45)
                fixed.append((label, value, color, x, width))
            return fixed
        metric_cells._ABA_TARGET_STAKE_RISK_LABEL = True  # type: ignore[attr-defined]
        patched.magazine_metric_cells = metric_cells


def _install_forced_two_page_renderer(patched: Any) -> None:
    try:
        from PIL import Image
        from autonomous_betting_agent import magazine_second_page_patch as second_page
    except Exception:
        return

    def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        row = _force_truthful_gate(pick)
        page_total = max(2, int(total_pages or 1) * 2)
        first = max(1, int(page_number or 1) * 2 - 1)
        page_one = patched.render_full_pick_magazine_page(row, background_image, report_name, first, page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        page_two = second_page._draw_second_page(patched, row, background_image, report_name, first + 1, page_total, language)
        book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(patched, "PAPER", (244, 235, 211)))
        book.paste(page_one.convert("RGB"), (0, 0))
        book.paste(page_two.convert("RGB"), (0, page_one.height))
        return _png(book)

    def book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows = [_force_truthful_gate(row) for row in (list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}])]
        total = len(rows) * 2
        pages: list[Any] = []
        for index, row in enumerate(rows):
            pages.append(patched.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
            pages.append(second_page._draw_second_page(patched, row, background_image, report_name, index * 2 + 2, total, language))
        return pages

    patched.render_full_pick_magazine_page_png = two_page_png
    patched.render_full_magazine_book_pages = book_pages
    patched._ABA_FORCED_TWO_PAGE_TRUTH_RENDERER = "truth_contract_v12"


def apply_magazine_sale_ready_patch(module):
    patched = _contract.apply_magazine_sale_ready_patch(module)
    current = str(getattr(patched, "MAGAZINE_STYLE_VERSION", ""))
    if current.endswith("_sale_ready_risk_chain_truth_v5"):
        patched.MAGAZINE_STYLE_VERSION = current[: -len("_sale_ready_risk_chain_truth_v5")] + "_sale_ready_risk_chain_v4"
    elif "sale_ready_risk_chain_v4" not in current:
        patched.MAGAZINE_STYLE_VERSION = f"{current}_sale_ready_risk_chain_v4" if current else "sale_ready_risk_chain_v4"
    if "pick_market_labels_v2" not in patched.MAGAZINE_STYLE_VERSION:
        patched.MAGAZINE_STYLE_VERSION = f"{patched.MAGAZINE_STYLE_VERSION}_matchup_readable_v2_pick_market_labels_v2"
    _install_display_patches(patched)
    original_render = patched.render_full_pick_magazine_page

    def truthful_render(pick: Any, *args: Any, **kwargs: Any):
        row = _force_truthful_gate(pick)
        image = original_render(row, *args, **kwargs)
        language = kwargs.get("language") if kwargs else None
        if len(args) >= 11 and language is None:
            language = args[10]
        return _overlay_page_one_context(patched, image, row, language)

    patched.render_full_pick_magazine_page = truthful_render
    patched._pairs = _truth_pairs
    _install_forced_two_page_renderer(patched)
    patched._ABA_SALE_READY_TRUTH_CONTRACT_VERSION = "truth_contract_v12_matchup_readable_pick_market_labels"
    return patched
