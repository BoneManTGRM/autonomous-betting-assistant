from __future__ import annotations

import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "event_match_resolver_v1"
MATCHED = "MATCHED"
LOW_CONFIDENCE = "LOW CONFIDENCE"
NO_MATCH = "NO MATCH"
DUPLICATE_MATCH = "DUPLICATE MATCH"
MANUAL_REVIEW = "MANUAL REVIEW"
STATUS_VALUES = (MATCHED, LOW_CONFIDENCE, NO_MATCH, DUPLICATE_MATCH, MANUAL_REVIEW)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


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


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def parse_json_records(text: str | None) -> list[dict[str, Any]]:
    raw = _text(text)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"parse_error": "invalid_json"}]
    if isinstance(parsed, list):
        return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in parsed]
    if isinstance(parsed, Mapping):
        for key in ("events", "games", "data", "results", "response"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in value]
        return [dict(parsed)]
    return [{"value": parsed}]


def normalize_name(value: Any) -> str:
    text = _lower(value)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def token_set(value: Any) -> set[str]:
    return {token for token in normalize_name(value).split() if token}


def name_similarity(left: Any, right: Any) -> float:
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta = token_set(a)
    tb = token_set(b)
    union = len(ta | tb)
    jaccard = len(ta & tb) / union if union else 0.0
    subset = 1.0 if ta and tb and (ta <= tb or tb <= ta) else 0.0
    return round(max(seq, jaccard, subset), 6)


def parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10] + "T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def minutes_between(left: Any, right: Any) -> float | None:
    a = parse_time(left)
    b = parse_time(right)
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 60.0


def time_score(left: Any, right: Any) -> float:
    minutes = minutes_between(left, right)
    if minutes is None:
        return 0.5
    if minutes <= 15:
        return 1.0
    if minutes <= 60:
        return 0.85
    if minutes <= 180:
        return 0.65
    if minutes <= 720:
        return 0.35
    if minutes <= 1440:
        return 0.15
    return 0.0


def event_name(row: Mapping[str, Any]) -> str:
    for key in ("event", "event_name", "matchup", "name", "title", "Name"):
        if _text(row.get(key)):
            return _text(row.get(key))
    home = _text(row.get("home_team") or row.get("HomeTeam") or row.get("home") or row.get("team_home"))
    away = _text(row.get("away_team") or row.get("AwayTeam") or row.get("away") or row.get("team_away"))
    if home and away:
        return f"{away} vs {home}"
    teams = row.get("teams")
    if isinstance(teams, Sequence) and not isinstance(teams, (str, bytes)):
        return " vs ".join(_text(item) for item in teams if _text(item))
    return ""


