"""Local Learning Memory safety controls.

These helpers identify rows that are safe to export for learning. They do not
train, reset, overwrite, or delete memory automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ledger_types import classify_ledger_type

SAFE_LEDGERS = {"official", "client", "research", "all_high_confidence"}
BAD_AUDITS = {"fail", "failed", "quarantine", "blocked", "bad"}
USABLE_GRADES = {"win", "won", "w", "loss", "lost", "l", "push", "void", "draw"}
VERSION_DIR = Path("data/learning_memory_versions")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def learning_safe_reason(row: Mapping[str, Any]) -> tuple[bool, str]:
    ledger_type = classify_ledger_type(row)
    grade = _lower(row.get("grade") or row.get("result"))
    audit_status = _lower(row.get("odds_audit_status") or row.get("audit_status"))
    has_probability = bool(row.get("learned_model_probability") or row.get("model_probability") or row.get("probability"))
    has_price = bool(row.get("decimal_price") or row.get("odds_at_pick"))

    if ledger_type not in SAFE_LEDGERS:
        return False, f"Ledger type {ledger_type} is not approved for learning export."
    if audit_status in BAD_AUDITS:
        return False, "Audit status is quarantined, failed, or blocked."
    if grade not in USABLE_GRADES:
        return False, "Row needs a usable final grade before learning export."
    if not has_probability:
        return False, "Row is missing model probability."
    if not has_price:
        return False, "Row is missing proof-safe price."
    return True, "Learning-safe export candidate."


def split_learning_safe_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    safe: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        ok, reason = learning_safe_reason(payload)
        payload["learning_safe"] = ok
        payload["learning_block_reason"] = reason
        payload["ledger_type"] = classify_ledger_type(payload)
        if ok:
            safe.append(payload)
        else:
            blocked.append(payload)
    return safe, blocked


def version_placeholder_path(label: str = "manual") -> Path:
    VERSION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in {"_", "-"}) or "manual"
    return VERSION_DIR / f"learning_memory_{safe_label}_{stamp}.json"


def reset_confirmation_matches(value: str) -> bool:
    return _text(value) == "RESET LEARNING MEMORY"
