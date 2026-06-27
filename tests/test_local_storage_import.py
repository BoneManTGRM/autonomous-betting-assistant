from __future__ import annotations

from pathlib import Path

from autonomous_betting_agent.local_storage_import import (
    import_rows_to_local_storage,
    parse_uploaded_csv_bytes,
    save_reparodynamics_rows_to_research,
    stable_row_identity,
)
from autonomous_betting_agent.storage import LocalStorage


class FakeStorage:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.audit: list[dict] = []

    def save_rows(self, rows, ledger_type=None):
        ledger = ledger_type or "research"
        self.rows.setdefault(ledger, [])
        for row in rows:
            payload = dict(row)
            payload["ledger_type"] = ledger
            self.rows[ledger].append(payload)
        return [str(row.get("proof_id") or idx) for idx, row in enumerate(rows)]

    def load_rows(self, ledger_type=None):
        if ledger_type:
            return list(self.rows.get(ledger_type, []))
        all_rows = []
        for rows in self.rows.values():
            all_rows.extend(rows)
        return all_rows

    def add_audit_event(self, action, row=None, detail=""):
        self.audit.append({"action": action, "row": row or {}, "detail": detail})

    def load_audit_log(self, limit=250):
        return self.audit[-limit:]


def _row(proof_id="", event="Team A vs Team B", pick="Team A", market="moneyline"):
    return {"proof_id": proof_id, "event": event, "pick": pick, "market_type": market, "odds": "+110", "result": "win"}


def test_local_csv_import_parses_rows():
    rows = parse_uploaded_csv_bytes(b"event,pick,result\nA vs B,A,win\n")
    assert rows == [{"event": "A vs B", "pick": "A", "result": "win"}]


def test_preview_only_mode_does_not_save_rows():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], preview_only=True, confirmed=True, storage=storage)
    assert result["rows_seen"] == 1
    assert result["rows_imported"] == 0
    assert storage.load_rows("research") == []


def test_confirmation_is_required_before_saving():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], preview_only=False, confirmed=False, storage=storage)
    assert result["rows_imported"] == 0
    assert "Confirmation required" in result["message"]
    assert storage.load_rows("research") == []


def test_import_saves_rows_to_selected_ledger():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], ledger_type="quarantine", preview_only=False, confirmed=True, storage=storage)
    assert result["rows_imported"] == 1
    assert len(storage.load_rows("quarantine")) == 1


def test_import_to_research_ledger_increases_research_count():
    storage = FakeStorage()
    before = len(storage.load_rows("research"))
    import_rows_to_local_storage([_row()], ledger_type="research", preview_only=False, confirmed=True, storage=storage)
    assert len(storage.load_rows("research")) == before + 1


def test_import_writes_local_audit_event():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], preview_only=False, confirmed=True, storage=storage, filename="graded.csv")
    assert result["audit_written"] is True
    assert storage.audit[-1]["action"] == "local_storage_import"
    assert "no model mutation" in storage.audit[-1]["detail"]
    assert "graded.csv" in storage.audit[-1]["detail"]


def test_duplicate_rows_are_skipped_when_dedupe_true():
    storage = FakeStorage()
    import_rows_to_local_storage([_row(proof_id="p1")], preview_only=False, confirmed=True, storage=storage)
    result = import_rows_to_local_storage([_row(proof_id="p1")], preview_only=False, confirmed=True, storage=storage, dedupe=True)
    assert result["rows_imported"] == 0
    assert result["rows_skipped_duplicate"] == 1
    assert len(storage.load_rows("research")) == 1


def test_duplicate_rows_are_not_skipped_when_dedupe_false():
    storage = FakeStorage()
    import_rows_to_local_storage([_row(proof_id="p1")], preview_only=False, confirmed=True, storage=storage)
    result = import_rows_to_local_storage([_row(proof_id="p1")], preview_only=False, confirmed=True, storage=storage, dedupe=False)
    assert result["rows_imported"] == 1
    assert result["rows_skipped_duplicate"] == 0
    assert len(storage.load_rows("research")) == 2


def test_invalid_ledger_type_is_rejected_safely():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], ledger_type="bad_ledger", preview_only=False, confirmed=True, storage=storage)
    assert result["rows_imported"] == 0
    assert "Invalid ledger" in result["message"]
    assert storage.load_rows() == []


def test_stable_row_identity_dedupes_rows_without_proof_id():
    first = _row(proof_id="", event=" Team A vs Team B ")
    second = _row(proof_id="", event="team a vs team b")
    assert stable_row_identity(first) == stable_row_identity(second)


def test_stable_row_identity_uses_proof_id_when_present():
    first = _row(proof_id="Proof-1", event="A")
    second = _row(proof_id=" proof-1 ", event="B")
    assert stable_row_identity(first) == "proof_id:proof-1"
    assert stable_row_identity(first) == stable_row_identity(second)


def test_reparodynamics_optional_save_writes_rows_to_research_when_confirmed():
    storage = FakeStorage()
    result = save_reparodynamics_rows_to_research([_row()], run_id="run123", confirmed=True, storage=storage)
    assert result["rows_imported"] == 1
    assert len(storage.load_rows("research")) == 1
    assert storage.audit[-1]["action"] == "reparodynamics_rows_saved_to_research"
    assert "run123" in storage.audit[-1]["detail"]


def test_saving_rows_does_not_change_live_mutation_or_repair_activation_flags():
    storage = FakeStorage()
    result = import_rows_to_local_storage([_row()], preview_only=False, confirmed=True, storage=storage)
    assert result["live_mutation"] is False
    assert result["model_training"] is False
    assert result["saved_locally_only"] is True


def test_local_control_center_storage_loads_when_empty(tmp_path: Path):
    storage = LocalStorage(db_path=tmp_path / "test.sqlite", csv_dir=tmp_path / "ledgers")
    assert storage.load_rows() == []
    assert storage.load_rows("research") == []


def test_spanish_safety_warning_text_exists():
    content = Path("pages/local_control_center.py").read_text(encoding="utf-8")
    assert "Guardar filas aqui solo almacena filas de prueba/investigacion localmente" in content


def test_storage_persistence_warning_text_exists():
    content = Path("pages/local_control_center.py").read_text(encoding="utf-8")
    assert "Local storage may not persist across redeploys unless persistent storage is configured" in content


def test_export_backup_warning_or_control_exists():
    content = Path("pages/local_control_center.py").read_text(encoding="utf-8")
    assert "Backup all local rows" in content
    assert "Backup audit events" in content
