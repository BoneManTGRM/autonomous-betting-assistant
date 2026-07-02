from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

MISSING_EXACT_MARKET_LINE = "Missing exact market line"
SAVED_SOURCE_PUBLIC_WARNING = "Saved-source report. Verify current provider price before publishing."
LIVE_TRIGGER_UNAVAILABLE = "Live trigger unavailable - no matched live feed."
NO_VERIFIED_PARLAY = "No verified parlay candidate yet - need at least 2 independent positive-EV legs from current provider data."
DANGLING_ENDINGS = ("where", "where the", "with", "with the", "who are", "because", "and", "but", "the", "of", "in", "against", "expected")
SAVED_SOURCE_TOKENS = ("saved", "uploaded", "cached", "handoff", "fallback", "manual", "uploaded_row")
PROVIDER_TOKENS = ("odds api", "the odds api", "sportsdataio", "sportradar", "api-football", "bookmaker", "draftkings", "fanduel", "betmgm", "caesars", "pinnacle", "consensus")
RAW_PUBLIC_DIAGNOSTIC_PATTERNS = (r"\bendpoint unknown\b", r"\bstatus code unknown\b", r"\brows returned\b\s*:?\s*\d*", r"\braw session key\b", r"\braw source key\b", r"\bUPLOADED_ROW\b")
TEXT_LINE_KEYS = ("verified_market_label", "full_market_label", "public_market_label", "market_label", "final_recommendation_label", "final_label", "trend_label", "display_pick", "exact_bet", "prediction", "pick", "selection", "recommended_action", "consumer_action", "why_pick", "analysis_summary", "reason", "explanation")


def public_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "none", "null", "nan", "nat", "n/a", "na", "--"}:
        return ""
    return re.sub(r"\s+", " ", text)