def event_time(row: Mapping[str, Any]) -> str:
    for key in ("event_start_utc", "commence_time", "start_time", "date", "DateTime", "Day", "time"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return ""


def sport_value(row: Mapping[str, Any]) -> str:
    return _lower(row.get("sport") or row.get("sport_key") or row.get("league") or row.get("League") or row.get("competition"))


def league_value(row: Mapping[str, Any]) -> str:
    return _lower(row.get("league") or row.get("League") or row.get("competition") or row.get("sport_key"))


def market_value(row: Mapping[str, Any]) -> str:
    return _lower(row.get("market_type") or row.get("market") or row.get("bet_type") or row.get("markets"))


def selection_value(row: Mapping[str, Any]) -> str:
    return _text(row.get("selection") or row.get("pick") or row.get("prediction") or row.get("outcome") or row.get("team") or row.get("player"))


def row_identity(row: Mapping[str, Any], prefix: str) -> str:
    for key in ("proof_id", "id", "event_id", "game_id", "GameID", "match_id", "record_id"):
        if _text(row.get(key)):
            return f"{prefix}:{key}:{_text(row.get(key))}"
    return f"{prefix}:{normalize_name(event_name(row))}|{event_time(row)}"


def score_candidate(locked_row: Mapping[str, Any], provider_event: Mapping[str, Any]) -> dict[str, Any]:
    locked_name = event_name(locked_row)
    provider_name = event_name(provider_event)
    name_score = name_similarity(locked_name, provider_name)
    sport_score = 1.0 if sport_value(locked_row) and sport_value(locked_row) == sport_value(provider_event) else 0.5 if not sport_value(locked_row) or not sport_value(provider_event) else 0.0
    league_score = 1.0 if league_value(locked_row) and league_value(locked_row) == league_value(provider_event) else 0.5 if not league_value(locked_row) or not league_value(provider_event) else 0.0
    market_score = 1.0 if market_value(locked_row) and market_value(locked_row) == market_value(provider_event) else 0.5 if not market_value(locked_row) or not market_value(provider_event) else 0.0
    selection_score = name_similarity(selection_value(locked_row), selection_value(provider_event)) if selection_value(locked_row) and selection_value(provider_event) else 0.5
    t_score = time_score(event_time(locked_row), event_time(provider_event))
    score = (
        name_score * 0.38
        + sport_score * 0.17
        + league_score * 0.10
        + t_score * 0.18
        + market_score * 0.09
        + selection_score * 0.08
    )
    return {
        "provider_event_id": row_identity(provider_event, "provider"),
        "provider_event": provider_name,
        "provider_time": event_time(provider_event),
        "score": round(score, 6),
        "name_score": round(name_score, 6),
        "sport_score": round(sport_score, 6),
        "league_score": round(league_score, 6),
        "time_score": round(t_score, 6),
        "market_score": round(market_score, 6),
        "selection_score": round(selection_score, 6),
        "time_delta_minutes": None if minutes_between(event_time(locked_row), event_time(provider_event)) is None else round(float(minutes_between(event_time(locked_row), event_time(provider_event)) or 0.0), 3),
    }


def resolve_locked_row(
    locked_row: Mapping[str, Any],
    provider_events: Sequence[Mapping[str, Any]],
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
    duplicate_margin: float = 0.03,
) -> dict[str, Any]:
    candidates = sorted((score_candidate(locked_row, event) for event in provider_events or []), key=lambda item: item["score"], reverse=True)
    best = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None
    reasons: list[str] = []
    status = NO_MATCH
    if best is None:
        reasons.append("no provider events supplied")
    elif best["score"] >= match_threshold:
        if second and second["score"] >= match_threshold and (best["score"] - second["score"]) <= duplicate_margin:
            status = DUPLICATE_MATCH
            reasons.append("multiple provider events are within duplicate margin")
        else:
            status = MATCHED
    elif best["score"] >= review_threshold:
        status = LOW_CONFIDENCE
        reasons.append("best score is below match threshold")
    else:
        status = NO_MATCH
        reasons.append("best score is below review threshold")
    if best and best.get("name_score", 0.0) < 0.50:
        status = MANUAL_REVIEW if status != NO_MATCH else status
        reasons.append("event name similarity is weak")
    return {
        "locked_row_id": row_identity(locked_row, "locked"),
        "locked_event": event_name(locked_row),
        "locked_time": event_time(locked_row),
        "status": status,
        "best_score": best.get("score") if best else 0.0,
        "best_provider_event_id": best.get("provider_event_id") if best else "",
        "best_provider_event": best.get("provider_event") if best else "",
        "second_score": second.get("score") if second else 0.0,
        "candidate_count": len(candidates),
        "manual_review_required": status in {LOW_CONFIDENCE, NO_MATCH, DUPLICATE_MATCH, MANUAL_REVIEW},
        "reasons": reasons,
        "top_candidates": candidates[:5],
    }


def build_event_match_report(
    workspace_id: str | None = None,
    locked_rows: Sequence[Mapping[str, Any]] | None = None,
    provider_events: Sequence[Mapping[str, Any]] | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
) -> dict[str, Any]:
    locked = [dict(row) for row in locked_rows or []]
    events = [dict(row) for row in provider_events or []]
    rows = [resolve_locked_row(row, events, match_threshold=match_threshold, review_threshold=review_threshold) for row in locked]
    counts = {status: len([row for row in rows if row["status"] == status]) for status in STATUS_VALUES}
    review_count = len([row for row in rows if row["manual_review_required"]])
    overall_status = MATCHED if locked and review_count == 0 else MANUAL_REVIEW if locked else NO_MATCH
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "status": overall_status,
        "locked_row_count": len(locked),
        "provider_event_count": len(events),
        "matched_count": counts[MATCHED],
        "low_confidence_count": counts[LOW_CONFIDENCE],
        "no_match_count": counts[NO_MATCH],
        "duplicate_match_count": counts[DUPLICATE_MATCH],
        "manual_review_count": review_count,
        "match_threshold": float(match_threshold),
        "review_threshold": float(review_threshold),
        "preview_only": True,
        "proof_rows_changed": 0,
        "match_rows": rows,
        "warnings": ["manual review rows remain"] if review_count else [],
        "errors": [] if locked else ["no locked rows supplied"],
    }


def build_event_match_report_from_text(
    workspace_id: str | None = None,
    locked_csv_text: str | None = None,
    provider_json_text: str | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
) -> dict[str, Any]:
    return build_event_match_report(
        workspace_id,
        parse_csv_text(locked_csv_text),
        parse_json_records(provider_json_text),
        match_threshold=match_threshold,
        review_threshold=review_threshold,
    )


def export_event_match_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)
