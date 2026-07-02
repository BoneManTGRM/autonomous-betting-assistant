from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any, Iterable, Mapping
import hashlib
import json
import math
import re

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
)

PATCH_VERSION = "direct_second_page_v8_buyer_facing_quality"
GOLD = (241, 184, 45)
GREEN = (61, 205, 84)
RED = (190, 30, 28)
BLUE = (19, 66, 108)
BLACK = (13, 14, 16)
CREAM = (255, 248, 230)
PAPER = (244, 235, 211)

VERIFIED = "VERIFIED CANDIDATE"
WATCHLIST = "WATCHLIST / VERIFY PRICE"
MENU_ONLY = "RESEARCH ONLY"
LIVE_TRIGGER = "LIVE TRIGGER"
NO_BET = "NO BET / PRICE REJECTED"
BLOCKED = "BLOCKED"
PRICE_EXPIRED = "PRICE EXPIRED"

ES = {
    "ADVANCED MARKET ANALYSIS": "ANÁLISIS AVANZADO DE MERCADO",
    "ADVANCED MARKETS ACTIVE": "MERCADOS AVANZADOS ACTIVOS",
    "ADVANCED MARKETS NEED VERIFICATION": "MERCADOS AVANZADOS REQUIEREN VERIFICACIÓN",
    "NO VERIFIED ADVANCED MARKET": "SIN MERCADO AVANZADO VERIFICADO",
    "PAGE": "PÁGINA", "OF": "DE", "PRICE": "CUOTA",
    "VERIFIED CANDIDATE": "CANDIDATO VERIFICADO", "WATCHLIST / VERIFY PRICE": "LISTA / VERIFICAR CUOTA",
    "RESEARCH ONLY": "SOLO INVESTIGACIÓN", "LIVE TRIGGER": "GATILLO EN VIVO",
    "NO BET / PRICE REJECTED": "NO JUGAR / CUOTA RECHAZADA", "BLOCKED": "BLOQUEADO", "PRICE EXPIRED": "CUOTA VENCIDA",
    "Primary Anchor": "Ancla principal", "Advanced Market Board": "Tablero Avanzado",
    "Parlay Builder": "Constructor Parlay", "Flash Triggers": "Gatillos Flash",
    "Reparodynamics Repair": "Reparación Reparodinámica", "Quality Gate": "Filtro de Calidad",
    "Source Diagnostics": "Diagnóstico de Fuente", "Cancel Conditions": "Condiciones de Cancelación",
    "Verification pending": "Verificación pendiente", "Provider match required": "Requiere coincidencia del proveedor",
    "Fresh timestamp required": "Requiere marca de tiempo reciente", "Exact market line required": "Requiere línea exacta",
}

MARKET_KEYS = (
    "advanced_markets", "advanced_market_rows", "market_discovery_rows", "available_markets",
    "provider_markets", "odds_markets", "odds_api_markets", "sportsdataio_markets",
    "sportsgameodds_markets", "sportradar_markets", "live_markets", "prop_markets",
    "player_prop_markets", "markets_json",
)
SOURCE_KEYS = ("provider", "odds_source", "sportsbook", "bookmaker", "source", "data_source")
EVENT_ID_KEYS = ("provider_event_id", "event_id", "game_id", "fixture_id", "sportsdataio_event_id", "sdio_event_id", "odds_api_event_id", "api_football_fixture_id")
TIME_KEYS = ("timestamp", "price_timestamp", "last_update", "last_updated", "updated_at", "commence_time", "locked_at_utc")
BAD_SOURCE_TOKENS = ("saved", "handoff", "uploaded", "cached", "fallback", "ledger", "history", "missing")


@dataclass
class MarketCandidate:
    raw_market: str
    normalized_market: str
    selection: str
    full_label: str = ""
    line: str = ""
    decimal_odds: float | None = None
    provider: str = ""
    sportsbook: str = ""
    timestamp: str = ""
    provider_event_id: str = ""
    is_live: bool = False
    model_probability: float | None = None
    implied_probability: float | None = None
    edge: float | None = None
    ev: float | None = None
    fair_odds: float | None = None
    target_odds: float | None = None
    badge: str = WATCHLIST
    rejection_reason: str = ""
    repair_status: str = "stable"
    correlation_warning: str = "independent check required"


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


