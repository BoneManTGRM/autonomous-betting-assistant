import pandas as pd
import pytest

from autonomous_betting_agent import proof_performance_store as store
from autonomous_betting_agent import performance_ledger_service as ledger
from autonomous_betting_agent.ledger_sync_service import (
    GENERATED_PICK_SOURCE,
    LEARNING_PAGE_SOURCE,
    MANUAL_REVIEW_SOURCE,
    ODDS_LOCK_SOURCE,
    PROOF_CENTER_SOURCE,
    PRO_PREDICTOR_SOURCE,
    REPORT_STUDIO_SOURCE,
    UPLOADED_CSV_SOURCE,
    SYNC_SOURCE_REGISTRY,
    sync_generated_pick_rows,
    sync_learning_rows,
    sync_manual_review_rows,
    sync_odds_lock_rows,
    sync_pro_predictor_rows,
    sync_proof_center_rows,
    sync_report_studio_rows,
    sync_rows_by_source,
    sync_uploaded_csv_rows,
)


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


def _assert_result_shape(result, source_key):
    assert result["source_key"] == source_key
    assert result["workspace_id"] == "client_a"
    assert "rows_seen" in result
    assert "rows_to_add" in result
    assert "duplicates_detected" in result
    assert "rejected_rows" in result
    assert "correction_rows_detected" in result
    assert "warnings" in result
    assert "errors" in result
    assert "summary" in result
    assert "added_rows" in result
    assert "duplicate_rows" in result
    assert "rejected_row_details" in result


def test_sync_source_registry_constants_are_stable():
    assert SYNC_SOURCE_REGISTRY[ODDS_LOCK_SOURCE]
    assert SYNC_SOURCE_REGISTRY[PRO_PREDICTOR_SOURCE]
    assert SYNC_SOURCE_REGISTRY[REPORT_STUDIO_SOURCE]
    assert SYNC_SOURCE_REGISTRY[PROOF_CENTER_SOURCE]
    assert SYNC_SOURCE_REGISTRY[LEARNING_PAGE_SOURCE]
    assert SYNC_SOURCE_REGISTRY[UPLOADED_CSV_SOURCE]
    assert SYNC_SOURCE_REGISTRY[GENERATED_PICK_SOURCE]
    assert SYNC_SOURCE_REGISTRY[MANUAL_REVIEW_SOURCE]


def test_sync_all_named_sources_preserve_source_keys_and_files(isolated_ledger):
    calls = [
        (sync_odds_lock_rows, ODDS_LOCK_SOURCE, _row("A vs B", "A ML", "2026-06-29T10:00:00Z")),
        (sync_pro_predictor_rows, PRO_PREDICTOR_SOURCE, _row("C vs D", "C ML", "2026-06-29T11:00:00Z")),
        (sync_report_studio_rows, REPORT_STUDIO_SOURCE, _row("E vs F", "E ML", "2026-06-29T12:00:00Z")),
        (sync_proof_center_rows, PROOF_CENTER_SOURCE, _row("G vs H", "G ML", "2026-06-29T13:00:00Z")),
        (sync_learning_rows, LEARNING_PAGE_SOURCE, _row("I vs J", "I ML", "2026-06-29T14:00:00Z")),
        (sync_uploaded_csv_rows, UPLOADED_CSV_SOURCE, _row("K vs L", "K ML", "2026-06-29T15:00:00Z")),
        (sync_generated_pick_rows, GENERATED_PICK_SOURCE, _row("M vs N", "M ML", "2026-06-29T16:00:00Z")),
        (sync_manual_review_rows, MANUAL_REVIEW_SOURCE, _row("O vs P", "O ML", "2026-06-29T17:00:00Z")),
    ]

    for func, source_key, row in calls:
        result = func([row], "Client A", source_file=f"{source_key}.csv")
        _assert_result_shape(result, source_key)
        assert result["rows_seen"] == 1
        assert result["rows_to_add"] == 1
        assert result["added_rows"][0]["source_key"] == source_key
        assert result["added_rows"][0]["source_file"] == f"{source_key}.csv"

    rows = ledger.read_workspace_rows("client_a")
    assert len(rows) == 8
    assert set(rows["source_key"]) == {
        ODDS_LOCK_SOURCE,
        PRO_PREDICTOR_SOURCE,
        REPORT_STUDIO_SOURCE,
        PROOF_CENTER_SOURCE,
        LEARNING_PAGE_SOURCE,
        UPLOADED_CSV_SOURCE,
        GENERATED_PICK_SOURCE,
        MANUAL_REVIEW_SOURCE,
    }


