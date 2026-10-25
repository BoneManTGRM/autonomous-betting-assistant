"""Ledger separation helpers for local-first ABA proof storage.

These helpers keep official proof, research, quarantine, learning-only, high-confidence,
and client-facing rows separated. Public metrics are allowed only for rows with
minimum timestamp/proof/audit requirements and a valid pre-start lock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

OFFICIAL_LEDGER = "official"
RESEARCH_LEDGER = "research"
ALL_HIGH_CONFIDENCE_LEDGER = "all_high_confidence"
QUARANTINE_LEDGER = "quarantine"
LEARNING_ONLY_LEDGER = "learning_only"
CLIENT_LEDGER = "client"

LEDGER_TYPES = {
    OFFICIAL_LEDGER,
    RESEARCH_LEDGER,
    ALL_HIGH_CONFIDENCE_LEDGER,
    QUARANTINE_LEDGER,
    LEARNING_ONLY_LEDGER,
    CLIENT_LEDGER,
}

_BAD_STATUS = {"fail", "failed", "quarantine", "review", "blocked", "bad"}
_RESEARCH_FLAGS = {"research", "test", "testing", "learning", "learning_only", "backfill"}
_OFFICIAL_FLAGS = {"official", "official_ev", "+ev", "proof", "client"}
_HIGH_CONFIDENCE_FLAGS = {"all_high_confidence", "high_confidence", "high_confidence_test", "b_high_confidence_test"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _lower(value) in {"1", "true", "yes", "y", "official", "locked", "pass", "ok"}


def _first_text(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = _text(row.get(name))
        if value:
            return value
    return ""


def proof_id_value(row: Mapping[str, Any]) -> str:
    return _first_text(row, ("proof_id", "lock_id", "id"))


def locked_at_value(row: Mapping[str, Any]) -> str:
    return _first_text(row, ("locked_at_utc", "lock_time", "prediction_timestamp", "odds_timestamp", "created_at"))


def event_start_value(row: Mapping[str, Any]) -> str:
    return _first_text(
        row,
        (
            "event_start_time",
            "event_start_utc",
            "known_start_utc",
            "commence_time",
            "start",
            "game_start",
            "match_start",
            "scheduled_start",
        ),
    )


def parse_dt(value: Any) -> datetime | None:
    """Parse common timestamp strings into timezone-aware UTC datetimes."""
    raw = _text(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def has_required_proof_fields(row: Mapping[str, Any]) -> bool:
    return bool(proof_id_value(row) and locked_at_value(row) and event_start_value(row))


def is_future_locked(row: Mapping[str, Any]) -> bool:
    locked_at = parse_dt(locked_at_value(row))
    event_start = parse_dt(event_start_value(row))
    if not locked_at or not event_start:
        # Some imported verified ledgers already carry proof_status from the lock stage.
        return _lower(row.get("proof_status")) == "locked_before_start"
    return locked_at < event_start


def has_clean_audit(row: Mapping[str, Any]) -> bool:
    audit_status = _lower(row.get("odds_audit_status") or row.get("audit_status"))
    if audit_status in _BAD_STATUS:
        return False
    ledger_hint = _lower(row.get("ledger_type") or row.get("proof_type") or row.get("row_type"))
    if ledger_hint in {QUARANTINE_LEDGER, "review_only", "review"}:
        return False
    return True


def is_research_or_learning(row: Mapping[str, Any]) -> bool:
    if is_demonstration_row(row):
        return True
    values = {
        _lower(row.get("ledger_type")),
        _lower(row.get("proof_type")),
        _lower(row.get("row_type")),
        _lower(row.get("source_type")),
    }
    if values & _RESEARCH_FLAGS:
        return True
    return _truthy(row.get("research_only")) or _truthy(row.get("learning_only")) or _truthy(row.get("backfill"))


def is_demonstration_row(row: Mapping[str, Any]) -> bool:
    """Recognize explicit fixture metadata, never guess from team/event names."""
    if _truthy(row.get("demonstration_mode")):
        return True
    if any(_lower(row.get(key)) == "demo_ledger" for key in ("source_file", "active_list_id", "ledger_batch_id")):
        return True
    if any(_lower(row.get(key)) in {"synthetic_fixture", "synthetic_test_fixture", "validation_fixture", "demonstration_fixture"}
           for key in ("source_mode", "report_source_mode", "report_source")):
        return True
    text = " ".join(_lower(row.get(key)) for key in ("report_title", "report_data_scope", "report_truth_warning", "league"))
    return any(token in text for token in ("demonstration", "demo only", "validation fixture", "synthetic test"))


def has_high_confidence_hint(row: Mapping[str, Any]) -> bool:
    values = {
        _lower(row.get("ledger_type")),
        _lower(row.get("proof_type")),
        _lower(row.get("row_type")),
        _lower(row.get("confidence_bucket")),
        _lower(row.get("confidence_tier")),
        _lower(row.get("public_confidence")),
        _lower(row.get("volume_tier")),
    }
    if values & _HIGH_CONFIDENCE_FLAGS:
        return True
    return any("high_confidence" in value or "ultra" in value or "premium" in value for value in values)


def can_be_official(row: Mapping[str, Any]) -> bool:
    """Return True only when a row is safe to count as official forward proof."""
    return (
        has_required_proof_fields(row)
        and is_future_locked(row)
        and has_clean_audit(row)
        and not is_research_or_learning(row)
    )


def can_be_public_high_confidence(row: Mapping[str, Any]) -> bool:
    return has_required_proof_fields(row) and is_future_locked(row) and has_clean_audit(row) and has_high_confidence_hint(row) and not is_research_or_learning(row)


def classify_ledger_type(row: Mapping[str, Any]) -> str:
    """Classify a row into the safest ledger bucket.

    Explicit quarantine/research/learning hints take priority. High-confidence
    proof ledgers are kept separate from low-confidence research rows but remain
    public-metric eligible when they were locked before start.
    """
    explicit = _lower(row.get("ledger_type") or row.get("proof_type") or row.get("row_type"))
    audit_status = _lower(row.get("odds_audit_status") or row.get("audit_status"))

    if explicit in {QUARANTINE_LEDGER, "review", "review_only"} or audit_status in _BAD_STATUS:
        return QUARANTINE_LEDGER
    if is_demonstration_row(row):
        return RESEARCH_LEDGER
    if explicit in {LEARNING_ONLY_LEDGER, "learning", "backfill"} or _truthy(row.get("learning_only")):
        return LEARNING_ONLY_LEDGER
    if explicit in {ALL_HIGH_CONFIDENCE_LEDGER, "all_high_confidence", "high_confidence_test", "b_high_confidence_test"} or has_high_confidence_hint(row):
        return ALL_HIGH_CONFIDENCE_LEDGER
    if explicit in {RESEARCH_LEDGER, "test", "testing"} or is_research_or_learning(row):
        return RESEARCH_LEDGER
    if explicit in {CLIENT_LEDGER, "client_facing"} and can_be_official(row):
        return CLIENT_LEDGER
    if explicit in _OFFICIAL_FLAGS or _truthy(row.get("official")):
        return OFFICIAL_LEDGER if can_be_official(row) else RESEARCH_LEDGER
    return OFFICIAL_LEDGER if can_be_official(row) else RESEARCH_LEDGER


def public_metric_allowed(row: Mapping[str, Any]) -> bool:
    """Return True when a row can be counted in public proof metrics."""
    ledger = classify_ledger_type(row)
    if ledger in {OFFICIAL_LEDGER, CLIENT_LEDGER}:
        return can_be_official(row)
    if ledger == ALL_HIGH_CONFIDENCE_LEDGER:
        return can_be_public_high_confidence(row)
    return False