def first_value(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = public_text(row.get(key))
        if value:
            return value
    return ""


def to_float(value: Any) -> float | None:
    text = public_text(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def probability(value: Any) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 <= parsed <= 1.0 else None


def format_line(value: Any) -> str:
    parsed = to_float(value)
    if parsed is None:
        return public_text(value)
    return f"+{parsed:g}" if parsed > 0 else f"{parsed:g}"


def format_total_line(value: Any) -> str:
    parsed = to_float(value)
    return public_text(value) if parsed is None else f"{parsed:g}"


def normalize_side(value: Any) -> str:
    text = public_text(value)
    lowered = text.lower()
    if re.search(r"\bover\b|^o\s*\d|\bo\d", lowered):
        return "Over"
    if re.search(r"\bunder\b|^u\s*\d|\bu\d", lowered):
        return "Under"
    return text


def _text_blob(row: Mapping[str, Any]) -> str:
    return " | ".join(public_text(row.get(key)) for key in TEXT_LINE_KEYS if public_text(row.get(key)))


def _extract_line_from_text(row: Mapping[str, Any], kind: str) -> str:
    blob = _text_blob(row).replace("−", "-").replace("–", "-").replace("—", "-")
    if not blob:
        return ""
    if kind in {"spread", "run_line"}:
        # Match explicit signed spread/run-line values in strings such as
        # "Point spread: Phoenix Mercury -1.5" or "Run Line: Padres +1.5".
        matches = re.findall(r"(?<![A-Za-z0-9])([+-]\s*\d+(?:\.\d+)?)(?![A-Za-z0-9])", blob)
        if matches:
            return matches[-1].replace(" ", "")
    if kind in {"total", "team_total"}:
        # Only recover totals when the line appears next to Over/Under or total wording.
        patterns = (
            r"\b(?:over|under)\s+(\d+(?:\.\d+)?)\b",
            r"\b(?:total|game total|team total)\D{0,24}(\d+(?:\.\d+)?)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, blob, flags=re.I)
            if match:
                return match.group(1)
    return ""


def market_type(row: Mapping[str, Any]) -> str:
    text = " ".join(public_text(row.get(key)).lower() for key in ("market_type", "market", "market_name", "bet_type", "selection", "pick", "prediction", "side", "outcome", "exact_bet", "final_recommendation_label", "trend_label"))
    if any(token in text for token in ("team total", "team_total", "team goals", "team points")):
        return "team_total"
    if any(token in text for token in ("run line", "run_line")):
        return "run_line"
    if any(token in text for token in ("spread", "handicap", "puck line", "point spread")):
        return "spread"
    if any(token in text for token in ("total", "over", "under", "o/u")):
        return "total"
    if any(token in text for token in ("player", "shots", "strikeout", "home run", "assist", "rebound", "touchdown", "passing", "rushing", "receiving")):
        return "player_prop"
    if any(token in text for token in ("moneyline", "winner", "h2h", "ml")):
        return "moneyline"
    return first_value(row, "market_type", "market", "market_name") or "unknown"


def _selection_text(row: Mapping[str, Any]) -> str:
    return first_value(row, "public_pick", "selection", "pick", "prediction", "side", "outcome", "team", "participant", "exact_bet", "final_recommendation_label")


def _team_text(row: Mapping[str, Any]) -> str:
    selection = _selection_text(row)
    if normalize_side(selection) in {"Over", "Under"}:
        return first_value(row, "team", "selection_team", "participant", "home_team", "away_team")
    cleaned = re.sub(r"\b(?:moneyline|ml|spread|point spread|run line|over|under|game total|total)\b", "", selection, flags=re.I)
    cleaned = re.sub(r"[+\-]?\d+(?:\.\d+)?", "", cleaned).strip(" -:|/")
    return cleaned or first_value(row, "team", "selection_team", "participant", "home_team", "away_team")


def _line_value(row: Mapping[str, Any], kind: str) -> str:
    if kind == "total":
        value = first_value(row, "total_line", "game_total_line", "total", "point", "points", "line", "handicap")
    elif kind == "team_total":
        value = first_value(row, "team_total_line", "total_line", "total", "point", "points", "line", "handicap")
    elif kind == "run_line":
        value = first_value(row, "run_line", "runline", "spread_line", "handicap", "point", "points", "line")
    elif kind == "spread":
        value = first_value(row, "spread_line", "handicap", "point", "points", "line")
    else:
        value = first_value(row, "line", "point", "points", "handicap")
    return value or _extract_line_from_text(row, kind)


def build_full_market_label(row: Mapping[str, Any]) -> str:
    kind = market_type(row)
    side = normalize_side(_selection_text(row))
    team = _team_text(row)
    if kind == "total":
        line = _line_value(row, "total")
        return f"Game Total: {side} {format_total_line(line)}" if side in {"Over", "Under"} and line else f"Game Total: {side} - {MISSING_EXACT_MARKET_LINE}" if side in {"Over", "Under"} else f"Game Total: {MISSING_EXACT_MARKET_LINE}"
    if kind == "team_total":
        line = _line_value(row, "team_total")
        prefix = f"Team Total: {team}".strip()
        return f"{prefix} {side} {format_total_line(line)}".strip() if side in {"Over", "Under"} and line else f"{prefix} {side} - {MISSING_EXACT_MARKET_LINE}".strip() if side in {"Over", "Under"} else f"{prefix}: {MISSING_EXACT_MARKET_LINE}".strip()
    if kind == "run_line":
        line = _line_value(row, "run_line")
        return f"Run Line: {team} {format_line(line)}" if team and line else f"Run Line: {team} - {MISSING_EXACT_MARKET_LINE}" if team else f"Run Line: {MISSING_EXACT_MARKET_LINE}"
    if kind == "spread":
        line = _line_value(row, "spread")
        return f"Spread: {team} {format_line(line)}" if team and line else f"Spread: {team} - {MISSING_EXACT_MARKET_LINE}" if team else f"Spread: {MISSING_EXACT_MARKET_LINE}"
    if kind == "player_prop":
        player = first_value(row, "player", "player_name", "participant") or team
        prop = first_value(row, "prop_name", "stat_type", "market", "market_type")
        line = _line_value(row, "prop")
        return f"Player Prop: {player} {side} {format_total_line(line)} {prop}" if player and prop and side in {"Over", "Under"} and line else f"Player Prop: {player} {prop} - {MISSING_EXACT_MARKET_LINE}" if player and prop else f"Player Prop: {MISSING_EXACT_MARKET_LINE}"
    if kind == "moneyline":
        return f"Moneyline: {team or side or _selection_text(row) or 'Missing selection'}"
    return _selection_text(row) or "Missing market selection"


def has_exact_market_line(row: Mapping[str, Any]) -> bool:
    kind = market_type(row)
    return bool(_line_value(row, kind if kind != "player_prop" else "prop")) if kind in {"total", "team_total", "run_line", "spread", "player_prop"} else True


def is_saved_source(row: Mapping[str, Any]) -> bool:
    text = " ".join(public_text(row.get(key)).lower() for key in ("source_mode", "selected_source_key", "odds_source", "data_source", "source", "source_file", "source_label", "odds_status", "report_source", "report_source_mode"))
    return any(token in text for token in SAVED_SOURCE_TOKENS)


def provider_state(row: Mapping[str, Any]) -> str:
    if is_saved_source(row):
        return "Source saved"
    text = " ".join(public_text(row.get(key)).lower() for key in ("api_match_status", "provider_match_status", "odds_source", "data_source", "source", "provider"))
    if any(token in text for token in ("not matched", "no match", "unmatched", "missing", "saved", "uploaded")):
        return "Provider not matched"
    if any(token in text for token in ("matched exact", "exact market", "provider matched", "odds api", "sportsbook", "bookmaker")) or any(token in text for token in PROVIDER_TOKENS):
        return "Provider matched"
    return "Provider not matched"


def _value_numbers(row: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, float | None]:
    ev = next((to_float(row.get(key)) for key in ("expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "EV", "raw_EV", "two_page_raw_EV") if to_float(row.get(key)) is not None), None)
    edge = next((to_float(row.get(key)) for key in ("model_market_edge", "edge", "raw_edge", "two_page_raw_edge") if to_float(row.get(key)) is not None), None)
    if edge is not None and abs(edge) > 1.0 and abs(edge) <= 100.0:
        edge /= 100.0
    price = next((to_float(row.get(key)) for key in ("decimal_price", "decimal_odds", "best_price", "odds_decimal", "odds_at_pick", "odds") if to_float(row.get(key)) is not None), None)
    prob = next((probability(row.get(key)) for key in ("learned_model_probability", "final_adjusted_probability", "adjusted_model_probability", "model_probability_clean", "model_probability", "probability") if probability(row.get(key)) is not None), None)
    return ev, edge, price, prob


def public_recommendation_status(row: Mapping[str, Any]) -> str:
    ev, edge, price, prob = _value_numbers(row)
    event_status = " ".join(public_text(row.get(key)).lower() for key in ("event_status", "status", "game_status", "odds_freshness_status", "price_status"))
    if any(token in event_status for token in ("started", "in progress", "live", "final", "stale", "expired")):
        return "Blocked / Do not publish as pick"
    if ev is not None and edge is not None and (ev <= 0 or edge <= 0):
        return "No bet / Research only / Price rejected"
    if price is None or prob is None:
        return "Research only - missing independent model probability or current provider price"
    if not has_exact_market_line(row):
        return "Research only - missing exact market line"
    if ev is None or edge is None:
        return "Research only - missing edge or EV"
    if is_saved_source(row) or provider_state(row) != "Provider matched":
        return "Watchlist / Verify price"
    return "Verified candidate / Playable value"


def public_action_label(row: Mapping[str, Any]) -> str:
    status = public_recommendation_status(row).lower()
    if "no bet" in status or "price rejected" in status:
        return "NO BET / PRICE REJECTED"
    if "blocked" in status:
        return "BLOCKED"
    if "research only" in status:
        return "RESEARCH ONLY"
    if "watchlist" in status or "verify price" in status:
        return "WATCHLIST"
    if "verified" in status or "playable" in status:
        return "VERIFIED CANDIDATE"
    return "RESEARCH ONLY"


def trim_complete_sentence(value: Any, fallback: str = "Context available, but summary was shortened for layout.") -> str:
    text = public_text(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip(); lowered = text.rstrip(" .,:;—-").lower()
    if any(lowered.endswith(end) for end in DANGLING_ENDINGS):
        matches = list(re.finditer(r"[.!?](?:\s|$)", text))
        return text[: matches[-1].end()].strip() if matches else fallback
    return text


def sanitize_public_text(value: Any) -> str:
    text = public_text(value)
    if not text:
        return ""
    replacements = ((r"\bGate failed\b", "Verification pending"), (r"\bsource mode saved-handoff\b", "Saved-source verification pending"), (r"\bsaved/uploaded rows cannot become VERIFIED\b", "Provider match required before verified status"), (r"\bReparodynamics blocked\b", "Reparodynamics remains in protected observation mode"), (r"\bno verified parlay\b(?! candidate)", "No verified parlay candidate yet"), (r"\bData unavailable\b", "Verification pending"), (r"\bUPLOADED_ROW\b", "Saved-source verification pending"))
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    for pattern in RAW_PUBLIC_DIAGNOSTIC_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -:;|")
    return trim_complete_sentence(text) if text else ""


def sanitize_public_items(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = sanitize_public_text(item)
        if text and text not in out:
            out.append(text)
    return out


def public_source_warning(row: Mapping[str, Any]) -> str:
    return SAVED_SOURCE_PUBLIC_WARNING if is_saved_source(row) else provider_state(row)


def public_diagnostic_banned_terms() -> tuple[str, ...]:
    return ("Gate failed", "endpoint unknown", "status code unknown", "rows returned", "UPLOADED_ROW")
