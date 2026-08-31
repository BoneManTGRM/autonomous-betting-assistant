from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterable, Mapping
import hashlib
import json
import re

from autonomous_betting_agent.report_public_quality import (
    LIVE_TRIGGER_UNAVAILABLE,
    NO_VERIFIED_PARLAY,
    build_full_market_label,
    has_exact_market_line,
    is_manual_verified_input,
    provider_state,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_items,
    sanitize_public_text,
)

PATCH_VERSION = "direct_second_page_v11_shared_snapshot_custom_brand"
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

PARLAY_PLAYABLE = "PLAYABLE"
PARLAY_WATCHLIST = "WATCHLIST"
PARLAY_AVOID = "AVOID"
PARLAY_BLOCKED = "BLOCKED"
STRAIGHT_ANCHOR_ONLY = "STRAIGHT ANCHOR ONLY"
BEST_PARLAY_FOUND = "BEST PARLAY FOUND"
NO_VERIFIED_PARLAY_AVAILABLE = "NO VERIFIED PARLAY AVAILABLE"
SPORTSBOOK_RETURNED_PARLAY_PRICE = "SPORTSBOOK_RETURNED_PARLAY_PRICE"
SYNTHETIC_PRODUCT_PRICE = "SYNTHETIC_PRODUCT_PRICE"
UNPRICED_PARLAY = "UNPRICED_PARLAY"

ES = {
    "ADVANCED MARKET ANALYSIS": "ANÁLISIS AVANZADO DE MERCADO",
    "PARLAY RECOMMENDATION BOARD": "TABLERO DE RECOMENDACIONES PARLAY",
    "BEST PARLAY FOUND": "MEJOR PARLAY ENCONTRADO",
    "WATCHLIST PARLAY ONLY": "PARLAY SOLO EN SEGUIMIENTO",
    "STRAIGHT ANCHOR ONLY": "SOLO ANCLA DIRECTA",
    "NO VERIFIED PARLAY AVAILABLE": "SIN PARLAY VERIFICADO DISPONIBLE",
    "PAGE": "PÁGINA",
    "OF": "DE",
    "PRICE": "CUOTA",
    "Primary Anchor": "Ancla principal",
    "Top Parlay Recommendations": "Mejores recomendaciones parlay",
    "Best 2-Leg Parlays": "Mejores parlays de 2 selecciones",
    "Best 3/4-Leg Parlays": "Mejores parlays de 3/4 selecciones",
    "SGP / Cross / Prop / Live": "SGP / cruzado / prop / en vivo",
    "Parlay Avoid List": "Parlays a evitar",
    "Source Diagnostics": "Diagnóstico de fuente",
    "Cancel Conditions": "Condiciones de cancelación",
    "PLAYABLE": "JUGABLE",
    "WATCHLIST": "SEGUIMIENTO",
    "AVOID": "EVITAR",
    "BLOCKED": "BLOQUEADO",
}

MARKET_KEYS = (
    "advanced_markets", "advanced_market_rows", "market_discovery_rows", "available_markets",
    "provider_markets", "odds_markets", "odds_api_markets", "sportsdataio_markets",
    "sportsgameodds_markets", "sportradar_markets", "live_markets", "prop_markets",
    "player_prop_markets", "markets_json",
)
SOURCE_KEYS = ("provider", "odds_provider", "api_provider", "odds_source", "sportsbook", "bookmaker", "source", "data_source")
BOOK_KEYS = ("sportsbook", "bookmaker", "book", "best_bookmaker")
EVENT_ID_KEYS = ("provider_event_id", "manual_event_id", "event_id", "game_id", "fixture_id", "sportsdataio_event_id", "sdio_event_id", "odds_api_event_id", "api_football_fixture_id")
TIME_KEYS = ("price_timestamp", "odds_timestamp", "captured_at_utc", "provider_timestamp", "timestamp", "last_update", "last_updated", "updated_at", "locked_at_utc")
BAD_SOURCE_TOKENS = ("saved", "handoff", "uploaded", "cached", "fallback", "ledger", "history", "missing")
PROP_MODEL_KEYS = ("model_probability", "probability", "win_probability", "prop_model_probability", "player_prop_probability", "market_model_probability")


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
    event_name: str = ""
    event_start_time: str = ""
    verification_method: str = "automated_provider"
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


@dataclass
class ParlayCandidate:
    rank: int
    parlay_type: str
    legs: list[MarketCandidate]
    combined_decimal_odds: float | None
    combined_probability: float | None
    parlay_implied_probability: float | None
    combined_ev: float | None
    pricing_source: str
    correlation_risk: str
    data_quality: str
    status: str
    reason: str
    cancel_trigger: str
    fair_decimal_odds: float | None = None
    minimum_acceptable_odds: float | None = None
    suggested_stake_units: float = 0.0
    profit_at_suggested_stake: float | None = None
    quoted_book: str = ""
    quoted_timestamp: str = ""
    quote_verification_method: str = ""


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
    replacements = (
        ("Primary anchor", "Ancla principal"), ("price", "cuota"), ("market", "mercado"),
        ("selection", "selección"), ("line", "línea"), ("edge", "ventaja"),
        ("timestamp", "marca de tiempo"), ("provider", "proveedor"), ("requires", "requiere"),
        ("verified", "verificado"), ("rejected", "rechazado"), ("Game Total", "Total del partido"),
        ("Run Line", "Línea de carrera"), ("Spread", "Hándicap"), ("Moneyline", "Ganador"),
        ("Over", "Más de"), ("Under", "Menos de"),
    )
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _lang(data: dict[str, Any], language: str | None = None) -> str:
    text = _clean(language or data.get("report_language") or data.get("language") or data.get("lang")).lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _demonstration_mode(data: Mapping[str, Any]) -> bool:
    if data.get("demonstration_mode") is True:
        return True
    text = " ".join(
        _clean(data.get(key)).lower()
        for key in ("report_title", "report_data_scope", "report_truth_warning", "league")
    )
    return any(token in text for token in ("demonstration", "demo only", "validation fixture"))


