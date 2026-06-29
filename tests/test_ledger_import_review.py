import pytest

from autonomous_betting_agent import proof_performance_store as store
from autonomous_betting_agent import performance_ledger_service as ledger
from autonomous_betting_agent.ledger_import_review import (
    preview_ledger_import,
    review_correction_rows,
    review_duplicate_rows,
)
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


def test_import_preview_dry_run_writes_nothing_and_has_hash(isolated_ledger):
    rows = [_row(), _row(event="Gamma vs Delta", pick="Gamma ML", locked="2026-06-29T11:00:00Z")]

    preview = preview_ledger_import(rows, "client_a", "uploaded_csv", source_file="proof.csv")

    assert preview["dry_run"] is True
    assert preview["rows_seen"] == 2
    assert preview["rows_to_add"] == 2
    assert preview["approval_required"] is True
    assert preview["preview_hash"].startswith("preview_")
    assert not store.LEDGER_CSV_PATH.exists()
    assert not store.LEDGER_JSON_PATH.exists()


def test_preview_hash_stability_and_changes_when_input_changes(isolated_ledger):
    first = preview_ledger_import([_row()], "client_a", "uploaded_csv", source_file="proof.csv")
    second = preview_ledger_import([_row()], "client_a", "uploaded_csv", source_file="proof.csv")
    changed = preview_ledger_import([_row(event="Changed Game")], "client_a", "uploaded_csv", source_file="proof.csv")

    assert first["preview_hash"] == second["preview_hash"]
    assert first["preview_hash"] != changed["preview_hash"]


def test_duplicate_review_detects_existing_and_incoming_duplicates(isolated_ledger):
    sync_generated_pick_rows([_row()], "client_a")

    review = review_duplicate_rows([_row(), _row()], "client_a", "uploaded_csv", source_file="dupes.csv")

    assert review["duplicate_row_count"] == 2
    assert review["duplicate_keys"]
    assert review["proof_ids"]
    assert len(ledger.read_workspace_rows("client_a")) == 1


def test_preview_reports_duplicates_but_does_not_write(isolated_ledger):
    sync_generated_pick_rows([_row()], "client_a")

    preview = preview_ledger_import([_row()], "client_a", "uploaded_csv")

    assert preview["rows_seen"] == 1
    assert preview["rows_to_add"] == 0
    assert preview["duplicates_detected"] == 1
    assert preview["approval_required"] is False
    assert len(ledger.read_workspace_rows("client_a")) == 1


def test_correction_review_detects_valid_explicit_correction(isolated_ledger):
    original = sync_generated_pick_rows([_row()], "client_a")["added_rows"][0]
    correction = _row(
        result="loss",
        record_type="correction",
        corrected_from_proof_id=original["proof_id"],
        correction_reason="explicit grading fix",
    )

    review = review_correction_rows([correction], "client_a", "manual_review")

    assert review["correction_row_count"] == 1
    assert len(review["valid_corrections"]) == 1
    assert not review["rejected_corrections"]
    assert not review["errors"]


def test_correction_review_rejects_missing_reason(isolated_ledger):
    original = sync_generated_pick_rows([_row()], "client_a")["added_rows"][0]
    correction = _row(record_type="correction", corrected_from_proof_id=original["proof_id"])

    review = review_correction_rows([correction], "client_a", "manual_review")

    assert review["correction_row_count"] == 1
    assert not review["valid_corrections"]
    assert review["rejected_corrections"][0]["reason"] == "missing correction_reason"
    assert review["errors"]


def test_correction_review_rejects_missing_corrected_from_proof_id(isolated_ledger):
    correction = _row(record_type="correction", correction_reason="explicit grading fix")

    review = review_correction_rows([correction], "client_a", "manual_review")

    assert review["correction_row_count"] == 1
    assert not review["valid_corrections"]
    assert review["rejected_corrections"][0]["reason"] == "missing corrected_from_proof_id"
    assert review["errors"]


def test_no_automatic_correction_creation_from_changed_result(isolated_ledger):
    sync_generated_pick_rows([_row()], "client_a")
    changed_result = _row(result="loss")

    preview = preview_ledger_import([changed_result], "client_a", "manual_review")

    assert preview["correction_rows_detected"] == 0
    assert preview["rows_to_add"] == 0
    assert preview["duplicates_detected"] == 1


def test_unsupported_source_key_validation(isolated_ledger):
    with pytest.raises(ValueError):
        preview_ledger_import([_row()], "client_a", "not_supported")

    with pytest.raises(ValueError):
        review_duplicate_rows([_row()], "client_a", "not_supported")

    with pytest.raises(ValueError):
        review_correction_rows([_row(record_type="correction")], "client_a", "not_supported")


def test_input_rows_are_not_mutated(isolated_ledger):
    rows = [_row()]
    before = [dict(rows[0])]

    preview_ledger_import(rows, "client_a", "uploaded_csv")
    review_duplicate_rows(rows, "client_a", "uploaded_csv")
    review_correction_rows(rows, "client_a", "uploaded_csv")

    assert rows == before
    assert "John Doe" not in str(preview_ledger_import(rows, "client_a", "uploaded_csv"))
    assert "NY Liberty -120" not in str(preview_ledger_import(rows, "client_a", "uploaded_csv"))
