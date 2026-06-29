import json

from autonomous_betting_agent import api_smoke_test_service as smoke


def test_key_readiness_reports_loaded_without_values():
    rows = smoke.build_key_readiness_report({
        "ODDS_API_KEY": "abc",
        "SPORTSDATAIO_API_KEY": "def",
        "WEATHERAPI_KEY": "ghi",
    })

    assert all(row["present"] for row in rows)
    assert all(row["display_value"] == "loaded" for row in rows)
    assert "abc" not in str(rows)
    assert "def" not in str(rows)


def test_key_readiness_reports_missing_aliases():
    row = smoke.secret_key_status({}, "the_odds_api")

    assert row["present"] is False
    assert row["display_value"] == "missing"


def test_redacted_request_plans_do_not_expose_key_values():
    plans = smoke.build_redacted_request_plans({
        "ODDS_API_KEY": "odds-secret",
        "SPORTSDATAIO_API_KEY": "sports-secret",
        "WEATHERAPI_KEY": "weather-secret",
    })

    text = str(plans)
    assert "odds-secret" not in text
    assert "sports-secret" not in text
    assert "weather-secret" not in text
    assert "***" in text


def test_parse_json_payload_handles_empty_and_invalid():
    assert smoke.parse_json_payload("") is None
    assert smoke.parse_json_payload("not json") == {"parse_error": "invalid_json"}
    assert smoke.parse_json_payload('{"ok": true}') == {"ok": True}


def test_analyze_the_odds_payload_ready_when_event_and_odds_exist():
    result = smoke.analyze_provider_payload("the_odds_api", [{
        "home_team": "A",
        "away_team": "B",
        "bookmakers": [{"markets": [{"outcomes": [{"price": 2.0}]}]}],
        "commence_time": "2026-06-29T20:00:00Z",
    }])

    assert result["status"] == "API READY"
    assert result["has_event_fields"] is True
    assert result["has_odds_fields"] is True
    assert result["record_count"] == 1


def test_analyze_sportsdata_payload_ready_when_scores_exist():
    result = smoke.analyze_provider_payload("sportsdataio", [{
        "Name": "A vs B",
        "home_score": 2,
        "away_score": 0,
    }])

    assert result["status"] == "API READY"
    assert result["has_score_fields"] is True


def test_analyze_payload_review_when_error_or_missing_shape():
    assert smoke.analyze_provider_payload("the_odds_api", {"error": "bad"})["status"] == "REVIEW REQUIRED"
    assert smoke.analyze_provider_payload("the_odds_api", {"nothing": True})["status"] == "REVIEW REQUIRED"


def test_build_api_smoke_report_ready_when_all_keys_and_payloads_valid():
    report = smoke.build_api_smoke_report(
        "test_01",
        {"ODDS_API_KEY": "a", "SPORTSDATAIO_API_KEY": "b", "WEATHERAPI_KEY": "c"},
        {
            "the_odds_api": [{"home_team": "A", "away_team": "B", "bookmakers": [{"markets": [{"outcomes": [{"price": 2.0}]}]}]}],
            "sportsdataio": [{"name": "A vs B", "home_score": 2, "away_score": 0}],
            "weatherapi": {"location": {"name": "X"}, "current": {"temp_c": 20}},
        },
    )

    assert report["status"] == "API READY"
    assert report["ready_provider_count"] == 3
    assert report["missing_key_count"] == 0
    assert report["preview_only"] is True
    assert report["proof_rows_changed"] == 0


def test_build_api_smoke_report_missing_key_blocks_ready():
    report = smoke.build_api_smoke_report("test_01", {}, {})

    assert report["status"] == "MISSING KEYS"
    assert report["missing_key_count"] == 3
    assert report["proof_rows_changed"] == 0


def test_export_api_smoke_report_json_round_trips():
    report = smoke.build_api_smoke_report("test_01", {}, {})
    payload = json.loads(smoke.export_api_smoke_report_json(report))

    assert payload["schema_version"] == "api_smoke_test_v1"
    assert payload["workspace_id"] == "test_01"


def test_api_smoke_service_has_no_direct_network_or_proof_change_paths():
    source = open("autonomous_betting_agent/api_smoke_test_service.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + ".", "append_" + "performance_rows", "sync_rows" + "_by_source", "approve_" + "ledger_import"):
        assert token not in source
