from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
import json
import re
from typing import Any, Iterable, Mapping

from PIL import Image, ImageDraw

from autonomous_betting_agent.report_public_quality import (
    LIVE_TRIGGER_UNAVAILABLE,
    MISSING_EXACT_MARKET_LINE,
    NO_VERIFIED_PARLAY,
    build_full_market_label,
    has_exact_market_line,
    provider_state,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_items,
    sanitize_public_text,
    to_float,
)

PATCH_VERSION = "direct_second_page_v9_saved_source_wording"
VERIFIED = "VERIFIED CANDIDATE"
WATCHLIST = "WATCHLIST / VERIFY PRICE"
NO_BET = "NO BET / PRICE REJECTED"
MENU_ONLY = "RESEARCH ONLY"
LIVE_TRIGGER = "LIVE TRIGGER WATCH"
PRICE_EXPIRED = "PRICE EXPIRED"
BLOCKED = "BLOCKED"
BAD_SOURCE_TOKENS = ("saved", "uploaded", "cached", "fallback", "manual", "handoff", "uploaded_row")
MARKET_KEYS = ("markets", "available_markets", "odds_markets", "bookmaker_markets", "props", "prop_markets", "live_markets", "alternate_markets")


@dataclass
class MarketCandidate:
    raw_market: str
    normalized_market: str
    selection: str
    full_label: str
    line: str
    decimal_odds: float | None
    provider: str
    sportsbook: str
    timestamp: str
    provider_event_id: str
    is_live: bool
    model_probability: float | None
    implied_probability: float | None
    edge: float | None
    ev: float | None
    fair_odds: float | None
    target_odds: float | None
    badge: str
    rejection_reason: str
    repair_status: str
    correlation_note: str


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "nan", "nat", "n/a", "na", "--"}:
        return ""
    return re.sub(r"\s+", " ", text.replace("−", "-").replace("–", "-").replace("—", "-"))


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


