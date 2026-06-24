"""Local-first storage facade for ABA Signal Pro.

Uses SQLite when available and falls back to CSV without crashing. This keeps the
existing no-cloud/no-password workflow intact while providing a safer path for
commercial proof storage.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ledger_types import classify_ledger_type

try:  # pragma: no cover - exercised through LocalStorage fallback behavior
    from .sqlite_store import SQLiteStore
except Exception:  # pragma: no cover
    SQLiteStore = None  # type: ignore[assignment]

DEFAULT_CSV_DIR = Path("data/ledgers")


class LocalStorage:
    def __init__(self, db_path: str | Path = "data/aba_signal_pro.sqlite", csv_dir: str | Path = DEFAULT_CSV_DIR) -> None:
        self.csv_dir = Path(csv_dir)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_error: str = ""
        self.store = None
        if SQLiteStore is not None:
            try:
                self.store = SQLiteStore(db_path)
            except Exception as exc:  # pragma: no cover - defensive fallback
                self.sqlite_error = str(exc)
                self.store = None

    @property
    def using_sqlite(self) -> bool:
        return self.store is not None

    def save_row(self, row: Mapping[str, Any], ledger_type: str | None = None) -> str:
        resolved_ledger = ledger_type or classify_ledger_type(row)
        payload = dict(row)
        payload["ledger_type"] = resolved_ledger
        if self.store is not None:
            return self.store.save_row(payload, ledger_type=resolved_ledger)
        self._append_csv(payload, resolved_ledger)
        return str(payload.get("proof_id") or "")

    def save_rows(self, rows: Iterable[Mapping[str, Any]], ledger_type: str | None = None) -> list[str]:
        return [self.save_row(row, ledger_type=ledger_type) for row in rows]

    def load_rows(self, ledger_type: str | None = None) -> list[dict[str, Any]]:
        if self.store is not None:
            return self.store.load_rows(ledger_type=ledger_type)
        if ledger_type:
            return self._read_csv(self._csv_path(ledger_type))
        rows: list[dict[str, Any]] = []
        for path in self.csv_dir.glob("*.csv"):
            rows.extend(self._read_csv(path))
        return rows

    def update_grade(self, proof_key_or_id: str, grade: str, **kwargs: Any) -> bool:
        if self.store is not None:
            return self.store.update_grade(proof_key_or_id, grade, **kwargs)
        # CSV fallback does not rewrite historical rows to avoid silent corruption.
        self.add_audit_event("grade_update_requested_csv_fallback", {"proof_id": proof_key_or_id}, f"Grade requested: {grade}")
        return False

    def add_audit_event(self, action: str, row: Mapping[str, Any] | None = None, detail: str = "") -> None:
        if self.store is not None:
            self.store.add_audit_event(action=action, row=row, detail=detail)
            return
        path = self.csv_dir / "audit_log.csv"
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["action", "proof_id", "detail"])
            if not exists:
                writer.writeheader()
            writer.writerow({"action": action, "proof_id": (row or {}).get("proof_id", ""), "detail": detail})

    def load_audit_log(self, limit: int = 250) -> list[dict[str, Any]]:
        if self.store is not None:
            return self.store.load_audit_log(limit=limit)
        rows = self._read_csv(self.csv_dir / "audit_log.csv")
        return rows[-limit:]

    def export_csv(self, path: str | Path, ledger_type: str | None = None) -> Path:
        rows = self.load_rows(ledger_type=ledger_type)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            out.write_text("", encoding="utf-8")
            return out
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return out

    def import_csv(self, path: str | Path, ledger_type: str | None = None) -> int:
        rows = self._read_csv(Path(path))
        self.save_rows(rows, ledger_type=ledger_type)
        return len(rows)

    def _csv_path(self, ledger_type: str) -> Path:
        return self.csv_dir / f"{ledger_type}.csv"

    def _append_csv(self, row: Mapping[str, Any], ledger_type: str) -> None:
        path = self._csv_path(ledger_type)
        exists = path.exists()
        fieldnames = sorted(set(row.keys()))
        if exists:
            existing = self._read_csv(path)
            fieldnames = sorted({key for item in existing for key in item.keys()} | set(row.keys()))
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(existing)
                writer.writerow(dict(row))
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(dict(row))

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, Any]]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", newline="", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
