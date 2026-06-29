import json
from pathlib import Path

import pandas as pd

from autonomous_betting_agent import proof_package_service as svc


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "schema_version": "3E.9.0",
                "proof_id": "proof-alpha",
                "workspace_id": "test_01",
                "ledger_sequence": 1,
                "record_type": "import",
                "event": "Alpha vs Beta",
                "market_type": "h2h",
                "pick": "Alpha ML",
                "sportsbook": "Book A",
                "decimal_odds": 2.10,
                "model_probability": 0.61,
                "raw_implied_probability": 0.51,
                "no_vig_implied_probability": 0.53,
                "edge": 0.10,
                "no_vig_edge": 0.08,
                "expected_value": 0.281,
                "clv": 0.04,
                "stake_units": 1.0,
                "result": "win",
                "profit_units": 1.10,
                "report_lane": "playable",
                "odds_verified": True,
                "duplicate_key": "dup-alpha",
                "row_hash": "row-alpha",
                "previous_row_hash": "row-private-prev",
                "source_file": "/home/private/source.csv",
                "correction_reason": "private note",
            },
            {
                "schema_version": "3E.9.0",
                "proof_id": "proof-watch",
                "workspace_id": "test_01",
                "ledger_sequence": 2,
                "record_type": "import",
                "event": "Gamma vs Delta",
                "market_type": "spreads",
                "pick": "Gamma +2.5",
                "sportsbook": "Book B",
                "decimal_odds": 1.91,
                "model_probability": 0.55,
                "edge": 0.03,
                "expected_value": 0.0505,
                "clv": -0.01,
                "stake_units": 1.0,
                "result": "loss",
                "profit_units": -1.0,
                "report_lane": "watchlist",
                "odds_verified": True,
                "duplicate_key": "dup-watch",
                "row_hash": "row-watch",
            },
        ]
    )


def _public_rows() -> list[dict]:
    return [
        {
            "proof_id": "proof-alpha",
            "workspace_id": "test_01",
            "event": "Alpha vs Beta",
            "market_type": "h2h",
            "pick": "Alpha ML",
            "sportsbook": "Book A",
            "decimal_odds": 2.10,
            "model_probability": 0.61,
            "edge": 0.10,
            "no_vig_edge": 0.08,
            "expected_value": 0.281,
            "clv": 0.04,
            "stake_units": 1.0,
            "result": "win",
            "profit_units": 1.10,
            "report_lane": "playable",
            "odds_verified": True,
            "duplicate_key": "dup-alpha",
            "row_hash": "row-alpha",
        },
        {
            "proof_id": "proof-watch",
            "workspace_id": "test_01",
            "event": "Gamma vs Delta",
            "market_type": "spreads",
            "pick": "Gamma +2.5",
            "sportsbook": "Book B",
            "decimal_odds": 1.91,
            "model_probability": 0.55,
            "edge": 0.03,
            "expected_value": 0.0505,
            "clv": -0.01,
            "stake_units": 1.0,
            "result": "loss",
            "profit_units": -1.0,
            "report_lane": "watchlist",
            "odds_verified": True,
            "duplicate_key": "dup-watch",
            "row_hash": "row-watch",
        },
    ]


def _summary(total_rows: int = 2) -> dict:
    return {
        "total_rows": total_rows,
        "total_active_rows": total_rows,
        "unique_events": total_rows,
        "duplicate_count": 0,
        "correction_count": 0,
        "wins": 1 if total_rows else 0,
        "losses": 1 if total_rows > 1 else 0,
        "pushes": 0,
        "cancels": 0,
        "win_rate_ex_push_cancel": 0.5 if total_rows else 0.0,
        "profit_units": 0.10 if total_rows else 0.0,
        "risked_units": 2.0 if total_rows else 0.0,
        "roi": 0.05 if total_rows else 0.0,
        "average_clv": 0.015 if total_rows else None,
        "last_updated_timestamp": "2026-06-29T12:00:00Z",
        "schema_version": "3E.9.0",
        "ledger_integrity_status": "PASS",
        "ledger_integrity": {"status": "PASS", "warnings": [], "errors": []},
    }


