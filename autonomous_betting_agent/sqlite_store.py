"""Local SQLite storage for ABA Signal Pro.

No cloud database is required. This module stores rows and audit events in a
single local SQLite file and keeps JSON row payloads so existing CSV schemas can
continue to evolve without fragile migrations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ledger_types import classify_ledger_type, event_start_value
from .grading_rules import PENDING, normalize_grade

DEFAULT_DB_PATH = Path("data/aba_signal_pro.sqlite")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(row: Mapping[str, Any]) -> str:
    return json.dumps(dict(row), sort_keys=True, default=str)


def _first(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def _grade_value(row: Mapping[str, Any]) -> str:
    return _first(
        row,
        "grade",
        "result_status",
        "verified_grade",
        "verified_result",
        "final_grade",
        "proof_grade",
        "result",
        "outcome",
    )


def _proof_key(row: Mapping[str, Any]) -> str:
    proof_id = str(row.get("proof_id") or "").strip()
    if proof_id:
        return proof_id
    parts = [
        _first(row, "event_name", "event", "matchup"),
        _first(row, "prediction", "pick", "selection"),
        _first(row, "market", "market_type"),
        event_start_value(row),
    ]
    return "|".join(parts)


class SQLiteStore:
    """Small local SQLite store with row and audit-log tables."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS proof_rows (
                    proof_key TEXT PRIMARY KEY,
                    proof_id TEXT,
                    ledger_type TEXT NOT NULL,
                    event_name TEXT,
                    prediction TEXT,
                    market TEXT,
                    event_start_time TEXT,
                    locked_at_utc TEXT,
                    grade TEXT,
                    proof_hash TEXT,
                    row_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proof_key TEXT,
                    proof_id TEXT,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_row(self, row: Mapping[str, Any], ledger_type: str | None = None, action: str = "row_saved") -> str:
        payload = dict(row)
        resolved_ledger = ledger_type or classify_ledger_type(payload)
        payload["ledger_type"] = resolved_ledger
        if event_start_value(payload) and not payload.get("event_start_time"):
            payload["event_start_time"] = event_start_value(payload)
        grade = _grade_value(payload)
        if grade and not payload.get("grade"):
            payload["grade"] = grade
        if grade and not payload.get("result_status"):
            payload["result_status"] = grade
        proof_key = _proof_key(payload)
        now = _utc_now()
        with self.connect() as conn:
            existing = conn.execute("SELECT created_at_utc FROM proof_rows WHERE proof_key = ?", (proof_key,)).fetchone()
            created_at = existing["created_at_utc"] if existing else now
            conn.execute(
                """
                INSERT INTO proof_rows (
                    proof_key, proof_id, ledger_type, event_name, prediction, market,
                    event_start_time, locked_at_utc, grade, proof_hash, row_json,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proof_key) DO UPDATE SET
                    proof_id=excluded.proof_id,
                    ledger_type=excluded.ledger_type,
                    event_name=excluded.event_name,
                    prediction=excluded.prediction,
                    market=excluded.market,
                    event_start_time=excluded.event_start_time,
                    locked_at_utc=excluded.locked_at_utc,
                    grade=excluded.grade,
                    proof_hash=excluded.proof_hash,
                    row_json=excluded.row_json,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    proof_key,
                    payload.get("proof_id"),
                    resolved_ledger,
                    _first(payload, "event_name", "event", "matchup"),
                    _first(payload, "prediction", "pick", "selection"),
                    _first(payload, "market", "market_type"),
                    event_start_value(payload),
                    payload.get("locked_at_utc"),
                    grade,
                    payload.get("proof_hash"),
                    _json(payload),
                    created_at,
                    now,
                ),
            )
            self.add_audit_event(action=action, row=payload, detail=f"Saved to {resolved_ledger}", conn=conn)
            conn.commit()
        return proof_key

    def save_rows(self, rows: Iterable[Mapping[str, Any]], ledger_type: str | None = None) -> list[str]:
        return [self.save_row(row, ledger_type=ledger_type) for row in rows]

    def load_rows(self, ledger_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT row_json, ledger_type FROM proof_rows"
        params: tuple[Any, ...] = ()
        if ledger_type:
            sql += " WHERE ledger_type = ?"
            params = (ledger_type,)
        sql += " ORDER BY updated_at_utc DESC"
        with self.connect() as conn:
            out: list[dict[str, Any]] = []
            for item in conn.execute(sql, params).fetchall():
                row = json.loads(item["row_json"])
                row.setdefault("ledger_type", item["ledger_type"])
                if event_start_value(row) and not row.get("event_start_time"):
                    row["event_start_time"] = event_start_value(row)
                if _grade_value(row) and not row.get("result_status"):
                    row["result_status"] = _grade_value(row)
                out.append(row)
            return out

    def update_grade(
        self,
        proof_key_or_id: str,
        grade: str,
        source_name: str = "",
        source_url: str = "",
        confidence: str = "manual",
        overwrite: bool = False,
    ) -> bool:
        now = _utc_now()
        with self.connect() as conn:
            item = conn.execute(
                "SELECT proof_key, row_json, grade FROM proof_rows WHERE proof_key = ? OR proof_id = ?",
                (proof_key_or_id, proof_key_or_id),
            ).fetchone()
            if not item:
                return False
            old_grade = item["grade"]
            old_normalized = normalize_grade(old_grade)
            new_normalized = normalize_grade(grade)
            # normalize_grade also returns pending for unknown provider labels.
            # Only explicit pending states may settle without overriding history.
            old_token = " ".join(str(old_grade or "").strip().lower().replace("_", " ").replace("-", " ").split())
            pending_tokens = {value.replace("_", " ").replace("-", " ") for value in PENDING}
            same_grade = old_grade == grade or (old_normalized != "pending" and old_normalized == new_normalized)
            if old_token not in pending_tokens and not same_grade and not overwrite:
                self.add_audit_event(
                    action="grade_conflict",
                    row={"proof_id": proof_key_or_id},
                    detail=f"Existing grade {old_grade!r} conflicts with new grade {grade!r}",
                    conn=conn,
                )
                conn.commit()
                return False
            row = json.loads(item["row_json"])
            row.update(
                {
                    "grade": grade,
                    "result": grade,
                    "result_status": grade,
                    "result_source_name": source_name,
                    "result_source_url": source_url,
                    "grade_confidence": confidence,
                    "graded_at_utc": now,
                }
            )
            conn.execute(
                "UPDATE proof_rows SET grade = ?, row_json = ?, updated_at_utc = ? WHERE proof_key = ?",
                (grade, _json(row), now, item["proof_key"]),
            )
            self.add_audit_event(action="row_graded", row=row, detail=f"Grade set to {grade}", conn=conn)
            conn.commit()
            return True

    def add_audit_event(
        self,
        action: str,
        row: Mapping[str, Any] | None = None,
        detail: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> None:
        payload = dict(row or {})
        proof_key = _proof_key(payload) if payload else ""
        proof_id = str(payload.get("proof_id") or "") if payload else ""
        owns_conn = conn is None
        db = conn or self.connect()
        try:
            db.execute(
                "INSERT INTO audit_log (proof_key, proof_id, action, detail, created_at_utc) VALUES (?, ?, ?, ?, ?)",
                (proof_key, proof_id, action, detail, _utc_now()),
            )
            if owns_conn:
                db.commit()
        finally:
            if owns_conn:
                db.close()

    def load_audit_log(self, limit: int = 250) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT proof_key, proof_id, action, detail, created_at_utc FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
