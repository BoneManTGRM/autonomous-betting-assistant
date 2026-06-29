import json

from autonomous_betting_agent import update_flow_service as flow


def _row(event="A vs B"):
    return {
        "proof_id": "p1",
        "sport": "tennis",
        "event": event,
        "event_start_utc": "2026-06-29T20:00:00Z",
        "market_type": "moneyline",
        "selection": "A",
    }


def test_build_provider_requests_preserves_locked_row_identity():
    requests = flow.build_provider_requests([_row()], "confirmation")
    assert requests[0]["source_row_id"] == "p1"
    assert requests[0]["event"] == "A vs B"


def test_fetch_provider_payloads_uses_injected_transport_only():
    def transport(request):
        return {"provider": "fake", "primary_value": 2, "secondary_value": 0, "confidence": 0.9}

    payloads = flow.fetch_provider_payloads(flow.build_provider_requests([_row()], "confirmation"), transport)
    assert payloads[0]["provider"] == "fake"
    assert payloads[0]["event"] == "A vs B"


def test_update_flow_ready_with_confirmations_and_values():
    row = _row()
    confirmation = {**row, "provider": "source_a", "primary_value": 2, "secondary_value": 0, "confidence": 0.95}
    value = {**row, "provider": "source_b", "original_value": 2.0, "latest_value": 1.9}
    report = flow.build_update_flow_report("test_01", [row], [confirmation], [value])
    assert report["status"] == "READY TO EXPORT"
    assert report["safe_to_export"] is True
    assert report["preview_only"] is True
    assert report["changed_records"] == 0
    assert report["ready_count"] == 1
    assert report["proposed_exports"][0]["confirmation_value"] == "2-0"


def test_update_flow_uses_injected_transports_to_build_full_preview():
    row = _row()

    def confirmation_transport(request):
        return {"provider": "source_a", "primary_value": 2, "secondary_value": 0, "confidence": 0.95}

    def value_transport(request):
        return {"provider": "source_b", "original_value": 2.0, "latest_value": 1.9}

    report = flow.build_update_flow_report("test_01", [row], confirmation_transport=confirmation_transport, value_transport=value_transport)
    assert report["status"] == "READY TO EXPORT"
    assert report["confirmation_payload_count"] == 1
    assert report["value_payload_count"] == 1
    assert report["proposed_exports"][0]["source"] == "source_a"


def test_update_flow_blocks_when_review_rows_remain():
    report = flow.build_update_flow_report("test_01", [_row()], [], [])
    assert report["status"] == "REVIEW REQUIRED"
    assert report["safe_to_export"] is False
    assert report["review_count"] == 1
    assert report["changed_records"] == 0


def test_update_flow_keeps_unique_event_and_row_counts_separate():
    row1 = _row()
    row2 = {**_row(), "proof_id": "p2", "market_type": "spread"}
    confirmation = {**row1, "primary_value": 2, "secondary_value": 0, "confidence": 0.95}
    value = {**row1, "original_value": 2.0, "latest_value": 1.9}
    report = flow.build_update_flow_report("test_01", [row1, row2], [confirmation], [value])
    assert report["row_count"] == 2
    assert report["unique_events"] == 1
    assert report["duplicate_row_count"] == 1


def test_dashboard_update_payload_is_sanitized_metrics_only():
    report = flow.build_update_flow_report("test_01", [_row()], [], [])
    payload = flow.build_dashboard_update_payload(report)
    assert "proposed_exports" not in payload
    assert payload["row_count"] == 1
    assert payload["review_count"] == 1
    assert payload["preview_only"] is True
    assert payload["changed_records"] == 0


def test_update_flow_exports_json_and_csv():
    report = flow.build_update_flow_report("test_01", [_row()], [], [])
    payload = json.loads(flow.export_update_flow_json(report))
    csv_text = flow.export_proposed_updates_csv(report)
    assert payload["schema_version"] == "update_flow_v1"
    assert "proof_id,row_key,source,confirmation_value" in csv_text
