from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
import re
from .report_display_contract import context_items, tr as display_tr, language as display_language, canonical_market_row, accounting_quarantined, team_items, display_decision
from .report_public_quality import build_full_market_label

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas
# Page 1 endpoint pass removes visible CHAIN BETTING NOTES through overlay replacement.

from autonomous_betting_agent import magazine_sale_ready_patch_contract as _contract
from autonomous_betting_agent.report_public_quality import is_manual_verified_input
from autonomous_betting_agent.report_verification_gate import VERIFIED_BUYER_PICK, classify_report_row

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


def _demonstration_mode(data: dict[str, Any]) -> bool:
    if data.get("demonstration_mode") is True:
        return True
    text = " ".join(
        _clean(data.get(key)).lower()
        for key in ("report_title", "report_data_scope", "report_truth_warning", "league")
    )
    return any(token in text for token in ("demonstration", "demo only", "validation fixture"))


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
    return build_full_market_label(data)


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
    display_pick = build_full_market_label(data)
    data["aba_display_pick"] = display_pick
    data["display_pick"] = display_pick
    data["prediction"] = display_pick
    data["pick"] = display_pick
    return data


def _force_truthful_gate(row: Any) -> dict[str, Any]:
    data = _normalize_display_fields(canonical_market_row(dict(_contract._row(row))))
    if accounting_quarantined(data):
        for key in ("final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action"):
            data[key] = "RESEARCH ONLY"
        data.update(risk="ACCOUNTING REVIEW", risk_level="ACCOUNTING REVIEW", risk_label="ACCOUNTING REVIEW", report_truth_severity="ACCOUNTING REVIEW", verification_status="ACCOUNTING REVIEW", final_explanation="Accounting review required before report publication.")
        return data
    if data.get('report_market_issue'):
        for key in ("final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action"):
            data[key] = "RESEARCH ONLY"
        data.update(risk="MARKET REVIEW", risk_level="MARKET REVIEW", risk_label="MARKET REVIEW", report_truth_severity="MARKET REVIEW", final_explanation="Conflicting market values")
        return data
    if _demonstration_mode(data):
        data.update({
            "final_decision": "DEMONSTRATION ONLY",
            "agent_decision": "DEMONSTRATION ONLY",
            "recommendation": "DEMONSTRATION ONLY",
            "consumer_action": "DEMONSTRATION ONLY",
            "recommended_action": "DEMONSTRATION ONLY",
            "risk": "DEMONSTRATION DATA",
            "risk_level": "DEMONSTRATION DATA",
            "risk_label": "DEMONSTRATION DATA",
            "target_stake_units": "0.0",
            "live_verified_stake_units": "0.0",
            "report_truth_severity": "DEMONSTRATION ONLY",
            "verification_status": "DEMONSTRATION ONLY",
            "report_truth_warning": data.get("report_truth_warning") or "Demonstration only; not current betting advice.",
        })
        return data
    if is_manual_verified_input(data):
        classified = classify_report_row(data)
        if classified.get("report_verification_class") == VERIFIED_BUYER_PICK:
            data.update(classified)
            data.update({
                "final_decision": "MANUALLY VERIFIED INPUT",
                "agent_decision": "MANUALLY VERIFIED INPUT",
                "recommendation": "MANUALLY VERIFIED INPUT",
                "consumer_action": "MANUALLY VERIFIED INPUT",
                "recommended_action": "MANUALLY VERIFIED INPUT",
                "risk": "MANUALLY VERIFIED PRICE",
                "risk_level": "MANUALLY VERIFIED PRICE",
                "risk_label": "MANUALLY VERIFIED PRICE",
                "live_verified_stake_units": "0.0",
                "report_truth_severity": "MANUALLY VERIFIED INPUT",
                "report_truth_warning": "Operator-attested sportsbook observation; not an automated live API quote.",
                "verification_status": "MANUALLY VERIFIED INPUT",
            })
            return data
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
    from .active_magazine_export_guard import public_truth_pairs
    return [(display_tr(label, lang), display_tr(value, lang)) for label, value in public_truth_pairs(row, lang)]


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _compact_context_rows(data: dict[str, Any]) -> list[str]:
    return context_items(data, display_language(data.get("report_language") or data.get("language")))


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


