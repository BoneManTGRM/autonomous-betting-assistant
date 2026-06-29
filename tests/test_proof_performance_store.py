import json

import pandas as pd
import pytest

from autonomous_betting_agent import proof_performance_store as store


@pytest.fixture()
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LEDGER_CSV_PATH", tmp_path / "proof_performance_ledger.csv")
    monkeypatch.setattr(store, "LEDGER_JSON_PATH", tmp_path / "proof_performance_ledger.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "ledger_backups")
    return tmp_path


def _base_row(**overrides):
    row = {
        "event": "Alpha vs Beta",
        "pick": "Alpha ML",
        "market_type": "h2h",
        "sportsbook": "Book A",
        "locked_at_utc": "2026-06-29T10:00:00Z",
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


def test_normalize_aliases_schema_version_proof_id_and_row_hash_stability(isolated_ledger):
    row = {
        "public_event": "Alpha vs Beta",
        "public_pick": "Alpha ML",
        "bookmaker": "Book A",
        "market": "h2h",
        "decimal_price": 2.0,
        "model_market_edge": 0.10,
        "model_no_vig_edge": 0.08,
        "expected_value_per_unit": 0.20,
        "manual_clv": 0.03,
        "grade": "won",
        "locked_at": "2026-06-29T10:00:00Z",
        "official_publish_ready": True,
        "odds_verified": True,
    }

    first = store.normalize_performance_record(row, "Client One", source_key="uploaded CSV", source_file="private/path.csv")
    second = store.normalize_performance_record(row, "Client One", source_key="uploaded CSV", source_file="private/path.csv")

    assert first["schema_version"] == store.SCHEMA_VERSION
    assert first["workspace_id"] == "client_one"
    assert first["event"] == "Alpha vs Beta"
    assert first["pick"] == "Alpha ML"
    assert first["sportsbook"] == "Book A"
    assert first["market_type"] == "h2h"
    assert first["decimal_odds"] == 2.0
    assert first["result"] == "win"
    assert first["proof_id"] == second["proof_id"]
    assert first["row_hash"] == second["row_hash"]
    assert store.build_duplicate_key(first) == first["duplicate_key"]
    assert store.build_row_hash(first) == first["row_hash"]


def test_dry_run_does_not_write_files_and_reports_duplicates_rejections(isolated_ledger):
    rows = [_base_row(), _base_row(), {"event": "", "pick": ""}]

    result = store.append_performance_rows(rows, "client_a", source_key="uploaded_csv", dry_run=True)

    assert result["rows_seen"] == 3
    assert result["rows_to_add"] == 1
    assert result["duplicates_detected"] == 1
    assert result["rejected_rows"] == 1
    assert result["dry_run"] is True
    assert not store.LEDGER_CSV_PATH.exists()
    assert not store.LEDGER_JSON_PATH.exists()


def test_append_preserves_existing_rows_workspace_isolation_and_duplicate_detection(isolated_ledger):
    first = store.append_performance_rows([_base_row()], "client_a", source_key="generated")
    original_hash = first["added_rows"][0]["row_hash"]
    original_proof = first["added_rows"][0]["proof_id"]

    duplicate = store.append_performance_rows([_base_row()], "client_a", source_key="generated")
    other_workspace = store.append_performance_rows([_base_row(event="Gamma vs Delta", pick="Gamma ML")], "client_b", source_key="generated")

    assert duplicate["rows_to_add"] == 0
    assert duplicate["duplicates_detected"] == 1
    assert other_workspace["rows_to_add"] == 1
    all_rows = store.read_performance_ledger()
    client_a = store.read_workspace_rows("client_a")
    client_b = store.read_workspace_rows("client_b")
    assert len(all_rows) == 2
    assert len(client_a) == 1
    assert len(client_b) == 1
    assert client_a.iloc[0]["row_hash"] == original_hash
    assert client_a.iloc[0]["proof_id"] == original_proof


def test_ledger_sequence_previous_hash_chain_atomic_writes_and_backups(isolated_ledger):
    store.append_performance_rows([_base_row()], "client_a", source_key="generated")
    store.append_performance_rows([_base_row(event="Gamma vs Delta", pick="Gamma ML", locked_at_utc="2026-06-29T11:00:00Z")], "client_a", source_key="generated")

    rows = store.read_performance_ledger("client_a").sort_values("ledger_sequence")
    assert rows["ledger_sequence"].tolist() == [1, 2]
    assert rows.iloc[1]["previous_row_hash"] == rows.iloc[0]["row_hash"]
    assert store.LEDGER_CSV_PATH.exists()
    assert store.LEDGER_JSON_PATH.exists()
    assert pd.read_csv(store.LEDGER_CSV_PATH).shape[0] == 2
    assert len(json.loads(store.LEDGER_JSON_PATH.read_text(encoding="utf-8"))["rows"]) == 2
    assert any(path.name.startswith("proof_performance_ledger.csv") for path in store.BACKUP_DIR.iterdir())
    assert any(path.name.startswith("proof_performance_ledger.json") for path in store.BACKUP_DIR.iterdir())
    assert store.validate_ledger_integrity()["status"] == "PASS"


def test_correction_rows_append_without_mutating_original(isolated_ledger):
    original = store.append_performance_rows([_base_row()], "client_a", source_key="generated")["added_rows"][0]
    correction = _base_row(
        record_type="correction",
        corrected_from_proof_id=original["proof_id"],
        correction_reason="grading correction",
        result="loss",
        locked_at_utc="2026-06-29T10:00:00Z",
    )

    result = store.append_performance_rows([correction], "client_a", source_key="correction_record")
    rows = store.read_performance_ledger("client_a").sort_values("ledger_sequence")

    assert result["rows_to_add"] == 1
    assert result["correction_rows_detected"] == 1
    assert len(rows) == 2
    assert rows.iloc[0]["result"] == "win"
    assert rows.iloc[0]["proof_id"] == original["proof_id"]
    assert rows.iloc[1]["record_type"] == "correction"
    assert rows.iloc[1]["corrected_from_proof_id"] == original["proof_id"]
    assert rows.iloc[1]["proof_id"] != original["proof_id"]


def test_private_and_public_exports_redact_internal_fields(isolated_ledger):
    store.append_performance_rows([_base_row(source_file="/private/source.csv")], "client_a", source_key="uploaded_csv", source_file="/private/source.csv")

    private_csv = store.export_performance_csv("client_a")
    private_json = store.export_performance_json("client_a")
    public_csv = store.export_performance_csv("client_a", public_safe=True)
    public_json = store.export_performance_json("client_a", public_safe=True)

    assert "source_file" in private_csv
    assert "previous_row_hash" in private_csv
    assert "source_file" not in public_csv
    assert "previous_row_hash" not in public_csv
    assert "proof_id" in public_csv
    assert "row_hash" in public_csv
    assert "source_file" in private_json
    assert "source_file" not in public_json
    assert "John Doe" not in public_json
    assert "NY Liberty -120" not in public_json


def test_empty_and_malformed_ledger_safety_path(isolated_ledger):
    assert store.read_performance_ledger().empty
    store.LEDGER_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    store.LEDGER_JSON_PATH.write_text("{not-valid-json", encoding="utf-8")

    frame = store.read_performance_ledger()
    integrity = store.validate_ledger_integrity()

    assert frame.empty
    assert integrity["rows_checked"] == 0
    assert integrity["warnings"]
