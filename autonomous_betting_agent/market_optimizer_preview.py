from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "market_optimizer_preview_v1"
PREVIEW_ONLY = "PREVIEW ONLY"
PLAYABLE_VALUE = "PLAYABLE VALUE"
WATCH_ONLY = "WATCH ONLY"
WAIT_FOR_BETTER_ODDS = "WAIT FOR BETTER ODDS"
NO_PLAY = "NO BET"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
DO_NOT_USE = "DO NOT USE"
FORBIDDEN = "FORBIDDEN"

SUPPORTED_MARKETS = {
    "moneyline",
    "ganador",
    "spread",
    "handicap",
    "total",
    "over_under",
    "team_total",
    "both_teams_to_score",
    "double_chance",
    "draw_no_bet",
    "first_half",
    "second_half",
    "player_prop",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return safe_text(value)


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _text(value).replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if "%" in _text(value) or number > 1.0 and any(key in _text(value).lower() for key in ("prob", "confidence", "edge")):
        return number / 100.0
    return number


def probability(value: Any) -> float | None:
    raw = safe_float(value)
    if raw is None:
        return None
    if raw > 1.0:
        raw = raw / 100.0
    if raw < 0 or raw > 1:
        return None
    return raw


def decimal_odds(row: Mapping[str, Any]) -> float | None:
    for key in ("decimal_odds", "odds_decimal", "best_decimal_odds", "odds"):
        value = safe_float(row.get(key))
        if value and value > 1.0:
            return value
    american = safe_float(row.get("american_odds") or row.get("odds_american"))
    if american is None or american == 0:
        return None
    if american > 0:
        return round(1.0 + american / 100.0, 6)
    return round(1.0 + 100.0 / abs(american), 6)


def implied_probability(dec_odds: float | None) -> float | None:
    if dec_odds is None or dec_odds <= 1:
        return None
    return 1.0 / dec_odds


def market_type(row: Mapping[str, Any]) -> str:
    text = _text(row.get("market_type") or row.get("market") or row.get("bet_type") or row.get("type")).lower().replace(" ", "_").replace("-", "_")
    return text or "unknown"


def event_key(row: Mapping[str, Any]) -> str:
    for key in ("event_id", "event_key", "game_id", "match_id"):
        value = _text(row.get(key))
        if value:
            return value
    event = _text(row.get("event") or row.get("matchup") or row.get("game") or row.get("teams"))
    start = _text(row.get("start_time") or row.get("commence_time") or row.get("date"))
    return stable_hash("event", {"event": event, "start": start}, 16)


def selection(row: Mapping[str, Any]) -> str:
    return _text(row.get("selection") or row.get("pick") or row.get("team") or row.get("outcome"))


def sportsbook(row: Mapping[str, Any]) -> str:
    return _text(row.get("sportsbook") or row.get("book") or row.get("bookmaker") or row.get("site")) or "unknown"


def calibrated_probability(row: Mapping[str, Any]) -> float | None:
    for key in ("calibrated_probability", "calibrated_prob", "model_probability", "model_prob", "confidence", "probability"):
        value = probability(row.get(key))
        if value is not None:
            return value
    return None


def raw_model_probability(row: Mapping[str, Any]) -> float | None:
    for key in ("model_probability", "model_prob", "confidence", "probability"):
        value = probability(row.get(key))
        if value is not None:
            return value
    return None


def fair_odds(prob: float | None) -> float | None:
    if prob is None or prob <= 0:
        return None
    return round(1.0 / prob, 6)


def min_playable_odds(prob: float | None, margin: float = 0.02) -> float | None:
    if prob is None or prob <= margin:
        return None
    return round(1.0 / (prob - margin), 6)


def ev(prob: float | None, dec_odds: float | None) -> float | None:
    if prob is None or dec_odds is None:
        return None
    return round(prob * dec_odds - 1.0, 6)


def odds_band(dec_odds: float | None) -> str:
    if dec_odds is None:
        return "missing"
    if dec_odds < 1.5:
        return "under_1_50"
    if dec_odds < 2.0:
        return "1_50_to_1_99"
    if dec_odds < 3.0:
        return "2_00_to_2_99"
    return "3_00_plus"


def is_stale(row: Mapping[str, Any]) -> bool:
    text = " ".join(_text(row.get(key)).lower() for key in ("stale", "line_status", "market_status", "status", "notes"))
    return "stale" in text or "closed" in text or "suspended" in text


def historical_segment_risk(row: Mapping[str, Any], history_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sport = _text(row.get("sport")).lower()
    league = _text(row.get("league")).lower()
    mtype = market_type(row)
    book = sportsbook(row).lower()
    matches = []
    for hist in history_rows or []:
        if sport and _text(hist.get("sport")).lower() != sport:
            continue
        if league and _text(hist.get("league")).lower() != league:
            continue
        if mtype != "unknown" and market_type(hist) != mtype:
            continue
        if book != "unknown" and sportsbook(hist).lower() != book:
            continue
        matches.append(hist)
    wins = sum(1 for row in matches if _text(row.get("result") or row.get("status")).lower() == "win")
    losses = sum(1 for row in matches if _text(row.get("result") or row.get("status")).lower() == "loss")
    clv_values = [safe_float(row.get("clv") or row.get("closing_line_value")) for row in matches]
    clv_clean = [value for value in clv_values if value is not None]
    roi_values = [safe_float(row.get("roi") or row.get("profit_units") or row.get("unit_profit")) for row in matches]
    roi_clean = [value for value in roi_values if value is not None]
    sample = wins + losses
    win_rate = wins / sample if sample else None
    avg_clv = sum(clv_clean) / len(clv_clean) if clv_clean else None
    profit_sum = sum(roi_clean) if roi_clean else None
    reasons = []
    risk_score = 0.0
    if sample >= 5 and win_rate is not None and win_rate < 0.45:
        risk_score += 0.25
        reasons.append("low historical win rate")
    if avg_clv is not None and avg_clv < 0:
        risk_score += 0.2
        reasons.append("negative CLV segment")
    if profit_sum is not None and profit_sum < 0:
        risk_score += 0.2
        reasons.append("negative historical return")
    return {"sample_size": sample, "win_rate": round(win_rate, 6) if win_rate is not None else None, "avg_clv": round(avg_clv, 6) if avg_clv is not None else None, "profit_sum": round(profit_sum, 6) if profit_sum is not None else None, "segment_risk_score": round(risk_score, 6), "segment_risk_reasons": reasons}


def score_market_row(row: Mapping[str, Any], history_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    dec = decimal_odds(row)
    implied = implied_probability(dec)
    model_prob = raw_model_probability(row)
    cal_prob = calibrated_probability(row)
    selected_prob = cal_prob if cal_prob is not None else model_prob
    raw_edge = round(model_prob - implied, 6) if model_prob is not None and implied is not None else None
    cal_edge = round(selected_prob - implied, 6) if selected_prob is not None and implied is not None else None
    row_ev = ev(selected_prob, dec)
    fair = fair_odds(selected_prob)
    target = min_playable_odds(selected_prob)
    mtype = market_type(row)
    stale = is_stale(row)
    unsupported = mtype not in SUPPORTED_MARKETS
    missing_context = selected_prob is None or dec is None or not selection(row)
    segment = historical_segment_risk(row, history_rows or [])
    blockers: list[str] = []
    if missing_context:
        blockers.append("missing probability, odds, or selection")
    if unsupported:
        blockers.append("unsupported market type")
    if stale:
        blockers.append("stale or unavailable market")
    if row_ev is not None and row_ev <= 0:
        blockers.append("non-positive calibrated EV")
    if target is not None and dec is not None and dec < target:
        blockers.append("price below minimum playable odds")
    if segment["segment_risk_score"] >= 0.4:
        blockers.append("historical segment risk")

    market_quality = 0.0
    if row_ev is not None:
        market_quality += max(min(row_ev, 0.25), -0.25)
    if cal_edge is not None:
        market_quality += max(min(cal_edge, 0.2), -0.2)
    if selected_prob is not None:
        market_quality += min(selected_prob * 0.25, 0.2)
    market_quality -= segment["segment_risk_score"]
    if stale:
        market_quality -= 0.4
    if unsupported:
        market_quality -= 0.2
    if missing_context:
        market_quality -= 0.4
    market_quality = round(market_quality, 6)

    if blockers:
        action = NO_PLAY if any("missing" in item or "unsupported" in item or "stale" in item or "historical" in item for item in blockers) else WAIT_FOR_BETTER_ODDS
    elif row_ev is not None and row_ev >= 0.05 and selected_prob is not None and selected_prob >= 0.52:
        action = PLAYABLE_VALUE
    elif row_ev is not None and row_ev > 0:
        action = WATCH_ONLY
    else:
        action = NO_PLAY

    if action == PLAYABLE_VALUE and selected_prob is not None and selected_prob >= 0.62 and market_quality >= 0.1:
        risk_level = LOW
    elif action in (PLAYABLE_VALUE, WATCH_ONLY) and market_quality >= 0:
        risk_level = MEDIUM
    else:
        risk_level = HIGH

    stake_fraction = 0.0
    if action == PLAYABLE_VALUE and row_ev is not None and dec is not None and dec > 1:
        kelly = row_ev / (dec - 1)
        stake_fraction = max(0.0, min(kelly * 0.25, 0.03))

    return {
        "market_id": stable_hash("market", row, 16),
        "event_id": event_key(row),
        "event": _text(row.get("event") or row.get("matchup") or row.get("game")),
        "sport": _text(row.get("sport")),
        "league": _text(row.get("league")),
        "sportsbook": sportsbook(row),
        "market_type": mtype,
        "selection": selection(row),
        "decimal_odds": dec,
        "implied_probability": round(implied, 6) if implied is not None else None,
        "model_probability": model_prob,
        "calibrated_probability": selected_prob,
        "raw_edge": raw_edge,
        "calibrated_edge": cal_edge,
        "ev": row_ev,
        "fair_odds": fair,
        "minimum_playable_odds": target,
        "needed_odds": target if action == WAIT_FOR_BETTER_ODDS else None,
        "odds_band": odds_band(dec),
        "market_quality_score": market_quality,
        "segment_risk_score": segment["segment_risk_score"],
        "segment_sample_size": segment["sample_size"],
        "segment_risk_reasons": segment["segment_risk_reasons"],
        "stale_line": stale,
        "unsupported_market": unsupported,
        "blockers": blockers,
        "final_action": action,
        "risk_level": risk_level,
        "suggested_stake_fraction": round(stake_fraction, 6),
        "chain_eligible": action == PLAYABLE_VALUE and risk_level in (LOW, MEDIUM),
        "why_value": explain_value(row, selected_prob, dec, row_ev, cal_edge),
        "why_fail": explain_failure(blockers, risk_level, segment),
        "mode": PREVIEW_ONLY,
    }


def explain_value(row: Mapping[str, Any], prob: float | None, dec: float | None, row_ev: float | None, edge: float | None) -> str:
    parts = []
    if row_ev is not None and row_ev > 0:
        parts.append(f"positive EV {row_ev:.3f}")
    if edge is not None and edge > 0:
        parts.append(f"market edge {edge:.3f}")
    if prob is not None and dec is not None:
        parts.append(f"calibrated probability {prob:.3f} vs decimal odds {dec:.3f}")
    return "; ".join(parts) or "No value case confirmed in preview."


def explain_failure(blockers: Sequence[str], risk_level: str, segment: Mapping[str, Any]) -> str:
    parts = list(blockers or [])
    if risk_level == HIGH:
        parts.append("high preview risk")
    for reason in segment.get("segment_risk_reasons") or []:
        parts.append(str(reason))
    return "; ".join(dict.fromkeys(parts)) or "Could fail if model probability is miscalibrated or market price moves against the pick."


def group_best_books(scored_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in scored_rows or []:
        groups[(str(row.get("event_id")), str(row.get("market_type")), str(row.get("selection")))].append(dict(row))
    best = []
    for (event_id, mtype, pick), rows in groups.items():
        ranked = sorted(rows, key=lambda item: (float(item.get("decimal_odds") or 0), float(item.get("market_quality_score") or -999)), reverse=True)
        top = ranked[0]
        best.append({"event_id": event_id, "market_type": mtype, "selection": pick, "best_sportsbook": top.get("sportsbook"), "best_decimal_odds": top.get("decimal_odds"), "book_count": len({row.get("sportsbook") for row in rows}), "market_id": top.get("market_id")})
    return sorted(best, key=lambda row: (str(row.get("event_id")), str(row.get("market_type")), str(row.get("selection"))))


def build_avoid_list(scored_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in scored_rows or []:
        key = (str(row.get("sport") or "unknown"), str(row.get("league") or "unknown"), str(row.get("market_type") or "unknown"), str(row.get("sportsbook") or "unknown"))
        bucket = buckets.setdefault(key, {"sport": key[0], "league": key[1], "market_type": key[2], "sportsbook": key[3], "row_count": 0, "blocked_count": 0, "negative_ev_count": 0, "stale_count": 0, "unsupported_count": 0, "reasons": set()})
        bucket["row_count"] += 1
        if row.get("final_action") == NO_PLAY:
            bucket["blocked_count"] += 1
        if row.get("ev") is not None and float(row.get("ev") or 0) <= 0:
            bucket["negative_ev_count"] += 1
            bucket["reasons"].add("negative or zero EV")
        if row.get("stale_line"):
            bucket["stale_count"] += 1
            bucket["reasons"].add("stale line")
        if row.get("unsupported_market"):
            bucket["unsupported_count"] += 1
            bucket["reasons"].add("unsupported market")
        for blocker in row.get("blockers") or []:
            bucket["reasons"].add(str(blocker))
    output = []
    for bucket in buckets.values():
        row_count = int(bucket["row_count"] or 0)
        blocked_ratio = bucket["blocked_count"] / row_count if row_count else 0
        if blocked_ratio >= 0.5 or bucket["negative_ev_count"] or bucket["stale_count"] or bucket["unsupported_count"]:
            output.append({**{key: value for key, value in bucket.items() if key != "reasons"}, "blocked_ratio": round(blocked_ratio, 6), "avoid_reasons": sorted(bucket["reasons"])})
    return sorted(output, key=lambda row: (row["blocked_ratio"], row["negative_ev_count"], row["stale_count"]), reverse=True)


def chain_preview(scored_rows: Sequence[Mapping[str, Any]], max_legs: int = 3) -> list[dict[str, Any]]:
    eligible = [dict(row) for row in scored_rows or [] if row.get("chain_eligible")]
    chains: list[dict[str, Any]] = []
    for leg_count in (2, 3):
        if leg_count > max_legs:
            continue
        for combo in itertools.combinations(eligible, leg_count):
            event_ids = [str(row.get("event_id")) for row in combo]
            correlated = len(set(event_ids)) != len(event_ids)
            combined_odds = 1.0
            combined_prob = 1.0
            combined_ev: float | None = None
            for row in combo:
                combined_odds *= float(row.get("decimal_odds") or 1.0)
                combined_prob *= float(row.get("calibrated_probability") or 0.0)
            if combined_prob and combined_odds:
                combined_ev = round(combined_prob * combined_odds - 1.0, 6)
            blockers = []
            if correlated:
                blockers.append("correlated event legs")
            if combined_ev is None or combined_ev <= 0:
                blockers.append("non-positive combined EV")
            if any(row.get("risk_level") == HIGH for row in combo):
                blockers.append("high-risk leg")
            if leg_count == 3 and combined_prob < 0.18:
                blockers.append("combined probability too low")
            if blockers:
                risk_class = DO_NOT_USE
            elif leg_count == 2 and combined_prob >= 0.32:
                risk_class = MEDIUM
            elif leg_count == 2:
                risk_class = HIGH
            else:
                risk_class = HIGH
            chains.append({
                "chain_id": stable_hash("chain", combo, 16),
                "leg_count": leg_count,
                "events": event_ids,
                "markets": [row.get("market_type") for row in combo],
                "selections": [row.get("selection") for row in combo],
                "sportsbooks": [row.get("sportsbook") for row in combo],
                "combined_decimal_odds": round(combined_odds, 6),
                "combined_probability": round(combined_prob, 6),
                "combined_ev": combined_ev,
                "risk_class": risk_class,
                "blockers": blockers,
                "final_action": "CHAIN PREVIEW" if not blockers else DO_NOT_USE,
                "mode": PREVIEW_ONLY,
            })
    return sorted(chains, key=lambda row: (row.get("final_action") == "CHAIN PREVIEW", float(row.get("combined_ev") or -999)), reverse=True)[:50]


def marco_mode(scored_rows: Sequence[Mapping[str, Any]], avoid_rows: Sequence[Mapping[str, Any]], chains: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    playable = [row for row in scored_rows if row.get("final_action") == PLAYABLE_VALUE]
    watch = [row for row in scored_rows if row.get("final_action") in (WATCH_ONLY, WAIT_FOR_BETTER_ODDS)]
    return {
        "mode": "MARCO MODE PREVIEW",
        "client_safe": True,
        "best_plays": sanitize_client_rows(playable[:10]),
        "watchlist": sanitize_client_rows(watch[:10]),
        "avoid_list": sanitize_client_rows(avoid_rows[:10]),
        "chain_preview": sanitize_client_rows([row for row in chains if row.get("final_action") == "CHAIN PREVIEW"][:5]),
        "private_diagnostics_included": False,
        "api_keys_included": False,
        "profit_guarantee": False,
    }


def sanitize_client_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    allowed = {
        "event",
        "sport",
        "league",
        "sportsbook",
        "market_type",
        "selection",
        "decimal_odds",
        "calibrated_probability",
        "calibrated_edge",
        "ev",
        "fair_odds",
        "minimum_playable_odds",
        "needed_odds",
        "risk_level",
        "risk_class",
        "final_action",
        "why_value",
        "why_fail",
        "avoid_reasons",
        "combined_decimal_odds",
        "combined_probability",
        "combined_ev",
        "leg_count",
        "selections",
    }
    return [{key: _safe(value) for key, value in dict(row).items() if key in allowed} for row in rows or []]


def build_market_optimizer_preview(
    workspace_id: str | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    bankroll: float | None = None,
) -> dict[str, Any]:
    markets = [dict(row) for row in market_rows or []]
    history = [dict(row) for row in history_rows or []]
    scored = [score_market_row(row, history) for row in markets]
    scored = sorted(scored, key=lambda row: (row.get("final_action") == PLAYABLE_VALUE, float(row.get("ev") or -999), float(row.get("market_quality_score") or -999)), reverse=True)
    best_books = group_best_books(scored)
    avoid = build_avoid_list(scored)
    chains = chain_preview(scored)
    action_counts = Counter(row.get("final_action") for row in scored)
    risk_counts = Counter(row.get("risk_level") for row in scored)
    playable = [row for row in scored if row.get("final_action") == PLAYABLE_VALUE]
    bank = bankroll if bankroll is not None else 1000.0
    for row in scored:
        row["suggested_stake_units"] = round(float(row.get("suggested_stake_fraction") or 0.0) * bank, 6)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "mode": PREVIEW_ONLY,
        "market_row_count": len(markets),
        "history_row_count": len(history),
        "playable_count": action_counts.get(PLAYABLE_VALUE, 0),
        "watch_count": action_counts.get(WATCH_ONLY, 0),
        "wait_count": action_counts.get(WAIT_FOR_BETTER_ODDS, 0),
        "no_play_count": action_counts.get(NO_PLAY, 0),
        "low_risk_count": risk_counts.get(LOW, 0),
        "medium_risk_count": risk_counts.get(MEDIUM, 0),
        "high_risk_count": risk_counts.get(HIGH, 0),
        "best_single": playable[0] if playable else None,
        "market_hunter_rows": scored,
        "best_book_rows": best_books,
        "avoid_list": avoid,
        "chain_builder_rows": chains,
        "marco_mode": marco_mode(scored, avoid, chains),
        "safety_gates": {
            "live_wager_execution": FORBIDDEN,
            "sportsbook_login": FORBIDDEN,
            "money_movement": FORBIDDEN,
            "automatic_proof_mutation": FORBIDDEN,
            "automatic_model_mutation": FORBIDDEN,
            "api_key_exposure": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
    }
    report["optimizer_id"] = stable_hash("market_optimizer", {"workspace_id": workspace_id, "rows": scored}, 24)
    report["optimizer_hash"] = stable_hash("market_optimizer_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_market_optimizer_preview_from_text(workspace_id: str | None = None, market_csv_text: str | None = None, history_csv_text: str | None = None, bankroll: float | None = None) -> dict[str, Any]:
    return build_market_optimizer_preview(workspace_id, parse_csv_text(market_csv_text), parse_csv_text(history_csv_text), bankroll)


def export_market_optimizer_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_market_hunter_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("market_hunter_rows") or [])


def export_best_books_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("best_book_rows") or [])


def export_avoid_list_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("avoid_list") or [])


def export_chain_builder_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("chain_builder_rows") or [])


def export_marco_mode_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("marco_mode") or {}), sort_keys=True, indent=2)


def export_market_optimizer_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "optimizer_id", "optimizer_hash", "generated_at_utc", "market_row_count", "history_row_count", "playable_count", "watch_count", "wait_count", "no_play_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