def _get(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
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
    checks = (
        ("team_to_qualify", ("qualify", "advance", "classify")), ("next_score", ("next goal", "next score", "next team to score")),
        ("corners", ("corner",)), ("throw_ins", ("throw in", "throw ins")), ("free_kicks", ("free kick",)),
        ("cards", ("card", "yellow", "red")), ("both_teams_to_score", ("both teams", "btts")),
        ("draw_no_bet", ("draw no bet", "dnb")), ("double_chance", ("double chance",)),
        ("team_total", ("team total",)), ("alternate_total", ("alternate total",)),
        ("total", ("total", "over under")), ("spread", ("spread", "handicap", "run line", "puck line")),
        ("moneyline", ("moneyline", "h2h", "match winner", "winner")), ("first_five", ("first five", "f5")),
        ("first_inning", ("nrfi", "yrfi", "first inning")), ("pitcher_strikeouts", ("strikeout", "pitcher k")),
        ("batter_props", ("batter", "total bases", "player hits")),
        ("player_props", ("player", "points", "rebounds", "assists", "pra", "yards", "receptions", "touchdown")),
        ("shots", ("shots", "saves")), ("set_market", ("set ",)),
        ("round_method", ("round", "method", "decision", "finish")), ("placement", ("top ", "placement", "matchup")),
    )
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


def _book(data: Mapping[str, Any]) -> str:
    return _get(data, *BOOK_KEYS)


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
    if is_manual_verified_input(data):
        return True
    mode = _get(data, "report_source_mode", "source_mode").lower()
    if public_source_warning(data).startswith("Saved-source"):
        return False
    blob = " ".join(_clean(data.get(k)).lower() for k in ("odds_status", "odds_api_status", "odds_source", "data_source", "odds_api_live", "the_odds_api_live", "odds_verified", "provider_verified", "verification_status", "report_truth_severity"))
    if any(t in (mode + " " + blob) for t in BAD_SOURCE_TOKENS):
        return False
    return mode == "current-run" or provider_state(data) == "Provider matched" or any(t in blob for t in ("live", "verified", "true", "yes"))


def _is_live(data: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(data.get(k)).lower() for k in ("is_live", "live", "in_play", "market_type", "status", "odds_status", "market_status"))
    has_feed = bool(_get(data, "live_clock", "game_clock", "minute", "event_minute", "match_minute")) and bool(_get(data, "live_score", "score", "current_score"))
    return has_feed and any(t in blob for t in ("true", "yes", "live", "inplay", "in-play", "in play"))


def _line_required(market_name: str) -> bool:
    if market_name in {"moneyline", "draw_no_bet", "double_chance", "team_to_qualify", "both_teams_to_score", "next_score"}:
        return False
    return _market_group(market_name) in {"main", "prop", "flash"}


def _candidate(item: Mapping[str, Any], parent: dict[str, Any], sport: str) -> MarketCandidate:
    merged = {**parent, **dict(item)}
    raw = _get(item, "market_raw", "raw_market", "market", "market_name", "key", "name", default=_get(parent, "market", "market_type", "prediction", "pick", default="Primary market"))
    selection = _get(item, "selection", "outcome", "side", "pick", "label", default=_get(parent, "prediction", "pick", "selection", default="Selection"))
    line = _get(item, "line", "point", "handicap", "total", "threshold", default=_get(parent, "verified_line", "current_line", "provider_line", "line", "point", "handicap", "total_line", "spread_line", "run_line"))
    dec = _decimal(_get(item, "decimal_odds", "decimal_price", "price", "odds", "best_price", "american_odds", default=_get(parent, "verified_price", "decimal_price", "odds", "best_price", "american_odds")))
    normal = _normal_market(raw, sport)
    group = _market_group(normal)
    item_prob = next((_prob(item.get(key)) for key in PROP_MODEL_KEYS if _prob(item.get(key)) is not None), None)
    if group in {"prop", "flash"} or normal in {"player_props", "corners", "throw_ins", "free_kicks", "cards", "next_score"}:
        prob = item_prob
    else:
        prob = item_prob or _prob(_get(parent, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    implied = 1.0 / dec if dec else None
    edge = _prob(_get(item, "edge", "model_market_edge", default=_get(parent, "model_market_edge", "edge")))
    if edge is None and prob is not None and implied is not None:
        edge = prob - implied
    ev_value = _num(_get(item, "ev", "expected_value", "expected_value_per_unit", default=_get(parent, "expected_value_per_unit", "expected_value", "ev")))
    if ev_value is None and prob is not None and dec is not None:
        ev_value = prob * dec - 1.0
    fair = 1.0 / prob if prob and prob > 0 else None
    target = fair + 0.02 if fair else None
    manual_verified = is_manual_verified_input(merged)
    provider = _provider(item) or _provider(parent) or ("Manual operator entry" if manual_verified else "")
    sportsbook = _book(item) or _book(parent)
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
    if _line_required(normal) and not (line or has_exact_market_line(merged)):
        missing.append("exact market line")
    if group in {"prop", "flash"} and prob is None:
        missing.append("prop-specific model probability")
    source_ok = _source_ok(merged)
    value_ok = edge is not None and ev_value is not None and edge > 0 and ev_value > 0
    full_label = build_full_market_label(merged)
    badge = WATCHLIST
    reason = ""
    if repair in {"drift detected in observation mode", "protected observation mode"} and "blocked" in _clean(parent.get("data_issue_reason")).lower():
        badge, reason = BLOCKED, "Reparodynamics remains in protected observation mode"
    elif not source_ok:
        badge, reason = WATCHLIST, "Provider match required before verified status"
    elif missing:
        badge, reason = MENU_ONLY, "Missing " + ", ".join(missing)
    elif not value_ok:
        badge, reason = NO_BET, "Requires positive edge and EV"
    else:
        badge = VERIFIED
    if live and badge == WATCHLIST and group == "flash":
        badge, reason = LIVE_TRIGGER, reason or "Requires live trigger confirmation"
    return MarketCandidate(
        raw_market=raw,
        normalized_market=normal,
        selection=selection,
        full_label=full_label,
        line=line,
        decimal_odds=dec,
        provider=provider,
        sportsbook=sportsbook,
        timestamp=timestamp,
        provider_event_id=event_id,
        event_name=_get(merged, "public_event", "event", "event_name", "matchup", "game", default=event_id),
        event_start_time=_get(merged, "event_start_utc", "start_time", "commence_time", "scheduled_at"),
        verification_method="manual_verified" if manual_verified else "automated_provider",
        is_live=live,
        model_probability=prob,
        implied_probability=implied,
        edge=edge,
        ev=ev_value,
        fair_odds=fair,
        target_odds=target,
        badge=badge,
        rejection_reason=reason,
        repair_status=repair,
        correlation_warning="same-event/correlation check required",
    )


def discover_markets(pick: Any) -> tuple[list[MarketCandidate], dict[str, Any]]:
    data = _row(pick)
    sport = _sport_family(data)
    items: list[dict[str, Any]] = []
    for key in MARKET_KEYS:
        items.extend(_parse_markets(data.get(key)))
    items.insert(0, {"market": _get(data, "market", "market_type", "prediction", "pick", default="Primary market"), "selection": _get(data, "prediction", "pick", "selection", default="Selection")})
    candidates = [_candidate(item, data, sport) for item in items]
    seen = set()
    unique: list[MarketCandidate] = []
    for c in candidates:
        key = (c.normalized_market, c.full_label.lower(), c.line.lower(), _odds(c.decimal_odds))
        if key not in seen:
            unique.append(c)
            seen.add(key)
    unique.sort(key=lambda c: ({VERIFIED: 0, LIVE_TRIGGER: 1, WATCHLIST: 2, MENU_ONLY: 3, NO_BET: 4, PRICE_EXPIRED: 5, BLOCKED: 6}.get(c.badge, 9), -(c.ev or -99), -(c.edge or -99)))
    rejected = [c for c in unique if c.badge != VERIFIED]
    diag = {
        "sport": sport,
        "provider_called": _provider(data) or "unknown",
        "provider_state": provider_state(data),
        "markets_discovered": len(unique),
        "markets_rejected": len(rejected),
        "rejection_reasons": sorted({c.rejection_reason for c in rejected if c.rejection_reason})[:4],
        "timestamp": _timestamp(data) or "missing",
        "source_priority_used": _get(data, "source_priority_used", "odds_source", "data_source", default="unknown"),
        "cached_handoff_live_status": _get(data, "report_source_mode", "source_mode", "report_source", default="unknown"),
        "repair_status": _repair_status(data),
    }
    return unique, diag


def _anchor_market(data: dict[str, Any]) -> MarketCandidate:
    sport = _sport_family(data)
    return _candidate({
        "market": _get(data, "market", "market_type", "prediction", "pick", default="Primary anchor"),
        "selection": _get(data, "prediction", "pick", "selection", default="Selection"),
        "line": _get(data, "verified_line", "current_line", "provider_line", "spread_line", "run_line", "line", "point", "handicap"),
        "decimal_odds": _get(data, "verified_price", "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american"),
    }, data, sport)


def _is_same_event(a: MarketCandidate, b: MarketCandidate) -> bool:
    return bool(a.provider_event_id and b.provider_event_id and a.provider_event_id == b.provider_event_id)


def _quote_leg_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return sorted(_clean(item).lower() for item in value if _clean(item))
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                return _quote_leg_ids(json.loads(text))
            except Exception:
                pass
        return sorted(part.strip().lower() for part in re.split(r"[|;,]", text) if part.strip())
    return []


def _quote_timestamp_is_fresh(value: Any) -> bool:
    text = _clean(value)
    if text.lower() in {"now", "current"}:
        return True
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return False
    parsed = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    return -300 <= age <= 900


def _quote_is_verified(quote: Mapping[str, Any]) -> bool:
    book = _book(quote)
    timestamp = _timestamp(quote)
    if not book or not timestamp or not _quote_timestamp_is_fresh(timestamp):
        return False
    mode = _get(quote, "source_mode", "report_source_mode").lower().replace("-", "_").replace(" ", "_")
    method = _get(quote, "verification_method", "price_verification_method").lower()
    attestation = _get(quote, "manual_attestation", "operator_attestation", "price_attested").lower()
    manual = mode in {"manual_verified", "manually_verified", "manual_verified_input"} and method in {"manual", "operator", "manual_entry", "manual_verified"} and attestation in {"1", "true", "yes", "attested", "confirmed"}
    provider = provider_state(quote) == "Provider matched" or _get(quote, "provider_verified", "odds_verified", "price_verified").lower() in {"1", "true", "yes", "verified", "current", "matched"}
    return manual or provider


def _matching_parlay_quote(legs: list[MarketCandidate], parent: Mapping[str, Any]) -> dict[str, Any] | None:
    leg_ids = sorted(leg.provider_event_id.lower() for leg in legs if leg.provider_event_id)
    leg_keys = sorted(f"{leg.provider_event_id}|{leg.full_label}".lower() for leg in legs)
    raw_quotes = parent.get("parlay_price_quotes") or parent.get("combined_price_quotes") or []
    quotes = _parse_markets(raw_quotes)
    for quote in quotes:
        quote_keys = _quote_leg_ids(quote.get("leg_keys"))
        quote_ids = _quote_leg_ids(quote.get("leg_event_ids") or quote.get("event_ids"))
        exact_match = bool(quote_keys and quote_keys == leg_keys) or bool(quote_ids and quote_ids == leg_ids)
        if exact_match:
            return quote
    return None


def _leg_is_eligible(market: MarketCandidate) -> tuple[bool, str]:
    missing = []
    if not market.provider_event_id:
        missing.append("event_id")
    if not market.provider:
        missing.append("provider")
    if not market.timestamp:
        missing.append("timestamp")
    if not market.decimal_odds:
        missing.append("odds")
    if market.model_probability is None:
        missing.append("model_probability")
    if market.implied_probability is None:
        missing.append("implied_probability")
    if market.ev is None:
        missing.append("EV")
    if _line_required(market.normalized_market) and not market.line:
        missing.append("line")
    if market.badge not in {VERIFIED, LIVE_TRIGGER}:
        return False, market.rejection_reason or market.badge
    if missing:
        return False, "Missing " + ", ".join(missing)
    if market.edge is not None and market.edge <= 0:
        return False, "Edge must be positive"
    if market.ev is not None and market.ev <= 0:
        return False, "EV must be positive"
    return True, "eligible"


def _pricing_source_for(legs: list[MarketCandidate], parent: dict[str, Any]) -> tuple[str, float | None, str, str, str, str]:
    same_game = any(_is_same_event(a, b) for i, a in enumerate(legs) for b in legs[i + 1:])
    quote = _matching_parlay_quote(legs, parent)
    if quote is None and same_game:
        returned = _decimal(_get(parent, "sportsbook_parlay_price", "sgp_decimal_odds", "same_game_parlay_price"))
        if returned:
            quote = {**parent, "decimal_odds": returned}
    if quote is not None:
        returned = _decimal(_get(quote, "decimal_odds", "decimal_price", "price", "provider_parlay_price", "parlay_decimal_odds"))
        if returned and _quote_is_verified(quote):
            method = "manual_verified" if _get(quote, "source_mode").lower().replace("-", "_") in {"manual_verified", "manually_verified", "manual_verified_input"} else "automated_provider"
            return SPORTSBOOK_RETURNED_PARLAY_PRICE, returned, "exact leg-matched sportsbook parlay quote", _book(quote), _timestamp(quote), method
        return UNPRICED_PARLAY, None, "Matched combined quote is missing a current verified book, price, or timestamp.", _book(quote), _timestamp(quote), ""
    if same_game:
        return UNPRICED_PARLAY, None, "Same-game correlation cannot be priced from independent leg multiplication.", "", "", ""
    if all(leg.decimal_odds for leg in legs):
        product = 1.0
        for leg in legs:
            product *= float(leg.decimal_odds or 1.0)
        return SYNTHETIC_PRODUCT_PRICE, product, "independent cross-game price estimate; confirm an exact sportsbook parlay quote", "", "", ""
    return UNPRICED_PARLAY, None, "combined price unavailable", "", "", ""


def _joint_probability(parent: Mapping[str, Any]) -> float | None:
    return _prob(_get(parent, "joint_model_probability", "parlay_model_probability", "sgp_model_probability"))


def _correlation_method(parent: Mapping[str, Any]) -> str:
    return _get(parent, "correlation_method", "joint_probability_method", "parlay_model_method")


def _correlation_for(legs: list[MarketCandidate], pricing_source: str, parent: Mapping[str, Any]) -> tuple[str, str]:
    same_events = sum(1 for i, a in enumerate(legs) for b in legs[i + 1:] if _is_same_event(a, b))
    labels = [leg.full_label.lower() for leg in legs]
    if len(labels) != len(set(labels)):
        return "blocked", "Duplicate market exposure."
    if same_events and pricing_source != SPORTSBOOK_RETURNED_PARLAY_PRICE:
        return "blocked", "Same-game correlation cannot be priced from independent leg multiplication; a sportsbook price and validated joint-probability model are required."
    if same_events and (_joint_probability(parent) is None or not _correlation_method(parent)):
        return "blocked", "Sportsbook SGP price is available, but validated joint probability and correlation method are missing."
    if same_events:
        return "modeled same-game", f"Sportsbook-returned SGP price with {_correlation_method(parent)}."
    return "independent product", "Independent cross-game probability product."


def _combined_probability(legs: list[MarketCandidate], correlation_risk: str, parent: Mapping[str, Any]) -> float | None:
    if correlation_risk == "modeled same-game":
        return _joint_probability(parent)
    prob = 1.0
    for leg in legs:
        if leg.model_probability is None:
            return None
        prob *= float(leg.model_probability)
    if correlation_risk == "blocked":
        return None
    return prob


def _build_parlay(parlay_type: str, legs: list[MarketCandidate], parent: dict[str, Any]) -> ParlayCandidate:
    pricing_source, combined_odds, source_reason, quoted_book, quoted_timestamp, quote_method = _pricing_source_for(legs, parent)
    corr, corr_reason = _correlation_for(legs, pricing_source, parent)
    combined_prob = _combined_probability(legs, corr, parent)
    implied = 1.0 / combined_odds if combined_odds else None
    combined_ev = combined_prob * combined_odds - 1.0 if combined_prob is not None and combined_odds else None
    eligibility = [_leg_is_eligible(leg) for leg in legs]
    bad_reasons = [reason for ok, reason in eligibility if not ok]
    if pricing_source == UNPRICED_PARLAY or corr == "blocked" or bad_reasons:
        status = PARLAY_BLOCKED
    elif combined_ev is None or combined_ev <= 0:
        status = PARLAY_AVOID
    elif pricing_source == SYNTHETIC_PRODUCT_PRICE:
        status = PARLAY_WATCHLIST
    else:
        status = PARLAY_PLAYABLE
    reason = corr_reason if status == PARLAY_BLOCKED else source_reason
    if bad_reasons:
        reason = bad_reasons[0]
    if status == PARLAY_AVOID:
        reason = "Combined EV is not positive."
    fair = (1.0 / combined_prob) if combined_prob and combined_prob > 0 else None
    minimum = (1.02 / combined_prob) if combined_prob and combined_prob > 0 else None
    fraction = 0.0
    if status in {PARLAY_PLAYABLE, PARLAY_WATCHLIST} and combined_odds and combined_prob:
        full_kelly = ((combined_odds * combined_prob) - 1.0) / (combined_odds - 1.0)
        fraction = round(min(0.25, max(0.0, full_kelly * 0.25)), 3)
    profit = round(fraction * (combined_odds - 1.0), 3) if combined_odds and fraction else None
    quality = "manual verified inputs" if any(leg.verification_method == "manual_verified" for leg in legs) else "automated provider inputs"
    if status == PARLAY_WATCHLIST:
        quality += "; exact combined quote required"
    elif status != PARLAY_PLAYABLE:
        quality = "requires review"
    return ParlayCandidate(
        0,
        parlay_type,
        legs,
        combined_odds,
        combined_prob,
        implied,
        combined_ev,
        pricing_source,
        corr,
        quality,
        status,
        reason,
        "Cancel if any leg loses source verification, price, line, timestamp, positive EV, or the quoted minimum price.",
        fair,
        minimum,
        fraction,
        profit,
        quoted_book,
        quoted_timestamp,
        quote_method,
    )


def generate_parlay_candidates(pick: Any) -> tuple[list[ParlayCandidate], dict[str, Any]]:
    data = _row(pick)
    markets, diag = discover_markets(data)
    anchor = _anchor_market(data)
    all_markets = [anchor] + [m for m in markets if m.full_label.lower() != anchor.full_label.lower()]
    eligible = [m for m in all_markets if _leg_is_eligible(m)[0]]
    out: list[ParlayCandidate] = []
    for size, label, limit in ((2, "2-leg", 80), (3, "3-leg", 80)):
        others = [m for m in eligible if m.full_label != anchor.full_label]
        combos: list[list[MarketCandidate]] = []
        if _leg_is_eligible(anchor)[0]:
            def build(start: int, current: list[MarketCandidate]) -> None:
                if len(combos) >= limit:
                    return
                if len(current) == size - 1:
                    combos.append([anchor] + current)
                    return
                for idx in range(start, len(others)):
                    build(idx + 1, current + [others[idx]])
            build(0, [])
        for combo in combos:
            out.append(_build_parlay(label, combo, data))
    for p in list(out):
        same_game = any(_is_same_event(a, b) for i, a in enumerate(p.legs) for b in p.legs[i + 1:])
        if same_game:
            out.append(_build_parlay("same-game parlay", p.legs, data))
        if all(_market_group(leg.normalized_market) == "prop" for leg in p.legs):
            out.append(_build_parlay("prop parlay", p.legs, data))
        if any(_market_group(leg.normalized_market) == "flash" or leg.is_live for leg in p.legs):
            out.append(_build_parlay("live/flash parlay", p.legs, data))
        # Cross-game combinations already exist as the canonical 2-leg/3-leg
        # candidates above. Do not duplicate them under a second label.
    unique: dict[tuple[str, tuple[str, ...]], ParlayCandidate] = {}
    for p in out:
        key = (p.parlay_type, tuple(sorted(leg.full_label for leg in p.legs)))
        if key not in unique or ((p.combined_ev or -99) > (unique[key].combined_ev or -99)):
            unique[key] = p
    ranked = sorted(unique.values(), key=lambda p: ({PARLAY_PLAYABLE: 0, PARLAY_WATCHLIST: 1, PARLAY_AVOID: 2, PARLAY_BLOCKED: 3}.get(p.status, 9), -(p.combined_ev or -99), -(p.combined_probability or 0), -(p.combined_decimal_odds or 0)))
    for i, p in enumerate(ranked, 1):
        p.rank = i
    diag = dict(diag)
    diag["parlay_candidates"] = len(ranked)
    diag["playable_parlays"] = sum(1 for p in ranked if p.status == PARLAY_PLAYABLE)
    diag["watchlist_parlays"] = sum(1 for p in ranked if p.status == PARLAY_WATCHLIST)
    diag["eligible_legs"] = len(eligible)
    return ranked, diag


def _leg_text(leg: MarketCandidate) -> str:
    event = leg.event_name or leg.provider_event_id or "event missing"
    source = "manual" if leg.verification_method == "manual_verified" else leg.provider
    return f"{event} · {leg.full_label or leg.selection} @ {_odds(leg.decimal_odds)} · {leg.sportsbook or 'book missing'} · {source} · {leg.timestamp or 'time missing'}"


def _parlay_line(p: ParlayCandidate, lang: str) -> str:
    legs = " + ".join(_leg_text(leg) for leg in p.legs)
    profit = f"{p.profit_at_suggested_stake * 100:.1f}% bankroll" if p.profit_at_suggested_stake is not None else "N/A"
    text = f"#{p.rank} {p.status} · {p.parlay_type}: {legs} · combined {_odds(p.combined_decimal_odds)} · P {_pct(p.combined_probability)} · implied {_pct(p.parlay_implied_probability)} · EV {_ev(p.combined_ev)} · min {_odds(p.minimum_acceptable_odds)} · quarter-Kelly stake {p.suggested_stake_units * 100:.1f}% bankroll · model profit {profit} · corr {p.correlation_risk} · {p.pricing_source}"
    return _tr(text, lang)


def _short_leg_text(leg: MarketCandidate) -> str:
    event = leg.event_name or leg.provider_event_id or "event missing"
    source = "manual" if leg.verification_method == "manual_verified" else leg.provider or "source missing"
    captured = leg.timestamp or "time missing"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured):
        captured = captured[11:16] + "Z"
    return (
        f"{event}: {leg.full_label or leg.selection} @ {_odds(leg.decimal_odds)} · "
        f"P {_pct(leg.model_probability)} · {leg.sportsbook or 'book missing'} · {source} {captured}"
    )


def _parlay_metrics(p: ParlayCandidate) -> str:
    profit = f"{p.profit_at_suggested_stake * 100:.1f}%" if p.profit_at_suggested_stake is not None else "N/A"
    return (
        f"Combined {_odds(p.combined_decimal_odds)} · P {_pct(p.combined_probability)} · "
        f"implied {_pct(p.parlay_implied_probability)} · EV {_ev(p.combined_ev)} · "
        f"min {_odds(p.minimum_acceptable_odds)} · ¼ Kelly {p.suggested_stake_units * 100:.1f}% bankroll · profit {profit}"
    )


def _parlay_summary(p: ParlayCandidate, lang: str) -> str:
    text = (
        f"#{p.rank} {p.status} · {p.parlay_type} · {_odds(p.combined_decimal_odds)} odds · "
        f"P {_pct(p.combined_probability)} · EV {_ev(p.combined_ev)} · ¼ Kelly {p.suggested_stake_units * 100:.1f}%"
    )
    return _tr(text, lang)


def _parlay_card_rows(p: ParlayCandidate, lang: str) -> list[str]:
    if p.pricing_source == SYNTHETIC_PRODUCT_PRICE:
        pricing = "estimated independent price · exact quote required"
    else:
        quote_time = p.quoted_timestamp
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", quote_time):
            quote_time = quote_time[11:16] + "Z"
        pricing = f"quoted {p.quoted_book or 'book missing'} {quote_time or 'time missing'}"
    rows = [f"#{p.rank} {p.status} · {p.parlay_type} · {pricing}"]
    rows.extend(f"Leg {index}: {_short_leg_text(leg)}" for index, leg in enumerate(p.legs, 1))
    rows.append(_parlay_metrics(p))
    if len(rows) < 5:
        rows.append(f"Correlation: {p.correlation_risk} · cancel below {_odds(p.minimum_acceptable_odds)}")
    return sanitize_public_items([_tr(row, lang) for row in rows[:5]])


def _unique_by_legs(parlays: Iterable[ParlayCandidate]) -> list[ParlayCandidate]:
    unique: list[ParlayCandidate] = []
    seen: set[tuple[str, ...]] = set()
    for parlay in parlays:
        signature = tuple(sorted(f"{leg.provider_event_id}|{leg.full_label}" for leg in parlay.legs))
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(parlay)
    return unique


def _top_by_type(parlays: list[ParlayCandidate], kind: str, n: int) -> list[ParlayCandidate]:
    return [p for p in parlays if kind in p.parlay_type and p.status in {PARLAY_PLAYABLE, PARLAY_WATCHLIST}][:n]


def _page_two_sections(
    data: dict[str, Any],
    lang: str,
    *,
    parlays: list[ParlayCandidate] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> list[tuple[str, list[str], tuple[int, int, int]]]:
    if parlays is None or diagnostics is None:
        parlays, generated_diagnostics = generate_parlay_candidates(data)
        diagnostics = generated_diagnostics
    diag = dict(diagnostics)
    playable = [p for p in parlays if p.status == PARLAY_PLAYABLE]
    watch = [p for p in parlays if p.status == PARLAY_WATCHLIST]
    blocked = [p for p in parlays if p.status in {PARLAY_BLOCKED, PARLAY_AVOID}]
    anchor = _anchor_market(data)
    anchor_rows = [
        f"Primary anchor: {anchor.full_label} at {_odds(anchor.decimal_odds)}.",
        f"Model P {_pct(anchor.model_probability)} · implied {_pct(anchor.implied_probability)} · edge {_spct(anchor.edge)} · EV {_ev(anchor.ev)}.",
        f"Provider: {anchor.provider or 'missing'} · book {anchor.sportsbook or 'missing'} · timestamp {anchor.timestamp or 'missing'}.",
        "Page 1 remains the straight-bet anchor; Page 2 only adds verified parlays.",
    ]
    ranked_unique = _unique_by_legs(playable + watch)
    if ranked_unique:
        top = [_parlay_summary(p, lang) for p in ranked_unique[:4]]
    else:
        top = ["No verified parlay or chain bet qualifies.", f"Eligible legs found: {diag.get('eligible_legs', 0)}. Need at least two source-traceable priced positive-EV legs."]
    best_two = next(iter(_top_by_type(parlays, "2-leg", 1)), None)
    best_three = next(iter(_top_by_type(parlays, "3-leg", 1)), None)
    two = _parlay_card_rows(best_two, lang) if best_two else ["No verified 2-leg parlay found. Reason: only one priced positive-EV leg available or correlation/pricing blocked."]
    three = _parlay_card_rows(best_three, lang) if best_three else ["No verified 3-leg parlay found. Three independently eligible legs were not available."]
    if ranked_unique:
        specialty = [
            "Cross-game chains: independent probability and price products are labeled estimates.",
            "Same-game parlays: require a sportsbook SGP quote plus a validated joint-probability method.",
            "Props: each leg requires its own market-specific model probability and current price.",
            "Live / flash: cancel when the market starts, suspends, expires, or changes price.",
        ]
    else:
        specialty = [
            "STRAIGHT ANCHOR ONLY",
            "No SGP/cross-game/prop/live parlay is playable until provider returns priced eligible legs and correlation is handled.",
        ]
    avoid = [f"Avoid: {p.parlay_type} · {p.reason}" for p in blocked[:5]] or ["Avoid any market with stale odds, line movement against the anchor, missing prop model, unsupported SGP pricing, or expired live window."]
    diag_rows = [
        f"Provider: {diag.get('provider_called', 'unknown')} · state {diag.get('provider_state', 'unknown')}.",
        f"Markets discovered: {diag.get('markets_discovered', 0)} · eligible legs: {diag.get('eligible_legs', 0)}.",
        f"Parlay candidates: {diag.get('parlay_candidates', 0)} · playable {diag.get('playable_parlays', 0)} · watchlist {diag.get('watchlist_parlays', 0)}.",
        f"Timestamp: {diag.get('timestamp', 'missing')} · repair status {diag.get('repair_status', 'stable')}.",
    ]
    cancel = [
        "Cancel if Page 1 line changes or sportsbook line differs from the report line.",
        "Cancel if any leg loses odds, timestamp, provider match, market status, or positive EV.",
        "Cancel if SGP correlation cannot be priced by sportsbook or model.",
        "Cancel if a live/flash window is started, suspended, or expired.",
    ]
    return [
        ("Primary Anchor", sanitize_public_items([_tr(x, lang) for x in anchor_rows]), RED),
        ("Top Parlay Recommendations", sanitize_public_items(top[:5]), BLUE),
        ("Best 2-Leg Parlays", sanitize_public_items([_tr(x, lang) for x in two[:5]]), BLUE),
        ("Best 3-Leg Parlays", sanitize_public_items([_tr(x, lang) for x in three[:5]]), GOLD),
        ("SGP / Cross / Prop / Live", sanitize_public_items([_tr(x, lang) for x in specialty[:5]]), BLUE),
        ("Parlay Avoid List", sanitize_public_items([_tr(x, lang) for x in avoid[:5]]), RED),
        ("Source Diagnostics", sanitize_public_items([_tr(x, lang) for x in diag_rows]), BLUE),
        ("Cancel Conditions", sanitize_public_items([_tr(x, lang) for x in cancel]), RED),
    ]


def _final_detail(parlay: ParlayCandidate, lang: str) -> str:
    legs = " + ".join(f"{leg.selection} @{_odds(leg.decimal_odds)}" for leg in parlay.legs)
    detail = f"{parlay.parlay_type}: {legs} · {_parlay_metrics(parlay)} · corr {parlay.correlation_risk}"
    return _tr(detail, lang)


def _final_status(
    data: dict[str, Any],
    lang: str,
    *,
    parlays: list[ParlayCandidate] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> tuple[str, str, tuple[int, int, int]]:
    if parlays is None or diagnostics is None:
        parlays, generated_diagnostics = generate_parlay_candidates(data)
        diagnostics = generated_diagnostics
    diag = dict(diagnostics)
    playable = next((p for p in parlays if p.status == PARLAY_PLAYABLE), None)
    watch = next((p for p in parlays if p.status == PARLAY_WATCHLIST), None)
    if playable:
        if _demonstration_mode(data):
            return _tr("DEMONSTRATION PARLAY CALCULATION", lang), _final_detail(playable, lang), GOLD
        return _tr(BEST_PARLAY_FOUND, lang), _final_detail(playable, lang), GREEN
    if watch:
        return _tr("WATCHLIST PARLAY ONLY", lang), _final_detail(watch, lang), GOLD
    if diag.get("eligible_legs", 0) <= 1:
        return _tr(STRAIGHT_ANCHOR_ONLY, lang), _tr("No verified parlay available. Straight anchor only until another priced, positive-EV, source-traceable leg exists.", lang), GOLD
    return _tr(NO_VERIFIED_PARLAY_AVAILABLE, lang), _tr("Parlay candidates were blocked by pricing, correlation, EV, stale data, or missing model probability.", lang), GOLD


def advanced_market_diagnostics(pick: Any) -> dict[str, Any]:
    markets, diag = discover_markets(pick)
    parlays, parlay_diag = generate_parlay_candidates(pick)
    diag.update(parlay_diag)
    diag["markets"] = [asdict(m) for m in markets[:30]]
    diag["parlays"] = [asdict(p) for p in parlays[:30]]
    return diag


def build_parlay_report_payload(pick: Any) -> dict[str, Any]:
    """Return the language- and brand-neutral Page 2 facts used by every renderer."""
    data = _row(pick)
    parlays, diagnostics = generate_parlay_candidates(data)
    return {
        "schema_version": "aba_parlay_report_v1",
        "anchor": asdict(_anchor_market(data)),
        "recommendations": [asdict(parlay) for parlay in parlays[:30]],
        "diagnostics": dict(diagnostics),
    }


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _report_brand_name(data: Mapping[str, Any], report_name: str | None = None) -> str:
    return _clean(report_name or _get(data, "report_brand_name", "brand_name", default="ABA SIGNAL PRO")) or "ABA SIGNAL PRO"


def _paint_header_identity(
    module: Any,
    img: Any,
    draw: Any,
    data: Mapping[str, Any],
    report_name: str | None,
    logo_image: Any,
    logo_mode: str,
    logo_opacity: float,
) -> None:
    red = getattr(module, "RED", RED)
    draw.rectangle((28, 24, 308, 74), fill=red)
    logo = None
    if logo_image is not None and str(logo_mode or "header").lower() not in {"none", "off", "disabled"}:
        loader = getattr(module, "_load_image", None)
        if callable(loader):
            logo = loader(logo_image)
    if logo is not None:
        resample = getattr(module, "_resample", lambda: 1)()
        logo.thumbnail((262, 44), resample)
        alpha = logo.getchannel("A") if "A" in logo.getbands() else None
        if alpha is not None:
            alpha = alpha.point(lambda value: int(value * min(1.0, max(0.0, float(logo_opacity)))))
            logo.putalpha(alpha)
        x = 28 + (280 - logo.width) // 2
        y = 24 + (50 - logo.height) // 2
        logo = logo.convert("RGBA")
        img.paste(logo, (x, y), logo)
        return
    brand = _report_brand_name(data, report_name).upper()
    draw.text((43, 29), brand, font=module._fit(brand, 250, 38, 18, True), fill="white")


def _draw_second_page(
    module: Any,
    pick: Any,
    background_image: Any = None,
    report_name: str | None = None,
    page_number: int = 2,
    total_pages: int = 2,
    language: str | None = None,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.9,
    logo_opacity: float = 1.0,
):
    from PIL import ImageDraw
    data = _row(pick)
    lang = _lang(data, language)
    black = getattr(module, "BLACK", BLACK)
    red = getattr(module, "RED", RED)
    blue = getattr(module, "BLUE", BLUE)
    cream = getattr(module, "CREAM", CREAM)
    paper = getattr(module, "PAPER", PAPER)
    seed = int(hashlib.sha256((_get(data, "event", "game", "matchup", "event_name", default="parlay") + "page2v11").encode()).hexdigest()[:8], 16)
    img = module._paper(seed).convert("RGBA")
    if background_image is not None and str(background_mode or "").lower() == "full_page":
        hero = getattr(module, "_hero", None)
        if callable(hero):
            hero(img, background_image, "full_page", background_opacity)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((18, 18, 1062, 82), fill=black)
    _paint_header_identity(module, img, draw, data, report_name, logo_image, logo_mode, logo_opacity)
    title = _tr(_get(data, "page_two_title", "parlay_report_title", default="PARLAY RECOMMENDATION BOARD"), lang).upper()
    draw.text((330, 28), title, font=module._fit(title, 470, 38, 17, True), fill="white")
    page_text = _tr(f"PAGE {page_number} OF {total_pages}", lang)
    draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=cream, outline=black)
    draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 15, True), fill=black)
    away, home = module._teams(data)
    module._txt_auto(draw, 42, 104, f"{away} vs {home}".upper(), 660, 52, 46, 15, red, True, 2)
    module._txt_auto(draw, 42, 162, _tr(build_full_market_label(data).upper(), lang), 650, 42, 32, 12, blue, True, 2)
    page_parlays, page_diagnostics = generate_parlay_candidates(data)
    final_title, final_detail, final_color = _final_status(
        data,
        lang,
        parlays=page_parlays,
        diagnostics=page_diagnostics,
    )
    best_parlay = next((candidate for candidate in page_parlays if candidate.status == PARLAY_PLAYABLE), None) or next((candidate for candidate in page_parlays if candidate.status == PARLAY_WATCHLIST), None)
    price = best_parlay.combined_decimal_odds if best_parlay else _decimal(_get(data, "display_decimal_odds", "verified_price", "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american"))
    price_label = "DEMO PRICE" if _demonstration_mode(data) else ("EST. PRICE" if best_parlay and best_parlay.pricing_source == SYNTHETIC_PRODUCT_PRICE else "PRICE")
    price_text = f"{_tr(price_label, lang)} {_odds(price)}"
    draw.rounded_rectangle((720, 104, 1042, 214), radius=14, fill=black, outline=final_color, width=3)
    draw.text((740, 122), final_title, font=module._fit(final_title, 282, 24, 10, True), fill=final_color)
    draw.text((740, 160), price_text, font=module._fit(price_text, 250, 28, 12, True), fill=cream)
    note = "Parlays use source-traceable priced legs only. SGPs require a book quote plus validated joint probability. Estimated cross-game prices are labeled estimates."
    if _demonstration_mode(data):
        note = "DEMONSTRATION ONLY - not current betting advice. " + note
    draw.rounded_rectangle((42, 232, 1042, 294), radius=12, fill=GOLD + (245,), outline=black, width=2)
    module._txt_auto(draw, 64, 248, _tr(note, lang), 956, 32, 20, 8, black, True, 2)

    def box(x: int, y: int, w: int, h: int, label: str, rows: list[str], color: tuple[int, int, int]):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=paper + (255,), outline=black + (220,), width=3)
        draw.rounded_rectangle((x, y, x + w, y + 46), radius=10, fill=color)
        title2 = _tr(label, lang).upper()
        draw.text((x + 14, y + 8), title2, font=module._fit(title2, w - 28, 23, 9, True), fill=cream)
        cy = y + 55
        for item in rows[:5]:
            if cy > y + h - 20:
                break
            up = item.upper()
            bcolor = GREEN if any(t in up for t in ("PLAYABLE", "BEST PARLAY", "VERIFIED")) else RED if any(t in up for t in ("AVOID", "BLOCK", "NO VERIFIED", "REJECTED")) else GOLD if any(t in up for t in ("WATCH", "STRAIGHT", "ONLY", "MISSING")) else color
            draw.ellipse((x + 14, cy + 5, x + 25, cy + 16), fill=bcolor)
            module._txt_auto(draw, x + 34, cy, _tr(item, lang), w - 48, 32, 11 if h <= 220 else 12, 7, black, False, 2)
            cy += 34

    coords = [(42, 318, 488, 210), (552, 318, 488, 210), (42, 548, 488, 224), (552, 548, 488, 224), (42, 792, 488, 224), (552, 792, 488, 224), (42, 1036, 488, 224), (552, 1036, 488, 224)]
    sections = _page_two_sections(
        data,
        lang,
        parlays=page_parlays,
        diagnostics=page_diagnostics,
    )
    for (title2, rows, color), coord in zip(sections, coords):
        box(*coord, title2, rows, color)
    draw.rounded_rectangle((42, 1288, 1042, 1518), radius=16, fill=black, outline=final_color, width=4)
    draw.text((68, 1310), final_title, font=module._fit(final_title, 914, 36, 14, True), fill=final_color)
    module._txt_auto(draw, 68, 1364, final_detail, 914, 104, 20, 8, cream, False, 3)
    draw.rectangle((20, 1542, 1060, 1581), fill=black)
    module._txt_auto(draw, 42, 1550, getattr(module, "SAFETY_FOOTER", "Informational only."), 890, 20, 15, 8, cream, False, 1)
    return img.convert("RGB")