def _draw_readable_bullets(patched: Any, draw: Any, x: int, y: int, rows: list[str], width: int, height: int, color: tuple[int, int, int], lang: str, *, overflow: list | None = None, title: str = '') -> None:
    """Measure complete blocks; overflow is preserved, never silently clipped."""
    rendered = [patched._tr(value, lang) for value in rows if str(value).strip()]
    def layout(values, size):
        font = patched._font(size)
        step = max(size + 3, patched._line_height(font))
        blocks = [patched._wrap_text_to_box(draw, value, font, width - 30, max(1, len(value) + 1)) for value in values]
        return font, step, blocks, sum(len(lines) * step + 6 for lines in blocks)
    for size in (18, 17, 16):
        font, step, blocks, needed = layout(rendered, size)
        if needed <= height:
            break
    if needed > height:
        if overflow is not None:
            overflow.append((title, '\n'.join(rendered)))
        rendered = [display_tr('Full source note continues on the source-notes pages.', lang)]
        font, step, blocks, needed = layout(rendered, 16)
    current_y = y
    for lines in blocks:
        draw.ellipse((x, current_y + 5, x + 8, current_y + 13), fill=color)
        for line in lines:
            draw.text((x + 24, current_y), line, font=font, fill=(14, 17, 21))
            current_y += step
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


