import json

import pytest

from autonomous_betting_agent import proof_center_control_service as control
from autonomous_betting_agent import proof_performance_store as store
from autonomous_betting_agent import performance_ledger_service as ledger
from autonomous_betting_agent.ledger_sync_service import sync_generated_pick_rows


@pytest.fixture()
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LEDGER_CSV_PATH", tmp_path / "proof_performance_ledger.csv")
    monkeypatch.setattr(store, "LEDGER_JSON_PATH", tmp_path / "proof_performance_ledger.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "ledger_backups")
    return tmp_path


def _row(event="Alpha vs Beta", pick="Alpha ML", locked="2026-06-29T10:00:00Z", **overrides):
    row = {
        "event": event,
        "pick": pick,
        "market_type": "h2h",
        "sportsbook": "Book A",
        "locked_at_utc": locked,
        "decimal_odds": 2.0,
        "model_probability": 0.6,
        "raw_implied_probability": 0.5,
        "no_vig_implied_probability": 0.52,
        "edge": 0.10,
        "no_vig_edge": 0.08,
        "expected_value": 0.20,
        "clv": 0.03,
        "stake_units": 1.0,
        "result": "win",
        "report_lane": "playable",
        "official_publish_ready": True,
        "odds_verified": True,
    }
    row.update(overrides)
    return row


def test_proof_center_status_with_empty_ledger(isolated_ledger):
    status = control.get_proof_center_status("client_a")
    readiness = control.get_dashboard_readiness("client_a")

    assert status["workspace_id"] == "client_a"
    assert status["ledger_rows"] == 0
    assert status["dashboard_rows"] == 0
    assert status["dashboard_ready"] is False
    assert status["ledger_integrity_status"] == "PASS"
    assert readiness["dashboard_ready"] is False
    assert readiness["warnings"]


def test_proof_center_status_with_populated_ledger_and_dashboard_ready(isolated_ledger):
    sync_generated_pick_rows([_row(), _row("Gamma vs Delta", "Gamma ML", "2026-06-29T11:00:00Z", result="loss")], "client_a")

    status = control.get_proof_center_status("client_a")
    summary = control.get_proof_center_summary("client_a")
    readiness = control.get_dashboard_readiness("client_a")

    assert status["ledger_rows"] == 2
    assert status["dashboard_rows"] == 2
    assert status["unique_events"] == 2
    assert status["wins"] == 1
    assert status["losses"] == 1
    assert status["dashboard_selected_source"] == "ledger"
    assert status["dashboard_ready"] is True
    assert summary["ledger_rows"] == 2
    assert readiness["required_fields_present"] is True
    assert readiness["missing_dashboard_fields"] == []


def test_ledger_health_safe_to_append_and_malformed_warning_path(isolated_ledger):
    empty_health = control.get_ledger_health("client_a")
    assert empty_health["safe_to_append"] is True
    assert empty_health["status"] == "PASS"

    store.LEDGER_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    store.LEDGER_JSON_PATH.write_text("{bad-json", encoding="utf-8")
    malformed = control.get_ledger_health("client_a")

    assert malformed["safe_to_append"] is True
    assert malformed["malformed_file_warnings"]


def test_import_preview_dry_run_writes_nothing_and_preview_hash(isolated_ledger):
    preview = control.preview_ledger_import([_row()], "client_a", "uploaded_csv", source_file="proof.csv")

    assert preview["dry_run"] is True
    assert preview["rows_to_add"] == 1
    assert preview["preview_hash"].startswith("preview_")
    assert not store.LEDGER_CSV_PATH.exists()
    assert not store.LEDGER_JSON_PATH.exists()


def test_approve_import_writes_after_safe_preview_and_returns_metadata(isolated_ledger):
    approval = control.approve_ledger_import([_row()], "client_a", "uploaded_csv", source_file="proof.csv", approval_reason="safe import")
    rows = ledger.read_workspace_rows("client_a")

    assert approval["approved"] is True
    assert approval["approved_at_utc"]
    assert approval["approval_reason"] == "safe import"
    assert approval["preview_hash"].startswith("preview_")
    assert approval["write_attempted"] is True
    assert approval["write_successful"] is True
    assert approval["preview_result"]["rows_to_add"] == 1
    assert approval["write_result"]["rows_to_add"] == 1
    assert len(rows) == 1


def test_approve_import_blocks_on_errors_and_unsupported_source_key(isolated_ledger):
    bad_correction = _row(record_type="correction", correction_reason="missing original")
    blocked = control.approve_ledger_import([bad_correction], "client_a", "manual_review")
    unsupported = control.approve_ledger_import([_row()], "client_a", "unsupported")

    assert blocked["approved"] is False
    assert blocked["write_attempted"] is False
    assert blocked["errors"]
    assert unsupported["approved"] is False
    assert unsupported["write_attempted"] is False
    assert unsupported["errors"]
    assert not store.LEDGER_CSV_PATH.exists()


def test_approve_import_skips_duplicates_and_zero_rows_to_add(isolated_ledger):
    first = control.approve_ledger_import([_row()], "client_a", "uploaded_csv")
    duplicate = control.approve_ledger_import([_row()], "client_a", "uploaded_csv")

    assert first["approved"] is True
    assert duplicate["approved"] is False
    assert duplicate["blocked_reason"] == "no rows to add"
    assert duplicate["write_attempted"] is False
    assert len(ledger.read_workspace_rows("client_a")) == 1


def test_approve_import_detects_preview_write_mismatch(isolated_ledger, monkeypatch):
    def fake_write(rows, workspace_id, source_key, source_file=None, dry_run=False):
        return {
            "source_key": source_key,
            "workspace_id": workspace_id,
            "dry_run": False,
            "rows_seen": 1,
            "rows_to_add": 99,
            "duplicates_detected": 0,
            "rejected_rows": 0,
            "correction_rows_detected": 0,
            "warnings": [],
            "errors": [],
            "summary": {},
            "added_rows": [],
            "duplicate_rows": [],
            "rejected_row_details": [],
        }

    monkeypatch.setattr(control, "sync_rows_by_source", fake_write)
    approval = control.approve_ledger_import([_row()], "client_a", "uploaded_csv")

    assert approval["approved"] is False
    assert approval["write_attempted"] is True
    assert approval["write_successful"] is False
    assert approval["blocked_reason"] == "preview/write mismatch"
    assert approval["errors"]


def test_duplicate_and_correction_review_from_control_service(isolated_ledger):
    original = sync_generated_pick_rows([_row()], "client_a")["added_rows"][0]
    duplicate_review = control.review_duplicate_rows([_row()], "client_a", "uploaded_csv")
    correction = _row(record_type="correction", corrected_from_proof_id=original["proof_id"], correction_reason="explicit correction", result="loss")
    correction_review = control.review_correction_rows([correction], "client_a", "manual_review")

    assert duplicate_review["duplicate_row_count"] == 1
    assert correction_review["correction_row_count"] == 1
    assert len(correction_review["valid_corrections"]) == 1


def test_private_and_public_exports_redact_private_fields(isolated_ledger):
    control.approve_ledger_import([_row()], "client_a", "uploaded_csv", source_file="/private/source.csv")

    private_exports = control.get_private_proof_exports("client_a")
    public_exports = control.get_public_proof_exports("client_a")
    public_payload = json.loads(public_exports["json"])

    assert "source_file" in private_exports["csv"]
    assert "previous_row_hash" in private_exports["json"]
    assert "source_file" not in public_exports["csv"]
    assert "source_file" not in public_exports["json"]
    assert "previous_row_hash" not in public_exports["csv"]
    assert public_payload["rows"][0]["proof_id"]
    assert public_payload["rows"][0]["row_hash"]
    assert "John Doe" not in public_exports["json"]
    assert "NY Liberty -120" not in public_exports["json"]


def test_recent_rows_workspace_isolation_source_key_validation_and_input_not_mutated(isolated_ledger):
    rows = [_row()]
    before = [dict(rows[0])]
    control.approve_ledger_import(rows, "client_a", "uploaded_csv")
    control.approve_ledger_import([_row("Other vs Team", "Other ML")], "client_b", "uploaded_csv")

    assert rows == before
    assert len(control.get_recent_proof_rows("client_a")) == 1
    assert len(control.get_recent_proof_rows("client_b")) == 1
    assert len(ledger.read_performance_ledger()) == 2
    with pytest.raises(ValueError):
        control.preview_ledger_import([_row()], "client_a", "not_supported")


def test_no_fake_demo_data_in_status_or_exports(isolated_ledger):
    control.approve_ledger_import([_row()], "client_a", "uploaded_csv")

    status = control.get_proof_center_status("client_a")
    exports = control.get_public_proof_exports("client_a")

    assert "John Doe" not in str(status)
    assert "NY Liberty -120" not in str(status)
    assert "John Doe" not in exports["json"]
    assert "NY Liberty -120" not in exports["json"]