def _tr(value: Any, lang: str) -> str:
    text = sanitize_public_text(_clean(value))
    if lang != "es":
        return text
    if text in ES:
        return ES[text]
    replacements = (("Primary read", "Lectura principal"), ("Source", "Fuente"), ("Status", "Estado"), ("Scope", "Alcance"), ("price", "cuota"), ("market", "mercado"), ("selection", "selección"), ("line", "línea"), ("edge", "ventaja"), ("timestamp", "marca de tiempo"), ("provider", "proveedor"), ("requires", "requiere"), ("verified", "verificado"), ("rejected", "rechazado"), ("Game Total", "Total del partido"), ("Run Line", "Línea de carrera"), ("Spread", "Hándicap"), ("Moneyline", "Ganador"), ("Over", "Más de"), ("Under", "Menos de"))
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _lang(data: dict[str, Any], language: str | None = None) -> str:
    text = _clean(language or data.get("report_language") or data.get("language") or data.get("lang")).lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _get(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable"}:
            return text
    return default


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _num(value: Any) -> float | None:
    text = _clean(value).replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _prob(value: Any) -> float | None:
    num = _num(value)
    if num is None:
        return None
    if abs(num) > 1:
        num /= 100.0
    return num if 0 <= num <= 1 else None


def _decimal(value: Any) -> float | None:
    num = _num(value)
    if num is None:
        return None
    if num <= -100:
        num = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        num = 1.0 + num / 100.0
    return num if num > 1 else None


def _pct(num: float | None) -> str:
    return "N/A" if num is None else f"{num:.0%}"


def _spct(num: float | None) -> str:
    return "N/A" if num is None else f"{num:+.1%}"


def _ev(num: float | None) -> str:
    return "N/A" if num is None else f"{num:+.3f}"


def _odds(num: float | None) -> str:
    return "N/A" if num is None else f"{num:.2f}".rstrip("0").rstrip(".")


def _sport_family(data: dict[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower() for k in ("sport", "league", "competition", "event", "event_name", "matchup", "game"))
    if any(t in text for t in ("soccer", "fifa", "uefa", "liga", "world cup", "premier league", "champions league")):
        return "soccer"
    if any(t in text for t in ("basketball", "nba", "wnba", "ncaab")):
        return "basketball"
    if any(t in text for t in ("baseball", "mlb", "kbo", "npb")):
        return "baseball"
    if any(t in text for t in ("nfl", "american football", "ncaaf")):
        return "football"
    if any(t in text for t in ("hockey", "nhl")):
        return "hockey"
    if any(t in text for t in ("tennis", "atp", "wta")):
        return "tennis"
    if any(t in text for t in ("mma", "ufc", "boxing", "fighter")):
        return "fight"
    if any(t in text for t in ("golf", "pga")):
        return "golf"
    return "general"


def _normal_market(raw: str, sport: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", _clean(raw).lower())
    checks = (("team_to_qualify", ("qualify", "advance")), ("next_score", ("next goal", "next score", "next team to score")), ("corners", ("corner",)), ("throw_ins", ("throw in", "throw ins")), ("free_kicks", ("free kick",)), ("cards", ("card", "yellow", "red")), ("both_teams_to_score", ("both teams", "btts")), ("draw_no_bet", ("draw no bet", "dnb")), ("double_chance", ("double chance",)), ("team_total", ("team total",)), ("alternate_total", ("alternate total",)), ("total", ("total", "over under")), ("spread", ("spread", "handicap", "run line", "puck line")), ("moneyline", ("moneyline", "h2h", "match winner", "winner")), ("first_five", ("first five", "f5")), ("first_inning", ("nrfi", "yrfi", "first inning")), ("pitcher_strikeouts", ("strikeout", "pitcher k")), ("batter_props", ("batter", "total bases", "player hits")), ("player_props", ("player", "points", "rebounds", "assists", "pra", "yards", "receptions", "touchdown")), ("shots", ("shots", "saves")), ("set_market", ("set ",)), ("round_method", ("round", "method", "decision", "finish")), ("placement", ("top ", "placement", "matchup")))
    for name, tokens in checks:
        if any(token in text for token in tokens):
            return name
    return text[:42] or "unknown_market"


def _market_group(name: str) -> str:
    if name in {"moneyline", "spread", "total", "team_total", "alternate_total", "double_chance", "draw_no_bet", "both_teams_to_score", "team_to_qualify", "first_five", "first_inning"}:
        return "main"
    if name in {"next_score", "throw_ins", "free_kicks", "corners", "cards"}:
        return "flash"
    return "prop"


def _provider(data: Mapping[str, Any]) -> str:
    return _get(data, *SOURCE_KEYS)


def _event_id(data: Mapping[str, Any]) -> str:
    return _get(data, *EVENT_ID_KEYS)


def _timestamp(data: Mapping[str, Any]) -> str:
    return _get(data, *TIME_KEYS)


def _parse_markets(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(x) if isinstance(x, Mapping) else {"market": _clean(x)} for x in value]
    if isinstance(value, Mapping):
        return _parse_markets(value.get("markets")) if isinstance(value.get("markets"), list) else [dict(value)]
    text = _clean(value)
    if not text:
        return []
    try:
        return _parse_markets(json.loads(text))
    except Exception:
        return [{"market": line} for line in _split(text)]


def _repair_status(data: dict[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower() for k in ("repair_status", "reparodynamics_status", "reparodynamics_market_status", "drift_status", "learning_status", "data_issue_reason"))
    if any(t in text for t in ("blocked", "forbidden", "bad matching")):
        return "protected observation mode"
    if "drift" in text:
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
    badge = WATCHLIST
    reason = ""
    if repair in {"drift detected in observation mode", "protected observation mode"} and "blocked" in _clean(parent.get("data_issue_reason")).lower():
        badge, reason = BLOCKED, "Reparodynamics remains in protected observation mode"
    elif not source_ok:
        badge, reason = WATCHLIST, "Provider match required before verified status"
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
    quality = ["Verification pending" if not verified else "Provider matched", "Provider match required", "Fresh timestamp required", "Exact market line required", "Live mutation disabled"]
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


def _draw_second_page(module: Any, pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 2, total_pages: int = 2, language: str | None = None):
    from PIL import ImageDraw
    data = _row(pick); lang = _lang(data, language)
    black = getattr(module, "BLACK", BLACK); red = getattr(module, "RED", RED); blue = getattr(module, "BLUE", BLUE); cream = getattr(module, "CREAM", CREAM); paper = getattr(module, "PAPER", PAPER)
    seed = int(hashlib.sha256((_get(data, "event", "game", "matchup", "event_name", default="advanced") + "page2v8").encode()).hexdigest()[:8], 16)
    img = module._paper(seed).convert("RGBA"); draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((18, 18, 1062, 82), fill=black); draw.rectangle((28, 24, 308, 74), fill=red)
    draw.text((43, 29), "ABA SIGNAL PRO", font=module._fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
    title = _tr("ADVANCED MARKET ANALYSIS", lang); draw.text((330, 28), title, font=module._fit(title, 470, 38, 18, True), fill="white")
    page_text = _tr(f"PAGE {page_number} OF {total_pages}", lang); draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=cream, outline=black); draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 15, True), fill=black)
    away, home = module._teams(data); module._txt_auto(draw, 42, 104, f"{away} vs {home}".upper(), 660, 58, 52, 16, red, True, 2)
    module._txt_auto(draw, 42, 172, _tr(build_full_market_label(data).upper(), lang), 650, 42, 36, 14, blue, True, 2)
    status, status_color = _source_status(data, lang); final_title, final_detail, final_color = _final_status(data, lang)
    draw.rounded_rectangle((720, 104, 1042, 222), radius=14, fill=black, outline=final_color if final_color == GREEN else status_color, width=3)
    draw.text((740, 122), status, font=module._fit(status, 282, 25, 11, True), fill=final_color if final_color == GREEN else status_color)
    price = _decimal(_get(data, "display_decimal_odds", "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american")); price_text = f"{_tr('PRICE', lang)} {_odds(price)}"
    draw.text((740, 163), price_text, font=module._fit(price_text, 250, 30, 13, True), fill=cream)
    note = "Page 2 uses only exact source-returned markets. Provider match, exact market line, current price, and timestamp are required."
    draw.rounded_rectangle((42, 246, 1042, 312), radius=12, fill=GOLD + (245,), outline=black, width=2); module._txt_auto(draw, 64, 263, _tr(note, lang), 956, 34, 21, 9, black, True, 2)
    def box(x: int, y: int, w: int, h: int, label: str, rows: list[str], color: tuple[int, int, int]):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=paper + (255,), outline=black + (220,), width=3); draw.rounded_rectangle((x, y, x + w, y + 48), radius=10, fill=color)
        title2 = _tr(label, lang).upper(); draw.text((x + 14, y + 9), title2, font=module._fit(title2, w - 28, 25, 10, True), fill=cream)
        cy = y + 58
        for item in rows[:5]:
            if cy > y + h - 22: break
            up = item.upper(); bcolor = GREEN if "VERIFIED" in up or "VERIFICADO" in up else RED if any(t in up for t in ("NO BET", "BLOCK", "REJECTED", "BLOQUE")) else GOLD if any(t in up for t in ("WATCH", "RESEARCH", "TRIGGER", "LISTA", "INVESTIG")) else color
            draw.ellipse((x + 14, cy + 5, x + 25, cy + 16), fill=bcolor); module._txt_auto(draw, x + 34, cy, _tr(item, lang), w - 48, 34, 12 if h <= 220 else 13, 7, black, False, 2); cy += 36
    coords = [(42, 336, 488, 218), (552, 336, 488, 218), (42, 574, 488, 238), (552, 574, 488, 238), (42, 832, 488, 238), (552, 832, 488, 238), (42, 1090, 488, 238), (552, 1090, 488, 238)]
    for (title2, rows, color), coord in zip(_page_two_sections(data, lang), coords): box(*coord, title2, rows, color)
    draw.rounded_rectangle((42, 1352, 1042, 1518), radius=16, fill=black, outline=final_color, width=4); draw.text((68, 1375), final_title, font=module._fit(final_title, 914, 40, 15, True), fill=final_color)
    module._txt_auto(draw, 68, 1432, final_detail, 914, 56, 22, 8, cream, False, 2); draw.rectangle((20, 1542, 1060, 1581), fill=black); module._txt_auto(draw, 42, 1550, getattr(module, "SAFETY_FOOTER", "Informational only."), 890, 20, 15, 8, cream, False, 1)
    return img.convert("RGB")


def install(module: Any | None = None) -> Any:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_DIRECT_SECOND_PAGE_PATCH", "") == PATCH_VERSION:
        return module
    try: module.ES.update(ES)
    except Exception: pass
    def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        page_total = max(2, int(total_pages or 1) * 2); first = max(1, int(page_number or 1) * 2 - 1)
        page_one = module.render_full_pick_magazine_page(pick, background_image, report_name, first, page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        page_two = _draw_second_page(module, pick, background_image, report_name, first + 1, page_total, language)
        from PIL import Image
        book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(module, "PAPER", PAPER)); book.paste(page_one.convert("RGB"), (0, 0)); book.paste(page_two.convert("RGB"), (0, page_one.height)); return _png(book)
    def render_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]; total = len(rows) * 2; pages: list[Any] = []
        for index, row in enumerate(rows):
            pages.append(module.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)); pages.append(_draw_second_page(module, row, background_image, report_name, index * 2 + 2, total, language))
        return pages
    module.render_full_pick_magazine_page_png = two_page_png; module.render_full_magazine_book_pages = render_pages; module._ABA_DIRECT_SECOND_PAGE_PATCH = PATCH_VERSION
    if "buyer_facing_quality" not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")): module.MAGAZINE_STYLE_VERSION = f"{getattr(module, 'MAGAZINE_STYLE_VERSION', 'magazine')}_buyer_facing_quality"
    return module


install()