def install(module: Any | None = None) -> Any:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_DIRECT_SECOND_PAGE_PATCH", "") == PATCH_VERSION:
        return module
    try:
        module.ES.update(ES)
    except Exception:
        pass

    def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        page_total = max(2, int(total_pages or 1) * 2)
        first = max(1, int(page_number or 1) * 2 - 1)
        page_one = module.render_full_pick_magazine_page(pick, background_image, report_name, first, page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        page_two = _draw_second_page(
            module,
            pick,
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
        from PIL import Image
        book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(module, "PAPER", PAPER))
        book.paste(page_one.convert("RGB"), (0, 0))
        book.paste(page_two.convert("RGB"), (0, page_one.height))
        return _png(book)

    def render_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
        total = len(rows) * 2
        pages: list[Any] = []
        for index, row in enumerate(rows):
            pages.append(module.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
            pages.append(_draw_second_page(
                module,
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

    module.render_full_pick_magazine_page_png = two_page_png
    module.render_full_magazine_book_pages = render_pages
    module._ABA_DIRECT_SECOND_PAGE_PATCH = PATCH_VERSION
    if "extensive_parlay_engine" not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{getattr(module, 'MAGAZINE_STYLE_VERSION', 'magazine')}_extensive_parlay_engine"
    return module


install()
