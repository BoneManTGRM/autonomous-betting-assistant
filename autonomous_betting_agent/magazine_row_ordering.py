from __future__ import annotations

from typing import Any, Iterable
import math
import re

SPORT_PRIORITY = {
    "nfl": 10,
    "football": 10,
    "ncaaf": 11,
    "nba": 20,
    "wnba": 21,
    "basketball": 22,
    "ncaab": 23,
    "mlb": 30,
    "baseball": 30,
    "nhl": 40,
    "hockey": 40,
    "soccer": 50,
    "tennis": 60,
    "mma": 70,
    "boxing": 71,
    "golf": 80,
}

STRENGTH_FIELDS = ("aba_strength_score", "strength_score", "signal_strength", "confidence_strength", "model_strength", "weighted_score", "score")
EV_FIELDS = ("expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
EDGE_FIELDS = ("model_market_edge", "no_vig_edge", "edge", "edge_pct")
PROB_FIELDS = ("learned_model_probability", "model_probability_clean", "model_probability", "final_probability", "confidence", "probability")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _num(value: Any, default: float = float("nan")) -> float:
    text = _clean(value).replace("%", "").replace("+", "").replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na", "--"}:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _first_num(row: dict[str, Any], fields: Iterable[str], default: float = float("nan")) -> float:
    for field in fields:
        number = _num(row.get(field), float("nan"))
        if not math.isnan(number):
            if field in EDGE_FIELDS and abs(number) > 1:
                number /= 100.0
            if field in PROB_FIELDS and number > 1:
                number /= 100.0
            return number
    return default


def sport_section(row: dict[str, Any]) -> str:
    raw = _clean(row.get("sport") or row.get("league") or row.get("sport_key") or row.get("competition") or "Other")
    low = raw.lower()
    if "mlb" in low or "baseball" in low:
        return "MLB"
    if "wnba" in low:
        return "WNBA"
    if "nba" in low or "basketball" in low:
        return "NBA"
    if "nhl" in low or "hockey" in low:
        return "NHL"
    if "soccer" in low:
        return "Soccer"
    if "tennis" in low:
        return "Tennis"
    if "mma" in low:
        return "MMA"
    if "golf" in low:
        return "Golf"
    if "nfl" in low or "football" in low:
        return "NFL"
    return raw.title() if raw else "Other"


def _sport_priority(section: str) -> int:
    low = _clean(section).lower()
    for key, priority in SPORT_PRIORITY.items():
        if key in low:
            return priority
    return 999


def _playability_rank(row: dict[str, Any]) -> int:
    text = " ".join(_clean(row.get(key)).lower() for key in ("gate", "value_gate", "official_status_label", "final_decision", "agent_decision", "recommendation", "consumer_action", "report_lane", "report_lane_v2", "price_value_label"))
    if any(token in text for token in ("avoid", "blocked", "no play", "negative", "expired")):
        return 2
    if any(token in text for token in ("watch", "verify", "research", "test")):
        return 1
    if any(token in text for token in ("play", "playable", "official", "value", "green")):
        return 0
    ev = _first_num(row, EV_FIELDS, float("nan"))
    edge = _first_num(row, EDGE_FIELDS, float("nan"))
    return 0 if (not math.isnan(ev) and ev > 0) or (not math.isnan(edge) and edge > 0) else 1


def strength_score(row: dict[str, Any]) -> float:
    strength = _first_num(row, STRENGTH_FIELDS, float("nan"))
    ev = _first_num(row, EV_FIELDS, 0.0)
    edge = _first_num(row, EDGE_FIELDS, 0.0)
    probability = _first_num(row, PROB_FIELDS, 0.0)
    base = 0.0 if math.isnan(strength) else (strength / 100.0 if strength > 1 else strength)
    return (ev * 1000.0) + (edge * 500.0) + (base * 25.0) + (probability * 10.0)


def order_magazine_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for original_index, row in enumerate(rows):
        item = dict(row)
        section = sport_section(item)
        item["report_sport_section"] = section
        item["report_strength_score"] = f"{strength_score(item):.6f}"
        item["report_original_index"] = str(original_index)
        prepared.append(item)
    prepared.sort(key=lambda row: (_sport_priority(row.get("report_sport_section", "Other")), _playability_rank(row), -strength_score(row), int(_num(row.get("report_original_index"), 0))))
    current = None
    rank = 0
    for global_rank, row in enumerate(prepared, start=1):
        section = row.get("report_sport_section") or sport_section(row)
        if section != current:
            current = section
            rank = 1
        else:
            rank += 1
        row["report_order_rank"] = str(global_rank)
        row["report_sport_rank"] = str(rank)
        row["report_section_header"] = "1" if rank == 1 else ""
    return prepared