def _patch_populated(monkeypatch, *, selected_source="ledger", dashboard_ready=True, integrity_status="PASS", public_json_bad=False):
    rows = _rows()
    monkeypatch.setattr(svc, "rows_for_dashboard", lambda workspace_id=None: rows)
    monkeypatch.setattr(svc, "summarize_performance", lambda workspace_id=None: _summary(2))
    monkeypatch.setattr(svc, "validate_ledger_integrity", lambda workspace_id=None: {"status": integrity_status, "rows_checked": 2, "warnings": [], "errors": [] if integrity_status == "PASS" else ["bad chain"], "schema_version": "3E.9.0"})
    monkeypatch.setattr(svc, "get_proof_center_status", lambda workspace_id=None: {"warnings": [], "errors": []})
    monkeypatch.setattr(svc, "get_ledger_health", lambda workspace_id=None: {"status": integrity_status, "last_sequence": 2, "last_row_hash": "row-watch", "warnings": [], "errors": [] if integrity_status == "PASS" else ["bad chain"]})
    monkeypatch.setattr(svc, "get_dashboard_readiness", lambda workspace_id=None: {"dashboard_ready": dashboard_ready, "dashboard_selected_source": selected_source, "ledger_rows": 2, "dashboard_rows": 2, "warnings": [], "errors": []})

    def export_json(workspace_id=None, public_safe=False):
        if public_safe:
            public_rows = _public_rows()
            if public_json_bad:
                public_rows[0]["source_file"] = "/home/private/source.csv"
            return json.dumps({"schema_version": "3E.9.0", "rows": public_rows}, sort_keys=True)
        return json.dumps({"schema_version": "3E.9.0", "rows": rows.to_dict(orient="records")}, sort_keys=True)

    def export_csv(workspace_id=None, public_safe=False):
        frame = pd.DataFrame(_public_rows()) if public_safe else rows
        return frame.to_csv(index=False)

    monkeypatch.setattr(svc, "export_performance_json", export_json)
    monkeypatch.setattr(svc, "export_performance_csv", export_csv)


def _patch_empty(monkeypatch):
    monkeypatch.setattr(svc, "rows_for_dashboard", lambda workspace_id=None: pd.DataFrame())
    monkeypatch.setattr(svc, "summarize_performance", lambda workspace_id=None: _summary(0))
    monkeypatch.setattr(svc, "validate_ledger_integrity", lambda workspace_id=None: {"status": "PASS", "rows_checked": 0, "warnings": [], "errors": [], "schema_version": "3E.9.0"})
    monkeypatch.setattr(svc, "get_proof_center_status", lambda workspace_id=None: {"warnings": [], "errors": []})
    monkeypatch.setattr(svc, "get_ledger_health", lambda workspace_id=None: {"status": "PASS", "last_sequence": 0, "last_row_hash": "", "warnings": [], "errors": []})
    monkeypatch.setattr(svc, "get_dashboard_readiness", lambda workspace_id=None: {"dashboard_ready": False, "dashboard_selected_source": "empty", "ledger_rows": 0, "dashboard_rows": 0, "warnings": [], "errors": []})
    monkeypatch.setattr(svc, "export_performance_json", lambda workspace_id=None, public_safe=False: json.dumps({"schema_version": "3E.9.0", "rows": []}, sort_keys=True))
    monkeypatch.setattr(svc, "export_performance_csv", lambda workspace_id=None, public_safe=False: "")


def test_public_package_builds_from_empty_ledger(monkeypatch):
    _patch_empty(monkeypatch)

    package = svc.build_public_proof_package("test_01")

    assert package["package_type"] == "public"
    assert package["proof_ready"] is False
    assert package["proof_grade"] == svc.EMPTY_GRADE
    assert package["total_rows"] == 0
    assert package["top_positive_ev_message"] == svc.NO_PLAYABLE_POSITIVE_EV_MESSAGE
    assert package["verification_manifest"]["proof_ready"] is False


def test_public_package_builds_from_populated_ledger_and_is_proof_ready(monkeypatch):
    _patch_populated(monkeypatch)

    package = svc.build_public_proof_package("test_01")

    assert package["package_schema_version"] == svc.PACKAGE_SCHEMA_VERSION
    assert package["package_hash"].startswith("pkg_hash_")
    assert package["public_export_hash"].startswith("export_hash_")
    assert package["proof_ready"] is True
    assert package["proof_grade"] == svc.PROOF_READY_GRADE
    assert package["ledger_backed"] is True
    assert package["verification_manifest"]["package_hash"] == package["package_hash"]
    assert package["verification_manifest"]["public_export_hash"] == package["public_export_hash"]


def test_private_and_internal_packages_include_audit_fields(monkeypatch):
    _patch_populated(monkeypatch)

    private_package = svc.build_private_audit_package("test_01")
    internal_package = svc.build_internal_review_package("test_01")

    for package in (private_package, internal_package):
        assert "private_export_csv" in package
        assert "private_export_json" in package
        assert "private_export_hash" in package
        assert "audit_manifest" in package
        assert "ledger_health" in package
        assert "dashboard_readiness" in package
        assert "integrity_validation_result" in package
        assert "row_hash_verification_summary" in package
        assert package["private_export_hash"].startswith("export_hash_")


