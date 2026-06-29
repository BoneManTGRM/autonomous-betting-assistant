import json

from autonomous_betting_agent import local_update_simulation as sim


def _locked():
    return [{
        "proof_id": "p1",
        "sport": "tennis",
        "league": "wta",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "market_type": "moneyline",
        "selection": "A",
    }]


def _events():
    return [{
        "event_id": "e1",
        "sport": "tennis",
        "league": "wta",
        "event": "A vs B",
        "commence_time": "2026-06-29T20:05:00Z",
        "market_type": "moneyline",
        "selection": "A",
        "bookmakers": [{"markets": [{"outcomes": [{"price": 2.0}]}]}],
    }]


def _confirmations():
    return [{"provider_event_id": "provider:event_id:e1", "provider": "sportsdataio", "primary_value": 2, "secondary_value": 0, "confirmed_at_utc": "2026-06-29T22:00:00Z"}]


def _values():
    return [{"provider_event_id": "provider:event_id:e1", "provider": "the_odds_api", "original_value": 2.0, "latest_value": 1.9}]


def test_stage_summary_lists_all_stages():
    report = sim.build_local_update_simulation("test_01", _locked(), _events(), _confirmations(), _values(), secrets={"ODDS_API_KEY": "x", "SPORTSDATAIO_API_KEY": "y", "WEATHERAPI_KEY": "z"})
    stages = [row["stage"] for row in report["stage_summary"]]

    assert stages == ["api_smoke", "event_match", "offline_package", "adaptive_intake"]


def test_build_local_update_simulation_runs_full_chain():
    report = sim.build_local_update_simulation("test_01", _locked(), _events(), _confirmations(), _values(), secrets={"ODDS_API_KEY": "x", "SPORTSDATAIO_API_KEY": "y", "WEATHERAPI_KEY": "z"})

    assert report["schema_version"] == "local_update_simulation_v1"
    assert report["locked_row_count"] == 1
    assert report["provider_event_count"] == 1
    assert report["matched_count"] == 1
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0
    assert report["simulation_hash"].startswith("local_sim_hash_")
    assert "backup_csv" in report["downloads"]
    assert "verified_lane_csv" in report["downloads"]


def test_build_local_update_simulation_from_text_round_trips():
    locked_csv = "proof_id,sport,league,event,event_start_utc,market_type,selection\np1,tennis,wta,A vs B,2026-06-29T20:00:00Z,moneyline,A\n"
    report = sim.build_local_update_simulation_from_text(
        "test_01",
        locked_csv,
        json.dumps(_events()),
        json.dumps(_confirmations()),
        json.dumps(_values()),
        "event,selection,confidence\nFuture Match,A,0.1\n",
        json.dumps([{"event": "Needs Review", "manual_review_required": True}]),
    )

    assert report["locked_row_count"] == 1
    assert report["shadow_lane_count"] >= 1
    assert report["review_lane_count"] >= 1


def test_export_simulation_manifest_removes_large_download_bodies():
    report = sim.build_local_update_simulation("test_01", _locked(), _events(), _confirmations(), _values(), secrets={"ODDS_API_KEY": "x", "SPORTSDATAIO_API_KEY": "y", "WEATHERAPI_KEY": "z"})
    manifest = json.loads(sim.export_simulation_manifest_json(report))

    assert manifest["workspace_id"] == "test_01"
    assert manifest["downloads"]["backup_csv"].startswith("available:")
    assert "proof_id" not in manifest["downloads"]["backup_csv"]


def test_empty_simulation_has_no_rows_status():
    report = sim.build_local_update_simulation("test_01", [], [], [], [], secrets={"ODDS_API_KEY": "x", "SPORTSDATAIO_API_KEY": "y", "WEATHERAPI_KEY": "z"})

    assert report["status"] == "NO ROWS"
    assert report["locked_row_count"] == 0


def test_local_simulation_has_no_external_client_paths():
    source = open("autonomous_betting_agent/local_update_simulation.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