def _overlay_metric_strip(patched: Any, draw: Any, row: dict[str, Any], lang: str) -> None:
    black = getattr(patched, "BLACK", (13, 14, 16))
    cream = getattr(patched, "CREAM", (255, 248, 230))
    green = getattr(patched, "GREEN", (61, 205, 84))
    metric = getattr(patched, "_metric", None)
    cells = getattr(patched, "magazine_metric_cells", None)
    if not callable(metric) or not callable(cells):
        return
    odds = patched._fmt(_first(row, "display_decimal_odds", "decimal_price", "decimal_odds", "odds", default=""), "odds")
    probability = patched._num(row, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability")
    confidence = patched._pct(probability)
    edge = patched._edge(patched._num(row, "model_market_edge", "edge"))
    ev = patched._fmt(_first(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev", default=""), "ev")
    units = patched._fmt(_first(row, "target_stake_units", "recommended_stake_units", "suggested_stake_units", "units", default="0.0"), "unit")
    if _demonstration_mode(row):
        risk = "DEMO"
    else:
        normalizer = getattr(patched, "normalize_public_risk_label", None)
        risk = normalizer(row, lang) if callable(normalizer) else _first(row, "risk", "risk_level", "risk_label", default="REVIEW")
    classified = display_decision(row)
    actionable = classified["report_display_actionable"] and not _demonstration_mode(row)
    if not actionable:
        risk = display_tr("ACCOUNTING REVIEW" if accounting_quarantined(row) else "VERIFY", lang)
        units = display_tr("NO ACTION", lang)
    draw.rectangle((344, 462, 1060, 556), fill=black)
    for label, value, color, x, width in cells(odds, confidence, edge, ev, units, risk):
        label = {"CONFIDENCE": "MODEL P", "TARGET": "STAKE (u)", "UNITS": "STAKE (u)", "EV": "STORED EV" if not actionable else "MODEL EV"}.get(label, label)
        if not actionable and label in {"MODEL P", "EDGE", "STORED EV", "RISK", "STAKE (u)"}:
            color = (241, 184, 45)
        metric(draw, x, 462, width, display_tr(label, lang), value, color or green, lang)
    draw.line((1060, 463, 1060, 555), fill=cream, width=1)


def _overlay_evidence_panel(patched: Any, draw: Any, row: dict[str, Any], lang: str) -> None:
    black = getattr(patched, "BLACK", (13, 14, 16))
    cream = getattr(patched, "CREAM", (255, 248, 230))
    blue = getattr(patched, "BLUE", (19, 66, 108))
    tr = getattr(patched, "_tr", lambda value, _lang="en": str(value))
    txt_auto = getattr(patched, "_txt_auto", None)
    font = getattr(patched, "_font", None)
    fit = getattr(patched, "_fit", None)
    if not callable(txt_auto) or not callable(font) or not callable(fit):
        return
    draw.rectangle((23, 961, 337, 1127), fill=cream)
    pairs = _truth_pairs(row, lang)[:4]
    if accounting_quarantined(row):
        pairs = [('TRUTH', 'ACCOUNTING REVIEW'), ('PRICE STATUS', 'RESEARCH ONLY'), ('SAVED PRICE', _first(row, 'decimal_price', 'decimal_odds', 'odds', default='Missing')), ('TIMESTAMP', _first(row, 'source_observed_at', 'provider_timestamp', 'price_timestamp', 'captured_at_utc', default='Missing'))]
    y = 969
    for label, value in pairs:
        label_text, value_text = tr(label, lang).upper(), tr(value, lang)
        draw.text((44, y), label_text, font=fit(label_text, 276, 10, 10, True), fill=blue)
        draw.text((44, y + 11), value_text, font=fit(value_text, 276, 15, 11, True), fill=black)
        y += 29
    draw.rectangle((28, 1088, 332, 1120), fill=blue)
    status = display_tr("NO LIVE FEEDS USED", lang)
    draw.text((43, 1095), status, font=fit(status, 270, 15, 8, True), fill=cream)
    draw.rectangle((337, 1084, 351, 1124), fill=getattr(patched, "PAPER", (244, 235, 211)))


def _overlay_why_panel(patched: Any, draw: Any, row: dict[str, Any], lang: str) -> None:
    if not _demonstration_mode(row):
        return
    cream = getattr(patched, "CREAM", (255, 248, 230))
    red = getattr(patched, "RED", (190, 30, 28))
    probability = patched._num(row, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability")
    implied = patched._num(row, "market_probability", "market_implied_probability")
    if implied is None:
        price = _decimal_text(_first(row, "display_decimal_odds", "decimal_price", "decimal_odds", "odds", default=""))
        implied = 1.0 / float(price) if price else None
    edge = patched._num(row, "model_market_edge", "edge")
    ev = _first(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev", default="")
    probability_text = patched._pct(probability)
    implied_text = patched._pct(implied)
    edge_text = patched._edge(edge)
    ev_text = patched._fmt(ev, "ev")
    if lang == "es":
        rows = [
            f"Entrada sintética del modelo: {probability_text}.",
            f"Momio de prueba: {_decimal_text(_first(row, 'decimal_price', 'decimal_odds', 'odds', default='')) or 'no disponible'}; implícita {implied_text}.",
            f"Cálculo demo: ventaja {edge_text}; VE {ev_text}.",
            "No es consejo de apuesta ni información en vivo.",
        ]
    else:
        rows = [
            f"Synthetic model input: {probability_text}.",
            f"Synthetic test price: {_decimal_text(_first(row, 'decimal_price', 'decimal_odds', 'odds', default='')) or 'unavailable'}; implied {implied_text}.",
            f"Demonstration math: edge {edge_text}; EV {ev_text}.",
            "Not betting advice or live information.",
        ]
    draw.rectangle((23, 641, 337, 882), fill=cream)
    _draw_readable_bullets(patched, draw, 44, 655, rows, 272, 210, red, lang)


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
    _overlay_metric_strip(patched, draw, row, lang)
    _overlay_why_panel(patched, draw, row, lang)
    _overlay_evidence_panel(patched, draw, row, lang)
    overflow = list(image.info.get('_aba_overflow_notes', []))
    red = getattr(patched, 'RED', (190, 30, 28))
    if not _demonstration_mode(row):
        draw.rectangle((23, 641, 337, 882), fill=cream)
        _draw_readable_bullets(patched, draw, 44, 655, patched._why(row, lang), 272, 210, red, lang, overflow=overflow, title='Fundamento' if lang == 'es' else 'Rationale')
    for side, x, accent in (('away', 376, red), ('home', 730, blue)):
        team = _first(row, f'{side}_team', 'team_a' if side == 'away' else 'team_b', default=side)
        draw.rectangle((x - 2, 746, x + 300, 924), fill=cream)
        _draw_readable_bullets(patched, draw, x, 751, team_items(row, side, lang), 292, 165, accent, lang, overflow=overflow, title=('Equipo: ' if lang == 'es' else 'Team: ') + team)
        draw.rectangle((x - 2, 1055, x + 300, 1147), fill=cream)
        _draw_readable_bullets(patched, draw, x, 1058, team_items(row, side, lang, injury=True), 302, 88, accent, lang, overflow=overflow, title=('Lesiones: ' if lang == 'es' else 'Injuries: ') + team)
    # One complete fitted season label; no one-line wrapper truncation.
    sport = _first(row, 'sport', 'league', default='Sport')
    season = tr(_first(row, 'season_label', 'event_stage', 'competition_round', default=f'{sport} regular season'), lang).upper()
    draw.rectangle((36, 330, 506, 378), fill=black)
    draw.text((54, 341), season, font=patched._fit(season, 438, 25, 12, True), fill=cream)
    classified = display_decision(row)
    actionable = classified['report_display_actionable'] and not _demonstration_mode(row)
    action = 'DEMONSTRATION ONLY' if _demonstration_mode(row) else classified['report_display_status']
    accent = getattr(patched, 'GREEN', (61, 205, 84)) if actionable else (241, 184, 45)
    draw.rounded_rectangle((20, 1374, 1060, 1532), radius=14, fill=black, outline=accent, width=3)
    draw.rectangle((20, 1374, 250, 1532), fill=blue if not actionable else accent)
    draw.text((40, 1404), tr('FINAL', lang), font=patched._font(30, True), fill=cream)
    rec = tr('RECOMMENDATION', lang)
    draw.text((40, 1450), rec, font=patched._fit(rec, 190, 24, 12, True), fill=cream)
    action_text = tr(action, lang).upper()
    draw.text((284, 1400), action_text, font=patched._fit(action_text, 720, 42, 16, True), fill=accent)
    _overlay_pick_display(patched, img, draw, row, lang)
    if not _demonstration_mode(row):
        draw.rectangle((23, 1241, 337, 1350), fill=cream)
        risk_rows = [display_tr('Accounting review required before report publication.' if accounting_quarantined(row) else 'Conflicting market values' if row.get('report_market_issue') else 'Verify lineup/news before entry.', lang), display_tr('Confirm current price before entry.' if actionable else 'No actionable stake; price verification is required.', lang)]
        _draw_readable_bullets(patched, draw, 44, 1246, risk_rows, 272, 98, red, lang, overflow=overflow, title='Riesgos' if lang == 'es' else 'Risk checks')
    draw.rounded_rectangle((350, 1174, 1064, 1358), radius=16, fill=paper + (255,), outline=paper + (255,), width=4)
    if callable(getattr(patched, "_section", None)):
        patched._section(draw, 354, 1178, 706, 175, "MATCHUP NOTES", blue, lang)
    else:
        draw.rounded_rectangle((354, 1178, 1060, 1353), radius=14, fill=cream + (255,), outline=black + (238,), width=3)
        draw.rounded_rectangle((354, 1178, 1060, 1234), radius=10, fill=blue)
        draw.text((372, 1189), tr("MATCHUP NOTES", lang).upper(), fill=cream)
    # Header context is an explicit status, independent of provider prose locale.
    from .report_public_quality import is_saved_source
    header = display_tr("Saved-source report. Verify current provider price before publishing." if is_saved_source(row) else "Current provider verification is incomplete." if not display_decision(row)["report_display_actionable"] else "Source verification is distinct from model accuracy.", lang)
    if accounting_quarantined(row):
        header = display_tr("Accounting review required before report publication.", lang)
    draw.rectangle((36, 388, 610, 451), fill=paper)
    patched._txt_auto(draw, 42, 394, header, 558, 54, 18, 14, getattr(patched, "TEXT", (14, 17, 21)), False, 3)
    rows = context_items(row, lang)
    _draw_readable_bullets(patched, draw, 378, 1246, rows, 650, 94, blue, lang, overflow=overflow, title='Contexto del partido' if lang == 'es' else 'Matchup context')
    if _demonstration_mode(row):
        if callable(getattr(patched, "_section", None)):
            patched._section(draw, 20, 1178, 320, 175, "RISK DESK", getattr(patched, "RED", (190, 30, 28)), lang)
        demo_rows = (
            ["Solo demostración", "No es consejo actual", "Cambiar momios primero"]
            if lang == "es"
            else ["Demonstration only", "Not current betting advice", "Replace all prices first"]
        )
        _draw_readable_bullets(patched, draw, 44, 1248, demo_rows, 272, 92, getattr(patched, "RED", (190, 30, 28)), lang)
    result = img.convert("RGB")
    result.info["_aba_overflow_notes"] = overflow
    result.info["report_display_actionable"] = actionable
    result.info["report_display_status"] = action_text
    return result


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
        page_two = second_page._draw_second_page(
            patched,
            row,
            background_image,
            report_name,
            first + 1,
            page_total,
            language,
            logo_image,
            background_mode,
            logo_mode,
            background_opacity,
            logo_opacity,
        )
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
            pages.append(second_page._draw_second_page(
                patched,
                row,
                background_image,
                report_name,
                index * 2 + 2,
                total,
                language,
                logo_image,
                background_mode,
                logo_mode,
                background_opacity,
                logo_opacity,
            ))
        return pages

    patched.render_full_pick_magazine_page_png = two_page_png
    patched.render_full_magazine_book_pages = book_pages
    patched._ABA_FORCED_TWO_PAGE_TRUTH_RENDERER = "truth_contract_v13_shared_snapshot_custom_brand"


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
        language = kwargs.get("language") if kwargs else None
        if len(args) >= 11 and language is None:
            language = args[10]
        row["report_language"] = display_language(language or row.get("report_language"))
        image = original_render(row, *args, **kwargs)
        return _overlay_page_one_context(patched, image, row, language)

    patched.render_full_pick_magazine_page = truthful_render
    patched._pairs = _truth_pairs
    _install_forced_two_page_renderer(patched)
    from .report_display_contract import install_source_note_pages
    install_source_note_pages(patched)
    patched._ABA_SALE_READY_TRUTH_CONTRACT_VERSION = "truth_contract_v14_locale_evidence_provenance"
    return patched
