from __future__ import annotations

from autonomous_betting_agent.storage import LocalStorage


def _row(proof_id: str = "PX1", grade: str = "") -> dict[str, object]:
    return {
        "proof_id": proof_id,
        "locked_at_utc": "2026-06-23T10:00:00+00:00",
        "event_start_time": "2026-06-23T12:00:00+00:00",
        "event_name": "Local Storage Test",
        "prediction": "Team A",
        "market": "moneyline",
        "odds_audit_status": "pass",
        "grade": grade,
    }


def test_sqlite_storage_saves_and_loads_official_rows(tmp_path):
    store = LocalStorage(db_path=tmp_path / "aba.sqlite", csv_dir=tmp_path / "ledgers")
    key = store.save_row(_row())
    assert key == "PX1"
    rows = store.load_rows("official")
    assert len(rows) == 1
    assert rows[0]["proof_id"] == "PX1"


def test_sqlite_storage_prevents_silent_grade_conflict(tmp_path):
    store = LocalStorage(db_path=tmp_path / "aba.sqlite", csv_dir=tmp_path / "ledgers")
    store.save_row(_row("PX2", grade="win"))
    assert store.update_grade("PX2", "loss") is False
    assert store.update_grade("PX2", "loss", overwrite=True) is True
    rows = store.load_rows("official")
    assert rows[0]["grade"] == "loss"


def test_storage_can_export_csv(tmp_path):
    store = LocalStorage(db_path=tmp_path / "aba.sqlite", csv_dir=tmp_path / "ledgers")
    store.save_row(_row("PX3"))
    output = store.export_csv(tmp_path / "export.csv", ledger_type="official")
    text = output.read_text(encoding="utf-8")
    assert "PX3" in text
    assert "proof_id" in text
