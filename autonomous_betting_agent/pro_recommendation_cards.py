from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.market_optimizer_preview import NO_PLAY, PLAYABLE_VALUE, WAIT_FOR_BETTER_ODDS, WATCH_ONLY, safe_float
from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "pro_recommendation_cards_v1"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"
READY = "RECOMMENDATION CARDS READY"
REVIEW = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

CARD_FIELDS = (
    "event",
    "sport",
    "book",
    "best_market",
    "recommended_bet",
    "odds",
    "confidence",
    "edge",
    "profit_score",
    "risk_level",
    "suggested_stake",
    "single_bet_rating",
    "chain_eligible",
    "best_chain_pairing",
    "why_this_bet",
    "why_it_could_fail",
    "final_recommendation",
)

CONTEXT_FIELDS = (
    "form",
    "injuries",
    "recent_performance",
    "head_to_head",
    "home_away",
    "rest_travel",
    "motivation_context",
    "market_movement",
    "public_consensus",
)


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


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


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


def market_rows_from_report(report: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if rows:
        return [dict(row) for row in rows]
    if not isinstance(report, Mapping):
        return []
    return [dict(row) for row in report.get("market_hunter_rows") or [] if isinstance(row, Mapping)]


def chain_rows_from_report(report: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if rows:
        return [dict(row) for row in rows]
    if not isinstance(report, Mapping):
        return []
    return [dict(row) for row in report.get("chain_builder_rows") or [] if isinstance(row, Mapping)]


def context_key(row: Mapping[str, Any]) -> str:
    for key in ("event_id", "event_key", "game_id", "match_id"):
        value = _text(row.get(key))
        if value:
            return value
    return _text(row.get("event") or row.get("matchup") or row.get("game"))


def context_map(context_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {}
    for row in context_rows or []:
        key = context_key(row)
        if key:
            output[key] = dict(row)
    return output


def final_recommendation(action: str) -> str:
    if action == PLAYABLE_VALUE:
        return "BET"
    if action in (WATCH_ONLY, WAIT_FOR_BETTER_ODDS):
        return "WATCH"
    return "AVOID"


def single_rating(row: Mapping[str, Any]) -> str:
    action = _text(row.get("final_action"))
    risk = _text(row.get("risk_level"))
    ev = safe_float(row.get("ev"))
    if action == PLAYABLE_VALUE and risk == "LOW" and ev is not None and ev >= 0.08:
        return "A"
    if action == PLAYABLE_VALUE:
        return "B"
    if action in (WATCH_ONLY, WAIT_FOR_BETTER_ODDS):
        return "C"
    return "D"


def profit_score(row: Mapping[str, Any]) -> float:
    ev = safe_float(row.get("ev")) or 0.0
    edge = safe_float(row.get("calibrated_edge") or row.get("edge")) or 0.0
    prob = safe_float(row.get("calibrated_probability") or row.get("model_probability") or row.get("confidence")) or 0.0
    if prob > 1:
        prob /= 100.0
    risk = _text(row.get("risk_level"))
    risk_penalty = 0.0 if risk == "LOW" else 0.08 if risk == "MEDIUM" else 0.18
    score = ev + edge + (prob * 0.2) - risk_penalty
    return round(score, 6)


def best_chain_pairing(row: Mapping[str, Any], chain_rows: Sequence[Mapping[str, Any]]) -> str:
    event_id = _text(row.get("event_id"))
    selection = _text(row.get("selection"))
    for chain in chain_rows or []:
        text = json.dumps(_safe(chain), sort_keys=True)
        if event_id and event_id in text or selection and selection in text:
            if _text(chain.get("final_action")) == "CHAIN PREVIEW":
                return _text(chain.get("chain_id")) or ", ".join(_safe(chain.get("selections") or []))
    return "None"


def explain_context(ctx: Mapping[str, Any]) -> str:
    parts = []
    for field in CONTEXT_FIELDS:
        value = _text(ctx.get(field))
        if value:
            parts.append(f"{field.replace('_', ' ')}: {value}")
    return "; ".join(parts)


def why_this_bet(row: Mapping[str, Any], ctx: Mapping[str, Any]) -> str:
    pieces = []
    if _text(row.get("why_value")):
        pieces.append(_text(row.get("why_value")))
    if safe_float(row.get("ev")) is not None:
        pieces.append(f"EV {safe_float(row.get('ev')):.3f}")
    if safe_float(row.get("calibrated_edge")) is not None:
        pieces.append(f"edge {safe_float(row.get('calibrated_edge')):.3f}")
    context = explain_context(ctx)
    if context:
        pieces.append(context)
    return "; ".join(pieces) or "No confirmed value case in preview."


def why_it_could_fail(row: Mapping[str, Any], ctx: Mapping[str, Any]) -> str:
    pieces = []
    if _text(row.get("why_fail")):
        pieces.append(_text(row.get("why_fail")))
    blockers = row.get("blockers") or []
    if blockers:
        pieces.append("blockers: " + ", ".join(_text(item) for item in blockers))
    for key in ("injuries", "market_movement", "public_consensus"):
        value = _text(ctx.get(key))
        if value:
            pieces.append(f"{key.replace('_', ' ')} risk: {value}")
    return "; ".join(pieces) or "Could fail if probability is miscalibrated, price moves, or context changes before lock."


def build_recommendation_card(row: Mapping[str, Any], ctx: Mapping[str, Any], chain_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    action = _text(row.get("final_action"))
    card = {
        "event": _text(row.get("event")),
        "sport": _text(row.get("sport")),
        "book": _text(row.get("sportsbook")),
        "best_market": _text(row.get("market_type")),
        "recommended_bet": _text(row.get("selection")),
        "odds": safe_float(row.get("decimal_odds")),
        "confidence": safe_float(row.get("calibrated_probability") or row.get("model_probability")),
        "edge": safe_float(row.get("calibrated_edge") or row.get("edge")),
        "profit_score": profit_score(row),
        "risk_level": _text(row.get("risk_level")),
        "suggested_stake": safe_float(row.get("suggested_stake_units") or row.get("suggested_stake_fraction")),
        "single_bet_rating": single_rating(row),
        "chain_eligible": bool(row.get("chain_eligible")),
        "best_chain_pairing": best_chain_pairing(row, chain_rows),
        "why_this_bet": why_this_bet(row, ctx),
        "why_it_could_fail": why_it_could_fail(row, ctx),
        "final_recommendation": final_recommendation(action),
        "source_action": action,
        "card_id": stable_hash("rec_card", {"row": row, "ctx": ctx}, 18),
        "mode": PREVIEW_ONLY,
    }
    return card


def build_completion_checks(cards: Sequence[Mapping[str, Any]], market_rows: Sequence[Mapping[str, Any]], chain_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    checks.append(check_row("cards_present", "Recommendation cards generated", PASS if cards else FAIL, details=f"cards={len(cards)}"))
    fields = set()
    for card in cards or []:
        fields.update(card.keys())
    for field in CARD_FIELDS:
        checks.append(check_row(f"card_field_{field}", f"Card field present: {field}", PASS if field in fields or not cards else FAIL))
    actions = Counter(_text(card.get("final_recommendation")) for card in cards or [])
    checks.append(check_row("bet_watch_avoid_output", "Bet/Watch/Avoid output available", PASS if any(actions.values()) else FAIL, actual=dict(actions)))
    checks.append(check_row("chain_preview_present", "Chain preview rows available when eligible", PASS if chain_rows else WARN, details=f"chains={len(chain_rows)}"))
    checks.append(check_row("market_rows_present", "Market scanner rows present", PASS if market_rows else FAIL, details=f"markets={len(market_rows)}"))
    checks.append(check_row("preview_only_cards", "Cards remain preview-only", PASS if all(card.get("mode") == PREVIEW_ONLY for card in cards or []) else FAIL))
    return checks


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW
    else:
        status = READY
    return {"cards_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_pro_recommendation_cards(
    workspace_id: str | None = None,
    optimizer_report: Mapping[str, Any] | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
    chain_rows: Sequence[Mapping[str, Any]] | None = None,
    context_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    optimizer = dict(optimizer_report or {})
    markets = market_rows_from_report(optimizer, market_rows)
    chains = chain_rows_from_report(optimizer, chain_rows)
    contexts = context_map(context_rows or [])
    cards = []
    for row in markets:
        key = _text(row.get("event_id")) or _text(row.get("event"))
        cards.append(build_recommendation_card(row, contexts.get(key, {}), chains))
    cards = sorted(cards, key=lambda card: (card.get("final_recommendation") == "BET", safe_float(card.get("profit_score")) or -999), reverse=True)
    checks = build_completion_checks(cards, markets, chains)
    summary = summarize_checks(checks)
    action_counts = Counter(card.get("final_recommendation") for card in cards)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or _text(optimizer.get("workspace_id")) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "card_count": len(cards),
        "bet_count": action_counts.get("BET", 0),
        "watch_count": action_counts.get("WATCH", 0),
        "avoid_count": action_counts.get("AVOID", 0),
        "recommendation_cards": cards,
        "marco_cards": sanitize_marco_cards(cards),
        "completion_checks": checks,
        "safety_gates": {
            "live_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "key_exposure": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["cards_id"] = stable_hash("rec_cards", {"workspace_id": report["workspace_id"], "cards": cards}, 24)
    report["cards_hash"] = stable_hash("rec_cards_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def sanitize_marco_cards(cards: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    allowed = set(CARD_FIELDS) | {"card_id"}
    return [{key: _safe(value) for key, value in card.items() if key in allowed} for card in cards or []]


def build_pro_recommendation_cards_from_text(
    workspace_id: str | None = None,
    optimizer_json_text: str | None = None,
    market_csv_text: str | None = None,
    chain_csv_text: str | None = None,
    context_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_pro_recommendation_cards(
        workspace_id,
        parse_json_object(optimizer_json_text),
        parse_csv_text(market_csv_text),
        parse_csv_text(chain_csv_text),
        parse_csv_text(context_csv_text),
    )


def export_recommendation_cards_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_recommendation_cards_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("recommendation_cards") or [])


def export_marco_cards_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("marco_cards") or []), sort_keys=True, indent=2)


def export_completion_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("completion_checks") or [])


def export_recommendation_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "cards_id", "cards_hash", "generated_at_utc", "cards_status", "card_count", "bet_count", "watch_count", "avoid_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