def test_client_package_excludes_private_audit_fields(monkeypatch):
    _patch_populated(monkeypatch)

    package = svc.build_client_summary_package("test_01")
    payload = svc.export_proof_package_json(package)

    assert package["package_type"] == "client"
    assert "private_export_csv" not in payload
    assert "private_export_json" not in payload
    assert "source_file" not in payload
    assert "previous_row_hash" not in payload
    assert "correction_reason" not in payload


def test_public_json_and_markdown_redact_private_fields(monkeypatch):
    _patch_populated(monkeypatch)

    package = svc.build_public_proof_package("test_01")
    json_text = svc.export_proof_package_json(package)
    markdown_text = svc.export_proof_package_markdown(package)

    for text in (json_text, markdown_text):
        assert "source_file" not in text
        assert "previous_row_hash" not in text
        assert "correction_reason" not in text
        assert "private_export_csv" not in text
        assert "private_export_json" not in text
        assert "/home/" not in text


def test_public_package_redaction_validation_blocks_private_terms_and_paths(monkeypatch):
    _patch_populated(monkeypatch)
    package = svc.build_public_proof_package("test_01")
    package["source_file"] = "/home/private/file.csv"
    package["api_key"] = "abc"
    package["token"] = "bearer secret"
    package["correction_reason"] = "private correction"

    result = svc.validate_public_package_redactions(package)

    assert result["passed"] is False
    assert result["blocked_terms_found"]
    assert result["blocked_paths_found"]
    assert set(result["checked_outputs"]) == {"package", "json", "markdown", "csv_bundle"}


def test_hashes_are_stable_without_generated_at_and_change_when_rows_change(monkeypatch):
    _patch_populated(monkeypatch)
    package = svc.build_public_proof_package("test_01")
    changed_time = dict(package)
    changed_time["generated_at_utc"] = "2099-01-01T00:00:00Z"

    assert svc.build_package_hash(package) == svc.build_package_hash(changed_time)

    changed_rows = dict(package)
    changed_rows["public_safe_rows"] = package["public_safe_rows"] + [{"proof_id": "proof-new", "row_hash": "row-new"}]
    assert svc.build_package_hash(package) != svc.build_package_hash(changed_rows)


def test_proof_ready_false_when_fallback_integrity_or_redaction_fail(monkeypatch):
    _patch_populated(monkeypatch, selected_source="uploaded")
    fallback_package = svc.build_public_proof_package("test_01")
    assert fallback_package["proof_ready"] is False
    assert fallback_package["proof_grade"] == svc.PROVISIONAL_GRADE

    _patch_populated(monkeypatch, integrity_status="FAIL")
    fail_package = svc.build_public_proof_package("test_01")
    assert fail_package["proof_ready"] is False
    assert fail_package["proof_grade"] != svc.PROOF_READY_GRADE

    _patch_populated(monkeypatch, public_json_bad=True)
    redaction_package = svc.build_public_proof_package("test_01")
    assert redaction_package["proof_ready"] is False
    assert redaction_package["redaction_status"]["passed"] is False


def test_top_ev_package_excludes_watchlist_and_empty_state_is_honest(monkeypatch):
    _patch_populated(monkeypatch)
    package = svc.build_public_proof_package("test_01")

    assert len(package["top_positive_ev_picks"]) == 1
    assert package["top_positive_ev_picks"][0]["event"] == "Alpha vs Beta"
    assert "watch" not in str(package["top_positive_ev_picks"][0].get("report_lane", "")).lower()

    _patch_empty(monkeypatch)
    empty = svc.build_public_proof_package("test_01")
    assert empty["top_positive_ev_picks"] == []
    assert empty["top_positive_ev_message"] == svc.NO_PLAYABLE_POSITIVE_EV_MESSAGE


def test_csv_bundle_modes_and_no_disk_writes(monkeypatch, tmp_path):
    _patch_populated(monkeypatch)
    public = svc.build_public_proof_package("test_01")
    private = svc.build_private_audit_package("test_01")

    public_bundle = svc.export_proof_package_csv_bundle(public)
    private_bundle = svc.export_proof_package_csv_bundle(private)

    assert isinstance(public_bundle, dict)
    assert "public_safe_proof_rows.csv" in public_bundle
    assert "private_audit_proof_rows.csv" not in public_bundle
    assert "private_audit_proof_rows.csv" in private_bundle
    assert list(Path(tmp_path).iterdir()) == []


def test_package_service_does_not_import_or_call_write_paths():
    source = Path("autonomous_betting_agent/proof_package_service.py").read_text(encoding="utf-8")
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "mutate_result",
        "update_result",
        "delete_proof",
    )
    for token in forbidden:
        assert token not in source
    assert "John Doe" not in source
    assert "NY Liberty -120" not in source