def _get(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = _clean(data.get(key))
        if value:
            return value
    return default


def _num(value: Any) -> float | None:
    return to_float(value)


def _prob(value: Any) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 <= parsed <= 1.0 else None


def _decimal(value: Any) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    if parsed <= -100:
        return 1.0 + 100.0 / abs(parsed)
    if parsed >= 100:
        return 1.0 + parsed / 100.0
    if parsed > 1.0:
        return parsed
    return None


def _odds(value: float | None) -> str:
    return "missing" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def _pct(value: float | None) -> str:
    return "missing" if value is None else f"{value * 100:.0f}%"


def _spct(value: float | None) -> str:
    return "missing" if value is None else f"{value * 100:+.1f}%"


def _ev(value: float | None) -> str:
    return "missing" if value is None else f"{value:+.3f}"


def _parse_markets(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        return [dict(value)]
    text = _clean(value)
    if not text:
        return []
    try:
        loaded = json.loads(text)
    except Exception:
        return []
    if isinstance(loaded, list):
        return [dict(item) for item in loaded if isinstance(item, Mapping)]
    if isinstance(loaded, Mapping):
        return [dict(loaded)]
    return []


def _sport_family(data: Mapping[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower() for k in ("sport", "league", "competition", "event_type", "market_type", "market", "prediction"))
    if any(t in text for t in ("soccer", "football/fifa", "api-football", "fifa", "uefa", "concacaf", "club world")):
        return "soccer"
    if any(t in text for t in ("nba", "wnba", "basketball")):
        return "basketball"
    if any(t in text for t in ("mlb", "baseball")):
        return "baseball"
    if any(t in text for t in ("nfl", "football")):
        return "football"
    if any(t in text for t in ("nhl", "hockey")):
        return "hockey"
    if any(t in text for t in ("tennis", "atp", "wta")):
        return "tennis"
    if any(t in text for t in ("ufc", "mma", "boxing", "fight")):
        return "fight"
    if "golf" in text:
        return "golf"
    return "general"


def _normal_market(raw: str, sport: str = "general") -> str:
    text = raw.lower().replace("_", " ")
    if any(t in text for t in ("team total", "team goals", "team points")):
        return "Team Total"
    if "run line" in text or (sport == "baseball" and any(t in text for t in ("spread", "point spread", "handicap"))):
        return "Run Line"
    if "puck line" in text or (sport == "hockey" and any(t in text for t in ("spread", "point spread", "handicap"))):
        return "Puck Line"
    if any(t in text for t in ("spread", "handicap", "point spread")):
        return "Spread"
    if any(t in text for t in ("total", "over", "under", "o/u")):
        return "Game Total"
    if any(t in text for t in ("moneyline", "winner", "h2h", "match winner")):
        return "Moneyline"
    if any(t in text for t in ("player", "prop", "shots", "strikeout", "assist", "rebound", "touchdown")):
        return "Player Prop"
    return raw.title() if raw else "Primary Market"


def _market_group(name: str) -> str:
    text = name.lower()
    if any(t in text for t in ("live", "next", "flash", "in-play", "in play")):
        return "flash"
    if any(t in text for t in ("player", "prop", "shots", "strikeout", "assist", "rebound", "touchdown", "batter", "pitcher")):
        return "prop"
    if any(t in text for t in ("team total", "total", "spread", "run line", "puck line", "moneyline")):
        return "main"
    return "other"


def _provider(data: Mapping[str, Any]) -> str:
    return _get(data, "provider", "odds_provider", "bookmaker_provider", "source_provider", "data_provider")


def _timestamp(data: Mapping[str, Any]) -> str:
    return _get(data, "timestamp", "odds_timestamp", "last_update", "last_updated", "last_refreshed", "created_at", "snapshot_time")


def _event_id(data: Mapping[str, Any]) -> str:
    return _get(data, "provider_event_id", "event_id", "game_id", "fixture_id", "match_id")


def _repair_status(data: Mapping[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower() for k in ("repair_status", "reparodynamics_status", "drift_status", "data_issue_reason"))
    if any(t in text for t in ("blocked", "observation", "protected")):
        return "protected observation mode"
    if any(t in text for t in ("drift", "repair")):
        return "drift detected in observation mode"
    if any(t in text for t in ("promoted", "validated")):
        return "promoted after validation"
    if any(t in text for t in ("watch", "candidate")):
        return "watch"
    return "stable"


def _source_ok(data: dict[str, Any]) -> bool:
    mode = _get(data, "report_source_mode", "source_mode").lower()
    if public_source_warning(data).startswith("Saved-source"):
        return False
    blob = " ".join(_clean(data.get(k)).lower() for k in ("odds_status", "odds_api_status", "odds_source", "data_source", "odds_api_live", "the_odds_api_live", "odds_verified", "verification_status", "report_truth_severity"))
    if any(t in (mode + " " + blob) for t in BAD_SOURCE_TOKENS):
        return False
    return mode == "current-run" or provider_state(data) == "Provider matched" or any(t in blob for t in ("live", "verified", "true", "yes"))


def _is_live(data: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(data.get(k)).lower() for k in ("is_live", "live", "in_play", "market_type", "status", "odds_status"))
    has_feed = bool(_get(data, "live_clock", "game_clock", "minute", "event_minute", "match_minute")) and bool(_get(data, "live_score", "score", "current_score"))
    return has_feed and any(t in blob for t in ("true", "yes", "live", "inplay", "in-play", "in play"))


def _candidate(item: Mapping[str, Any], parent: dict[str, Any], sport: str) -> MarketCandidate:
    merged = {**parent, **dict(item)}
    raw = _get(item, "market_raw", "raw_market", "market", "market_name", "key", "name", default=_get(parent, "market", "market_type", "prediction", "pick", default="Primary market"))
    selection = _get(item, "selection", "outcome", "side", "pick", "label", default=_get(parent, "prediction", "pick", "selection", default="Selection"))
    line = _get(item, "line", "point", "handicap", "total", "threshold", default=_get(parent, "line", "point", "handicap", "total_line", "spread_line", "run_line"))
    dec = _decimal(_get(item, "decimal_odds", "decimal_price", "price", "odds", "best_price", "american_odds", default=_get(parent, "decimal_price", "odds", "best_price", "american_odds")))
    prob = _prob(_get(item, "model_probability", "probability", "win_probability", default=_get(parent, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability")))
    implied = 1.0 / dec if dec else None
    edge = _prob(_get(item, "edge", "model_market_edge", default=_get(parent, "model_market_edge", "edge")))
    if edge is None and prob is not None and implied is not None:
        edge = prob - implied
    ev_value = _num(_get(item, "ev", "expected_value", "expected_value_per_unit", default=_get(parent, "expected_value_per_unit", "expected_value", "ev")))
    if ev_value is None and prob is not None and dec is not None:
        ev_value = prob * dec - 1.0
    fair = 1.0 / prob if prob and prob > 0 else None
    target = fair + 0.02 if fair else None
    normal = _normal_market(raw, sport)
    if normal in {"Run Line", "Puck Line"}:
        merged["market_type"] = merged["market"] = "run line"
        if line:
            merged["run_line"] = line
    provider = _provider(item) or _provider(parent)
    sportsbook = _get(item, "sportsbook", "bookmaker", default=_get(parent, "sportsbook", "bookmaker"))
    timestamp = _timestamp(item) or _timestamp(parent)
    event_id = _event_id(item) or _event_id(parent)
    live = _is_live(item) or _is_live(parent)
    repair = _repair_status(parent)
    missing = []
    if not provider:
        missing.append("provider match")
    if not sportsbook:
        missing.append("sportsbook")
    if not dec:
        missing.append("current provider price")
    if not timestamp:
        missing.append("fresh timestamp")
    if not has_exact_market_line(merged):
        missing.append("exact market line")
    source_ok = _source_ok(parent)
    value_ok = edge is not None and ev_value is not None and edge > 0 and ev_value > 0
    full_label = build_full_market_label(merged)
    if normal in {"Run Line", "Puck Line"}:
        full_label = full_label.replace("Spread:", "Run Line:")
    badge = WATCHLIST
    reason = ""
    saved_source = public_source_warning(parent).startswith("Saved-source")
    if repair in {"drift detected in observation mode", "protected observation mode"} and "blocked" in _clean(parent.get("data_issue_reason")).lower():
        badge, reason = BLOCKED, "Reparodynamics remains in protected observation mode"
    elif not source_ok:
        badge, reason = WATCHLIST, "Saved-source only - current provider match required" if saved_source else "Current provider match required before verified status"
    elif missing:
        badge = MENU_ONLY
        reason = "Missing " + ", ".join(missing)
    elif not value_ok:
        badge, reason = NO_BET, "Requires positive edge and EV"
    else:
        badge = VERIFIED
    if live and badge == WATCHLIST and _market_group(normal) == "flash":
        badge, reason = LIVE_TRIGGER, reason or "Requires live trigger confirmation"
    return MarketCandidate(raw, normal, selection, full_label, line, dec, provider, sportsbook, timestamp, event_id, live, prob, implied, edge, ev_value, fair, target, badge, reason, repair, "same-event/correlation check required")


def discover_markets(pick: Any) -> tuple[list[MarketCandidate], dict[str, Any]]:
    data = _row(pick)
    sport = _sport_family(data)
    items: list[dict[str, Any]] = []
    for key in MARKET_KEYS:
        items.extend(_parse_markets(data.get(key)))
    items.insert(0, {"market": _get(data, "market", "market_type", "prediction", "pick", default="Primary market"), "selection": _get(data, "prediction", "pick", "selection", default="Selection")})
    candidates = [_candidate(item, data, sport) for item in items]
    seen = set(); unique = []
    for c in candidates:
        key = (c.normalized_market, c.full_label.lower(), c.line.lower(), _odds(c.decimal_odds))
        if key not in seen:
            unique.append(c); seen.add(key)
    unique.sort(key=lambda c: ({VERIFIED: 0, LIVE_TRIGGER: 1, WATCHLIST: 2, MENU_ONLY: 3, NO_BET: 4, PRICE_EXPIRED: 5, BLOCKED: 6}.get(c.badge, 9), -(c.ev or -99), -(c.edge or -99)))
    rejected = [c for c in unique if c.badge != VERIFIED]
    diag = {"sport": sport, "provider_called": _provider(data) or "unknown", "provider_state": provider_state(data), "markets_discovered": len(unique), "markets_rejected": len(rejected), "rejection_reasons": sorted({c.rejection_reason for c in rejected if c.rejection_reason})[:4], "timestamp": _timestamp(data) or "missing", "source_priority_used": _get(data, "source_priority_used", "odds_source", "data_source", default="unknown"), "cached_handoff_live_status": _get(data, "report_source_mode", "source_mode", "report_source", default="unknown"), "repair_status": _repair_status(data)}
    return unique, diag


def advanced_market_diagnostics(pick: Any) -> dict[str, Any]:
    markets, diag = discover_markets(pick)
    diag["markets"] = [asdict(m) for m in markets[:20]]
    return diag


def _source_status(data: dict[str, Any], lang: str) -> tuple[str, tuple[int, int, int]]:
    markets, _diag = discover_markets(data)
    if any(m.badge == VERIFIED for m in markets):
        return _tr("VERIFIED CANDIDATE", lang), GREEN
    if any(m.badge == BLOCKED for m in markets):
        return _tr("Verification pending", lang), GOLD
    return _tr("Verification pending", lang), GOLD


def _line(m: MarketCandidate, lang: str) -> str:
    parts = [m.badge, m.full_label or f"{m.normalized_market}: {m.selection}"]
    if m.decimal_odds:
        parts.append(f"price {_odds(m.decimal_odds)}")
    parts += [f"P {_pct(m.model_probability)}", f"edge {_spct(m.edge)}", f"EV {_ev(m.ev)}"]
    if m.rejection_reason and m.badge != VERIFIED:
        parts.append(m.rejection_reason)
    return _tr(" · ".join(parts), lang)


def _sport_menu(sport: str) -> list[str]:
    menus = {"soccer": ["Research only · qualify, next goal, cards, corners, throw-ins, free kicks require exact provider market.", "Live trigger unavailable — no matched live feed."], "basketball": ["Research only · player props, team totals, quarters/halves require exact provider market.", "Live trigger unavailable — no matched live feed."], "baseball": ["Research only · F5, NRFI/YRFI, pitcher props, batter props require exact provider market.", "Live trigger unavailable — no matched live feed."], "football": ["Research only · player yards/TDs/receptions, team totals, next score require exact provider market.", "Live trigger unavailable — no matched live feed."], "tennis": ["Research only · set winner, total games, handicap, next game require exact provider market.", "Live trigger unavailable — no matched live feed."], "hockey": ["Research only · puck line, team totals, shots, saves, periods require exact provider market.", "Live trigger unavailable — no matched live feed."], "fight": ["Research only · moneyline, method, round, round total require exact provider market."], "golf": ["Research only · matchup, placement, round score, top 5/10/20 require exact provider market."]}
    return menus.get(sport, ["Research only · side, total, team/player prop, and live trigger only if provider returns exact market."])


def _independent_pair(markets: list[MarketCandidate]) -> list[MarketCandidate]:
    verified = [m for m in markets if m.badge == VERIFIED and m.edge is not None and m.ev is not None and m.edge > 0 and m.ev > 0]
    for first in verified:
        for second in verified:
            if first is second:
                continue
            if first.provider_event_id and second.provider_event_id and first.provider_event_id == second.provider_event_id:
                continue
            if first.full_label == second.full_label:
                continue
            return [first, second]
    return []


def _page_two_sections(data: dict[str, Any], lang: str) -> list[tuple[str, list[str], tuple[int, int, int]]]:
    markets, diag = discover_markets(data)
    verified = [m for m in markets if m.badge == VERIFIED]
    live = [m for m in markets if m.badge == LIVE_TRIGGER and m.is_live]
    saved_source = public_source_warning(data).startswith("Saved-source")
    main_rows = [_line(m, lang) for m in markets[:5]] or [_tr(r, lang) for r in _sport_menu(diag["sport"])]
    if len(main_rows) < 3:
        main_rows += [_tr(r, lang) for r in _sport_menu(diag["sport"])]
    pair = _independent_pair(markets)
    if len(pair) == 2:
        parlay = [f"VERIFIED CANDIDATE · 2-leg candidate: {pair[0].full_label} + {pair[1].full_label}.", f"Leg 1 · {pair[0].full_label} · price {_odds(pair[0].decimal_odds)} · edge {_spct(pair[0].edge)} · EV {_ev(pair[0].ev)}.", f"Leg 2 · {pair[1].full_label} · price {_odds(pair[1].decimal_odds)} · edge {_spct(pair[1].edge)} · EV {_ev(pair[1].ev)}."]
    else:
        parlay = [NO_VERIFIED_PARLAY]
    flash = [_line(m, lang) for m in live[:5]] or [LIVE_TRIGGER_UNAVAILABLE]
    repair = [f"Status: {diag['repair_status']}.", "Reparodynamics remains in protected observation mode unless validation promotes the market.", "Live recommendation changes remain disabled."]
    quality = ["Verification pending" if not verified else "Provider matched", "Current provider match required", "Fresh provider timestamp required", "Exact provider market line required", "Live mutation disabled"]
    if saved_source:
        diag_rows = ["Source type: Saved-source report", "Current provider match: Not verified", "Timestamp: Saved-row timestamp", "Verification status: Source saved"]
    else:
        diag_rows = [f"Source type: {public_source_warning(data)}", f"Provider: {diag['provider_called']}", f"Timestamp: {diag['timestamp']}", f"Verification status: {diag['provider_state']}"]
    cancel = ["Cancel if source cannot match the same event.", "Cancel if price moves below fair value or target.", "Cancel if market, line, or selection differs from provider row.", "Cancel if news, lineup, weather, tempo, or pressure contradicts the trigger."]
    anchor_label = build_full_market_label(data)
    anchor = [f"Primary read: {anchor_label}.", "Page one remains the straight-bet anchor.", f"Source: {public_source_warning(data)}", "Status: " + (verified[0].badge if verified else public_recommendation_status(data))]
    return [("Primary Anchor", sanitize_public_items([_tr(x, lang) for x in anchor[:4]]), RED), ("Advanced Market Board", sanitize_public_items(main_rows[:5]), BLUE), ("Parlay Builder", sanitize_public_items([_tr(x, lang) for x in parlay[:5]]), BLUE), ("Flash Triggers", sanitize_public_items([_tr(x, lang) for x in flash[:5]]), GOLD), ("Reparodynamics Repair", sanitize_public_items([_tr(x, lang) for x in repair]), BLUE), ("Quality Gate", sanitize_public_items([_tr(x, lang) for x in quality]), RED), ("Source Diagnostics", sanitize_public_items([_tr(x, lang) for x in diag_rows]), BLUE), ("Cancel Conditions", sanitize_public_items([_tr(x, lang) for x in cancel]), RED)]


def _final_status(data: dict[str, Any], lang: str) -> tuple[str, str, tuple[int, int, int]]:
    markets, _diag = discover_markets(data)
    verified = [m for m in markets if m.badge == VERIFIED]
    if verified:
        m = verified[0]
        return _tr("ADVANCED MARKETS ACTIVE", lang), _tr(f"Best advanced market: {m.full_label} · price {_odds(m.decimal_odds)} · edge {_spct(m.edge)} · EV {_ev(m.ev)}.", lang), GREEN
    live = next((m for m in markets if m.badge == LIVE_TRIGGER), None)
    if live:
        return _tr("ADVANCED MARKETS NEED VERIFICATION", lang), _tr(f"Best live watch: {live.full_label}. Verify trigger, price, and timestamp first.", lang), GOLD
    return _tr("NO VERIFIED ADVANCED MARKET", lang), _tr("No verified advanced market yet. Straight-bet anchor only until provider/live data confirms an additional market.", lang), GOLD


def _png(image: Any) -> bytes:
    out = BytesIO(); image.save(out, format="PNG", optimize=True); return out.getvalue()


def _maybe_image(value: Any) -> Image.Image | None:
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    if isinstance(value, bytes):
        try:
            return Image.open(BytesIO(value)).convert("RGB")
        except Exception:
            return None
    return None


def _draw_second_page(patched: Any, pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 2, total_pages: int = 2, language: str | None = None) -> Image.Image:
    data = _row(pick)
    lang = patched._lang(data, language) if hasattr(patched, "_lang") else ("es" if str(language or data.get("report_language") or "").lower().startswith("es") else "en")
    W, H = patched.W, patched.H
    img = Image.new("RGB", (W, H), patched.PAPER)
    draw = ImageDraw.Draw(img)
    bg = _maybe_image(background_image)
    if bg is not None:
        bg = bg.resize((W, H))
        try:
            img.blend(bg, img, 0.08)
        except Exception:
            pass
    def tr(text: str) -> str:
        return _tr(text, lang)
    def font(size: int, bold: bool = False):
        return patched._font(size, bold)
    draw.rectangle((18, 18, W - 18, H - 18), outline=patched.RED, width=6)
    draw.rectangle((28, 28, 330, 88), fill=patched.RED)
    draw.text((45, 43), tr("ABA SIGNAL PRO"), font=font(30, True), fill=patched.CREAM)
    draw.rectangle((330, 28, W - 210, 88), fill=patched.BLACK)
    draw.text((360, 43), tr("ADVANCED MARKET ANALYSIS"), font=font(29, True), fill=patched.CREAM)
    draw.rounded_rectangle((W - 195, 30, W - 28, 82), radius=6, fill=patched.CREAM, outline=patched.BLACK, width=2)
    draw.text((W - 174, 45), tr(f"PAGE {page_number} OF {total_pages}"), font=font(20, True), fill=patched.BLACK)
    event = patched._event(data) if hasattr(patched, "_event") else _get(data, "event", "matchup", default="Event")
    draw.text((45, 120), patched._ellipsize_to_width(draw, tr(event).upper(), font(30, True), 760), font=font(30, True), fill=patched.RED)
    market_label = build_full_market_label(data)
    draw.text((45, 180), patched._ellipsize_to_width(draw, tr(market_label).upper(), font(34, True), 760), font=font(34, True), fill=patched.BLUE)
    status, color = _source_status(data, lang)
    draw.rounded_rectangle((W - 360, 120, W - 60, 235), radius=12, fill=patched.BLACK, outline=patched.GOLD, width=3)
    draw.text((W - 340, 145), status, font=font(24, True), fill=patched.GOLD)
    draw.text((W - 340, 190), f"PRICE {_odds(_decimal(_get(data, 'decimal_price', 'odds', 'best_price')))}", font=font(28, True), fill=patched.CREAM)
    draw.rounded_rectangle((45, 265, W - 45, 335), radius=10, fill=patched.GOLD, outline=patched.BLACK, width=2)
    draw.text((70, 287), tr("Page 2 uses only exact source-returned markets. Provider match, exact market line, current price, and timestamp are required."), font=font(14, True), fill=patched.BLACK)
    sections = _page_two_sections(data, lang)
    boxes = [(45, 365, 575, 620), (600, 365, W - 45, 620), (45, 640, 575, 900), (600, 640, W - 45, 900), (45, 925, 575, 1200), (600, 925, W - 45, 1200), (45, 1225, 575, 1490), (600, 1225, W - 45, 1490)]
    for (title, rows, header_color), box in zip(sections, boxes):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill=patched.CREAM, outline=patched.BLACK, width=3)
        draw.rounded_rectangle((x1, y1, x2, y1 + 55), radius=10, fill=header_color)
        draw.text((x1 + 16, y1 + 14), tr(title).upper(), font=font(22, True), fill=patched.CREAM)
        y = y1 + 78
        bullet_color = patched.GREEN if header_color == patched.BLUE else patched.RED
        for row in rows[:4]:
            if y > y2 - 28:
                break
            clean = sanitize_public_text(row)
            draw.ellipse((x1 + 18, y + 6, x1 + 29, y + 17), fill=bullet_color if not clean.lower().startswith(("research only", "live trigger unavailable", "cancel if news")) else patched.GOLD)
            for line in patched._wrap_text_to_box(draw, clean, font(14), x2 - x1 - 60, 2):
                if y > y2 - 20:
                    break
                draw.text((x1 + 40, y), line, font=font(14), fill=patched.BLACK)
                y += 18
            y += 8
    title, body, final_color = _final_status(data, lang)
    draw.rounded_rectangle((45, 1515, W - 45, 1665), radius=12, fill=patched.BLACK, outline=patched.GOLD, width=3)
    draw.text((75, 1545), title, font=font(34, True), fill=final_color)
    y = 1600
    for line in patched._wrap_text_to_box(draw, body, font(22), W - 150, 3):
        draw.text((75, y), line, font=font(22), fill=patched.CREAM)
        y += 28
    draw.rectangle((28, H - 58, W - 28, H - 18), fill=patched.BLACK)
    draw.text((45, H - 48), tr("No guarantees. Bet responsibly. This analysis is for informational purposes only."), font=font(14), fill=patched.CREAM)
    return img


def install(module: Any) -> Any:
    if getattr(module, "_ABA_DIRECT_SECOND_PAGE_PATCH", "") == PATCH_VERSION:
        return module
    module._ABA_DIRECT_SECOND_PAGE_PATCH = PATCH_VERSION
    old_png = getattr(module, "render_full_pick_magazine_page_png", None)
    old_pages = getattr(module, "render_full_magazine_book_pages", None)
    def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        first = module.render_full_pick_magazine_page(pick, background_image, report_name, page_number * 2 - 1, max(2, total_pages * 2), logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        second = _draw_second_page(module, pick, background_image, report_name, page_number * 2, max(2, total_pages * 2), language)
        book = Image.new("RGB", (first.width, first.height * 2), module.PAPER)
        book.paste(first.convert("RGB"), (0, 0)); book.paste(second, (0, first.height))
        return _png(book)
    def book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Image.Image]:
        rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
        pages: list[Image.Image] = []
        total = len(rows) * 2
        for index, pick in enumerate(rows):
            pages.append(module.render_full_pick_magazine_page(pick, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
            pages.append(_draw_second_page(module, pick, background_image, report_name, index * 2 + 2, total, language))
        return pages
    module.render_full_pick_magazine_page_png = two_page_png
    module.render_full_magazine_book_pages = book_pages
    return module
