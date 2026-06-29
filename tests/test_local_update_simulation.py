import json

from autonomous_betting_agent import local_update_simulation as sim


def _locked_csv():
    return "proof_id,sport,league,event,event_start_utc,market_type,selection\np1,tennis,wta,A vs B,2026-06-29T20:00:00Z,moneyline,A\n"


def _provider_events():
    return [
        {
            "event_id": "e1",
            "sport": "tennis",
            "league": "wta",
            "event": "A vs B",
            "commence_time": "2026-06-29T20:05:00Z",
            "market_type": "moneyline",
            "selection": "A",
        }
    ]


def _confirmation_rows():
    return [{"provider_event_id": "provider:event_id:e1", "provider": "sportsdataio", "primary_value": 2, "secondary_value": 0, "confirmed_at_utc": "2026-06-29T22:00:00Z"}]


def _value_rows():
    return [{"provider_event_id": "provider:event_id:e1", "provider": "the_odds_api", "original_value": 2.0, "latest_value": 1.9}]


def _payloads():
    return {
        "the_odds_api": [{"home_team": "A", "away_team": "B", "bookmakers": [{"markets": [{"outcomes": [{"price": 2.0}]}]}]}],
        "sportsdataio": [{"name": "A vs B", "home_score": 2, "away_score": 0}],
        "weatherapi": {"location": {"name": "X"}, "current": {"temp_c": 20}},
    }


def test_build_smoke_summary_counts_payloads():
    summary = sim.build_smoke_summary(_payloads())

    assert summary["ready_provider_count"] == 3
    assert summary["review_provider_count"] == 0
    assert summary["status"] == "API READY"


def test_build_local_update_simulation_chains_all_stages():
    report = sim.build_local_update_simulation(
        "test_01",
        [{"proof_id": "p1", "sport": "tennis", "league": "wta", "event": "A vs B", "event_start_utc": "2026-06-29T20:00:00Z", "market_type": "moneyline", "selection": "A"}],
        _provider_events(),
        _confirmation_rows(),
        _value_rows(),
        _payloads(),
    )

    assert report["schema_version"] == "local_update_simulation_v1"
    assert report["locked_row_count"] == 1
    assert report["provider_event_count"] == 1
    assert report["ready_provider_count"] == 3
    assert report["matched_count"] == 1
    assert report["package_changed_count"] >= 0
    assert report["intake_verified_count"] >= 0
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["proof_rows_changed"] == 0
    assert report["simulation_hash"].startswith("local_sim_hash_")


def test_build_local_update_simulation_from_text_round_trips():
    report = sim.build_local_update_simulation_from_text(
        "test_01",
        _locked_csv(),
        json.dumps(_provider_events()),
        json.dumps(_confirmation_rows()),
        json.dumps(_value_rows()),
        json.dumps(_payloads()["the_odds_api"]),
        json.dumps(_payloads()["sportsdataio"]),
        json.dumps(_payloads()["weatherapi"]),
    )

    assert report["locked_row_count"] == 1
    assert report["matched_count"] == 1
    assert "match_report" in report
    assert "offline_package" in report
    assert "adaptive_intake" in report


def test_empty_simulation_reports_no_rows():
    report = sim.build_local_update_simulation("test_01", [], [], [], [], {})

    assert report["status"] == "NO ROWS"
    assert report["errors"]


def test_review_simulation_flags_unsafe_flow():
    report = sim.build_local_update_simulation(
        "test_01",
        [{"proof_id": "p1", "event": "A vs B"}],
        [],
        [],
        [],
        {},
    )

    assert report["status"] == "REVIEW REQUIRED"
    assert report["review_flags"]


def test_export_simulation_manifest_removes_large_csv_blocks():
    report = sim.build_local_update_simulation_from_text(
        "test_01",
        _locked_csv(),
        json.dumps(_provider_events()),
        json.dumps(_confirmation_rows()),
        json.dumps(_value_rows()),
        json.dumps(_payloads()["the_odds_api"]),
        json.dumps(_payloads()["sportsdataio"]),
        json.dumps(_payloads()["weatherapi"]),
    )
    manifest = json.loads(sim.export_simulation_manifest_json(report))

    assert "offline_package" in manifest
    assert "backup_csv" not in manifest["offline_package"]
    assert "updated_csv_preview" not in manifest["offline_package"]
    assert "rollback_csv" not in manifest["offline_package"]


def test_local_simulation_service_has_no_external_client_paths():
    source = open("autonomous_betting_agent/local_update_simulation.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
