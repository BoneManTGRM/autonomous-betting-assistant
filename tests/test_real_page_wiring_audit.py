import json

from autonomous_betting_agent import real_page_wiring_audit as wiring


def _wired_rows():
    return [
        {
            "page": "Pro Predictor",
            "role": "predictor",
            "path": "pages/pro_predictor_volume.py",
            "source_text": "st.session_state plus canonical_locked_ledger pro_predictor_latest_rows canonical_store_recovery disk_fallback reload row_count_match",
        },
        {
            "page": "Odds Lock Pro",
            "role": "odds_lock",
            "path": "pages/odds_lock_pro.py",
            "source_text": "odds_lock_pro_locked_rows canonical_store_recovery local_json_fallback save_reload fingerprint",
        },
        {
            "page": "Public Proof Dashboard",
            "role": "dashboard",
            "path": "pages/public_proof_share.py",
            "source_text": "public_proof_dashboard_refresh_rows canonical_locked_ledger fallback recovery reload",
        },
        {
            "page": "Learning",
            "role": "learning",
            "path": "pages/learn_memory_safe.py",
            "source_text": "ara_latest_predictions canonical_store_recovery fallback reload verification",
        },
    ]


def test_evaluate_page_wiring_detects_wired_page():
    result = wiring.evaluate_page_wiring(_wired_rows()[0])

    assert result["status"] == "WIRED"
    assert result["has_canonical_store_reference"] is True
    assert result["has_recovery_path"] is True
    assert result["uses_session_state"] is True
    assert result["session_state_only"] is False


def test_evaluate_page_wiring_blocks_session_state_only_page():
    result = wiring.evaluate_page_wiring({"page": "Legacy", "role": "dashboard", "source_text": "st.session_state latest rows only"})

    assert result["status"] == "BLOCKED"
    assert result["session_state_only"] is True
    assert any(risk["risk_id"] == "session_only" for risk in result["risks"])


def test_evaluate_page_wiring_blocks_no_rows_without_recovery():
    result = wiring.evaluate_page_wiring({"page": "Public Proof Dashboard", "role": "dashboard", "source_text": "No rows found. No proof rows or historical tracker rows found yet."})

    assert result["status"] == "BLOCKED"
    assert result["no_rows_without_recovery"] is True
    assert any(risk["risk_id"] == "no_rows_without_recovery" for risk in result["risks"])


def test_evaluate_page_wiring_blocks_unsafe_indicators():
    result = wiring.evaluate_page_wiring({"page": "Writer", "role": "dashboard", "source_text": "canonical_locked_ledger fallback unsafe_write forced_live"})

    assert result["status"] == "BLOCKED"
    assert result["unsafe_indicator_count"] >= 1
    assert any(risk["risk_id"] == "unsafe_indicator" for risk in result["risks"])


def test_build_real_page_wiring_audit_ready_for_wired_inventory():
    report = wiring.build_real_page_wiring_audit("test_01", _wired_rows())

    assert report["schema_version"] == "real_page_wiring_audit_v1"
    assert report["system_status"] == "CANONICAL WIRING READY"
    assert report["page_count"] == 4
    assert report["wired_count"] == 4
    assert report["blocked_count"] == 0
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0


def test_build_real_page_wiring_audit_from_text_exports():
    csv_text = wiring.csv_from_rows(_wired_rows())
    report = wiring.build_real_page_wiring_audit_from_text("test_01", csv_text)
    blocked_report = wiring.build_real_page_wiring_audit("test_01", [{"page": "Bad", "role": "dashboard", "source_text": "st.session_state no rows found"}])
    payload = json.loads(wiring.export_wiring_audit_json(report))

    assert payload["system_status"] == "CANONICAL WIRING READY"
    assert "page_name" in wiring.export_wiring_page_summary_csv(report)
    assert "risk_id" in wiring.export_wiring_risk_summary_csv(blocked_report)
    assert "check_id" in wiring.export_wiring_checks_csv(report)
    assert "wiring_hash" in wiring.export_wiring_manifest_json(report)


def test_build_real_page_wiring_audit_blocks_bad_inventory():
    report = wiring.build_real_page_wiring_audit("test_01", [{"page": "Bad", "role": "dashboard", "source_text": "st.session_state no rows found"}])

    assert report["system_status"] == "BLOCKED"
    assert report["blocked_count"] == 1
    assert any("canonical recovery" in action.lower() or "recovery attempt" in action.lower() for action in report["next_actions"])


def test_required_roles_warn_when_missing():
    report = wiring.build_real_page_wiring_audit("test_01", [_wired_rows()[0]])

    assert report["system_status"] == "REVIEW REQUIRED"
    assert report["warn_count"] >= 1


def test_real_page_wiring_audit_has_no_external_client_paths():
    source = open("autonomous_betting_agent/real_page_wiring_audit.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
