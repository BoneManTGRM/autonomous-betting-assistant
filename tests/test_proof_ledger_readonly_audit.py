import json

from autonomous_betting_agent import proof_ledger_readonly_audit as audit


def _proof_rows():
    return [
        {"proof_id": "p1", "event_id": "e1", "event": "A vs B", "selection": "A", "decimal_odds": "2.00", "model_probability": "60%", "result": "win", "sport": "tennis", "league": "atp"},
        {"proof_id": "p2", "event_id": "e1", "event": "A vs B", "selection": "B", "decimal_odds": "1.90", "model_probability": "45%", "result": "loss", "sport": "tennis", "league": "atp"},
        {"proof_id": "p3", "event_id": "e2", "event": "C vs D", "selection": "C", "decimal_odds": "1.80", "model_probability": "55%", "result": "push", "sport": "wnba", "league": "wnba"},
    ]


def _page_rows():
    return [
        {"page": "Pro Predictor", "role": "predictor", "source": "canonical shared proof store", "mutation_flag": "read only"},
        {"page": "Odds Lock Pro", "role": "odds_lock", "source": "canonical shared proof store", "mutation_flag": "read only"},
        {"page": "Public Proof Dashboard", "role": "dashboard", "source": "canonical shared proof store", "mutation_flag": "read only"},
        {"page": "Learning", "role": "learning", "source": "canonical shared proof store", "mutation_flag": "read only"},
    ]


def _store_rows():
    return [{"store": "proof_ledger", "role": "canonical primary", "mode": "read only audit"}]


def test_dataset_summary_counts_rows_events_and_results():
    summary = audit.summarize_dataset("proof", _proof_rows())

    assert summary["row_count"] == 3
    assert summary["unique_event_count"] == 2
    assert summary["duplicate_event_group_count"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["pushes"] == 1
    assert summary["dataset_fingerprint"].startswith("dataset_")


def test_duplicate_event_rows_reports_grouped_rows():
    duplicates = audit.duplicate_event_rows(_proof_rows())

    assert len(duplicates) == 1
    assert duplicates[0]["event_key"] == "e1"
    assert duplicates[0]["row_count"] == 2


def test_page_inventory_checks_pass_with_expected_roles():
    checks = audit.page_inventory_checks(_page_rows())

    assert any(row["check_id"] == "page_role_predictor" and row["status"] == "PASS" for row in checks)
    assert any(row["check_id"] == "canonical_source_declared" and row["status"] == "PASS" for row in checks)
    assert any(row["check_id"] == "page_mutation_flags" and row["status"] == "PASS" for row in checks)


def test_store_inventory_checks_pass_with_canonical_store():
    checks = audit.store_inventory_checks(_store_rows())

    assert any(row["check_id"] == "store_canonical_present" and row["status"] == "PASS" for row in checks)
    assert any(row["check_id"] == "store_unsafe_flags" and row["status"] == "PASS" for row in checks)


def test_handoff_checks_warn_when_counts_disagree():
    proof = audit.summarize_dataset("proof", _proof_rows())
    learning = audit.summarize_dataset("learning", _proof_rows()[:2])
    checks = audit.handoff_checks(proof, [proof, learning])

    assert any(row["status"] == "WARN" for row in checks)


def test_build_proof_ledger_readonly_audit_from_text_exports():
    proof_csv = audit.csv_from_rows(_proof_rows())
    page_csv = audit.csv_from_rows(_page_rows())
    store_csv = audit.csv_from_rows(_store_rows())
    report = audit.build_proof_ledger_readonly_audit_from_text(
        "test_01",
        proof_csv,
        proof_csv,
        proof_csv,
        "",
        page_csv,
        store_csv,
        '{"preview_only": true, "live_changes": 0}',
    )
    payload = json.loads(audit.export_proof_audit_json(report))

    assert payload["schema_version"] == "proof_ledger_readonly_audit_v1"
    assert payload["proof_row_count"] == 3
    assert payload["learning_row_count"] == 3
    assert payload["dashboard_row_count"] == 3
    assert payload["page_inventory_count"] == 4
    assert payload["store_inventory_count"] == 1
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "check_id" in audit.export_proof_audit_checks_csv(report)
    assert "dataset_name" in audit.export_proof_audit_summaries_csv(report)
    assert "event_key" in audit.export_proof_audit_duplicates_csv(report)
    assert "audit_hash" in audit.export_proof_audit_manifest_json(report)


def test_parse_json_object_handles_invalid_json():
    assert audit.parse_json_object("not json")["parse_error"] == "invalid_json"


def test_proof_audit_has_no_external_client_paths():
    source = open("autonomous_betting_agent/proof_ledger_readonly_audit.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