def test_generic_sync_dry_run_writes_nothing_and_rejected_rows_reported(isolated_ledger):
    result = sync_rows_by_source(
        [_row(), {"event": "", "pick": ""}],
        "Client A",
        ODDS_LOCK_SOURCE,
        source_file="dry.csv",
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["rows_seen"] == 2
    assert result["rows_to_add"] == 1
    assert result["rejected_rows"] == 1
    assert not store.LEDGER_CSV_PATH.exists()
    assert not store.LEDGER_JSON_PATH.exists()


def test_duplicate_rows_and_repeated_sync_do_not_inflate_ledger(isolated_ledger):
    first = sync_odds_lock_rows([_row()], "client_a", source_file="locks.csv")
    second = sync_odds_lock_rows([_row()], "client_a", source_file="locks.csv")
    third = sync_odds_lock_rows(pd.DataFrame([_row(), _row()]), "client_a", source_file="locks.csv")

    assert first["rows_to_add"] == 1
    assert second["rows_to_add"] == 0
    assert second["duplicates_detected"] == 1
    assert third["rows_to_add"] == 0
    assert third["duplicates_detected"] == 2
    assert len(ledger.read_workspace_rows("client_a")) == 1


def test_workspace_isolation(isolated_ledger):
    sync_pro_predictor_rows([_row()], "client_a")
    sync_pro_predictor_rows([_row()], "client_b")

    assert len(ledger.read_workspace_rows("client_a")) == 1
    assert len(ledger.read_workspace_rows("client_b")) == 1
    assert len(ledger.read_performance_ledger()) == 2


def test_correction_rows_pass_only_when_explicitly_marked_no_auto_correction(isolated_ledger):
    original = sync_generated_pick_rows([_row()], "client_a")["added_rows"][0]
    changed_result_same_pick = _row(result="loss")
    duplicate_result = sync_generated_pick_rows([changed_result_same_pick], "client_a")
    correction = _row(result="loss", record_type="correction", corrected_from_proof_id=original["proof_id"], correction_reason="explicit grading correction")
    correction_result = sync_manual_review_rows([correction], "client_a")

    assert duplicate_result["rows_to_add"] == 0
    assert duplicate_result["correction_rows_detected"] == 0
    assert correction_result["rows_to_add"] == 1
    assert correction_result["correction_rows_detected"] == 1
    rows = ledger.read_workspace_rows("client_a")
    assert len(rows) == 2
    assert set(rows["record_type"]) == {"import", "correction"}


def test_sync_does_not_mutate_input_rows_or_existing_proof_rows(isolated_ledger):
    source = [_row()]
    source_before = [dict(source[0])]
    result = sync_uploaded_csv_rows(source, "client_a")
    original_hash = result["added_rows"][0]["row_hash"]
    original_proof = result["added_rows"][0]["proof_id"]

    source[0]["result"] = "loss"
    sync_uploaded_csv_rows(source, "client_a")
    stored = ledger.read_workspace_rows("client_a")

    assert source_before[0]["result"] == "win"
    assert len(stored) == 1
    assert stored.iloc[0]["row_hash"] == original_hash
    assert stored.iloc[0]["proof_id"] == original_proof


def test_unsupported_source_key_is_rejected(isolated_ledger):
    with pytest.raises(ValueError):
        sync_rows_by_source([_row()], "client_a", "unsupported")
