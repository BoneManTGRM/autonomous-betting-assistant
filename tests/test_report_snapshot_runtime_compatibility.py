"""Snapshot status and runtime bridge contracts; all provider IO is synthetic."""
from copy import deepcopy
from unittest.mock import patch

from autonomous_betting_agent import magazine_live_api_enrichment as live
from autonomous_betting_agent import balldontlie_integration as bdl
from autonomous_betting_agent import magazine_provider_usage_patch as usage


def row(**fields):
    return {"event": "North Lake vs East Harbor", "sport": "NBA", **fields}


def test_pure_snapshot_status_never_reads_keys_or_changes_input():
    for metadata in ({}, {"demonstration_mode": True}, {"source_file": "demo_ledger"},
                     {"report_title": "Validation fixture"}, {"source_mode": "synthetic_fixture"}):
        original = row(**metadata)
        before = deepcopy(original)
        with patch.object(live, "_secret", side_effect=AssertionError("No key lookup in pure snapshot")), \
             patch.object(live, "_request_json", side_effect=AssertionError("No network")):
            result = live.prepare_report_snapshot_row(original)
        assert original == before
        assert result["live_api_enrichment_status"] == ("DEMONSTRATION_ONLY" if metadata else "PROVIDED_DATA_ONLY")
        assert result["report_provider_calls_allowed"] is False


def test_legacy_facade_retains_explicit_status_without_provider_dispatch():
    for configured in ("", "synthetic-configured-key"):
        original = row(sportsdataio_status="SAVED_OBSERVATION")
        with patch.object(live, "_secret", return_value=configured), \
             patch.object(live, "_request_json", side_effect=AssertionError("No provider IO")), \
             patch.object(bdl, "_request_json", side_effect=AssertionError("No BDL IO")):
            result = live.enrich_row_with_live_api_data(original)
        assert result["sportsdataio_status"] == "SAVED_OBSERVATION"
        assert result["news_status"] == ("REPORT_REFRESH_DISABLED" if configured else "API_KEY_MISSING")
        assert "report_provider_calls_allowed" not in original
        assert result["report_provider_calls_allowed"] is False
        assert "matchup_notes" not in result


def test_provider_bridge_keeps_snapshot_aware_callable_and_helpers():
    before = live.enrich_row_with_live_api_data
    weather = live._enrich_weather
    usage.install()
    assert live.enrich_row_with_live_api_data is before
    assert live._enrich_weather is weather
    # An explicit caller must reach the supported implementation, not the old
    # interceptor whose signature rejects the refresh keyword.
    with patch.object(live, "_secret", return_value=""), \
         patch.object(bdl, "_secret", return_value=""), \
         patch.object(live, "_request_json", side_effect=AssertionError("No keys")):
        result = live.enrich_row_with_live_api_data(row(), allow_provider_refresh=True)
    assert result["sportsdataio_status"] == "API_KEY_MISSING"


def test_balldontlie_honors_report_no_call_and_demo_before_key_lookup():
    for metadata in ({"report_provider_calls_allowed": False}, {"demonstration_mode": True}):
        original = row(**metadata)
        with patch.object(bdl, "_secret", side_effect=AssertionError("Snapshot does not need keys")), \
             patch.object(bdl, "_request_json", side_effect=AssertionError("No BDL IO")):
            result = bdl.enrich_row_with_balldontlie(original)
        assert result["balldontlie_status"] == "REPORT_REFRESH_DISABLED"
        assert "balldontlie_status" not in original


def test_bootstrap_preserves_sale_gate_contract():
    from autonomous_betting_agent import magazine_sale_ready_patch as sale
    from autonomous_betting_agent import report_studio_bootstrap as bootstrap
    before = sale._force_truthful_gate
    bootstrap.install()
    assert sale._force_truthful_gate is before
    demo = sale._force_truthful_gate(row(demonstration_mode=True))
    assert demo["final_decision"] == "DEMONSTRATION ONLY"
    assert demo["target_stake_units"] == "0.0"
    assert demo["live_verified_stake_units"] == "0.0"


def test_many_legacy_wrappers_cannot_refresh_report_snapshots_with_keys():
    original = [row(), row(event="West Valley vs South Ridge")]
    before = deepcopy(original)
    with patch.object(live, "_secret", return_value="synthetic-configured-key"), \
         patch.object(live, "_request_json", side_effect=AssertionError("No provider IO")), \
         patch.object(bdl, "_secret", side_effect=AssertionError("Snapshot does not need BDL keys")), \
         patch.object(bdl, "_request_json", side_effect=AssertionError("No BDL IO")):
        result = live.enrich_rows_with_live_api_data(original)
    assert len(result) == 2
    assert all(item["report_provider_calls_allowed"] is False for item in result)
    assert all(item["live_api_enrichment_status"] == "PROVIDED_DATA_ONLY" for item in result)
    assert original == before


def test_explicit_nonreport_refresh_keeps_request_adapter_and_results():
    original = row(sport="Soccer", away_team="North Lake", home_team="East Harbor", venue="Synthetic Ground")
    with patch.object(live, "_secret", return_value="synthetic-configured-key"), \
         patch.object(bdl, "_secret", return_value=""), \
         patch.object(live, "_request_json", return_value={}) as requests:
        result = live.enrich_row_with_live_api_data(original, allow_provider_refresh=True)
    assert requests.call_count == 4  # Weather, news, and two football-team requests.
    assert {call.kwargs["cache_key"][0] for call in requests.call_args_list} == {"weather", "news", "api-football-team"}
    assert result["api_football_summary"].endswith("no match returned.")
    assert "_live_api_enriched" not in original


def test_explicit_bulk_refresh_keyword_survives_all_runtime_wrappers():
    original = [row(sport="Soccer", away_team="North Lake", home_team="East Harbor", venue="Synthetic Ground")]
    before = deepcopy(original)
    with patch.object(live, "_secret", return_value="synthetic-configured-key"), \
         patch.object(bdl, "_secret", return_value=""), \
         patch.object(live, "_request_json", return_value={}) as requests:
        result = live.enrich_rows_with_live_api_data(original, allow_provider_refresh=True)
    assert requests.call_count == 4
    assert {call.kwargs["cache_key"][0] for call in requests.call_args_list} == {"weather", "news", "api-football-team"}
    assert len(result) == 1
    assert result[0]["api_football_summary"].endswith("no match returned.")
    assert original == before
