import json

from autonomous_betting_agent import offline_update_package_builder as builder


def _locked_row():
    return {
        "proof_id": "p1",
        "sport": "tennis",
        "league": "wta",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "market_type": "moneyline",
        "selection": "A",
    }


def _match_report(status="MATCHED", review=False):
    return {
        "match_rows": [
            {
                "locked_row_id": "locked:proof_id:p1",
                "locked_event": "A vs B",
                "status": status,
                "best_score": 0.97,
                "best_provider_event_id": "provider:event_id:e1",
                "best_provider_event": "A vs B",
                "manual_review_required": review,
                "reasons": [],
            }
        ]
    }


def _confirmation():
    return {"provider_event_id": "provider:event_id:e1", "provider": "sportsdataio", "primary_value": 2, "secondary_value": 0, "confirmed_at_utc": "2026-06-29T22:00:00Z"}


def _value():
    return {"provider_event_id": "provider:event_id:e1", "provider": "the_odds_api", "original_value": 2.0, "latest_value": 1.9}


def test_parse_helpers_accept_csv_and_json():
    rows = builder.parse_csv_text("proof_id,event\np1,A vs B\n")
    obj = builder.parse_json_object('{"match_rows": []}')
    list_rows = builder.parse_json_rows('[{"a": 1}]')

    assert rows == [{"proof_id": "p1", "event": "A vs B"}]
    assert obj == {"match_rows": []}
    assert list_rows == [{"a": 1}]


def test_csv_from_rows_keeps_headers():
    text = builder.csv_from_rows([{"a": 1, "b": 2}], ["a", "b"])
    assert "a,b" in text
    assert "1,2" in text


def test_package_rows_updates_matched_rows_only():
    result = builder.build_package_rows([_locked_row()], _match_report(), [_confirmation()], [_value()])
    row = result["updated_rows"][0]

    assert row["verification_status"] == "ready_for_manual_import"
    assert row["confirmation_value"] == "2-0"
    assert row["latest_value"] == "1.9"
    assert result["diff_rows"][0]["status"] == "READY"
    assert result["verified_learning_rows"][0]["learning_status"] == "verified_ready"
    assert result["manual_review_rows"] == []


def test_package_rows_routes_review_rows_to_manual_review():
    result = builder.build_package_rows([_locked_row()], _match_report("LOW CONFIDENCE", True), [], [])

    assert result["updated_rows"][0]["verification_status"] == "manual_review_required"
    assert result["diff_rows"] == []
    assert result["verified_learning_rows"] == []
    assert result["manual_review_rows"][0]["status"] == "LOW CONFIDENCE"


def test_build_offline_update_package_outputs_all_expected_files():
    package = builder.build_offline_update_package("test_01", [_locked_row()], _match_report(), [_confirmation()], [_value()])

    assert package["schema_version"] == "offline_update_package_v1"
    assert package["status"] == "PACKAGE READY"
    assert package["locked_row_count"] == 1
    assert package["changed_row_count"] == 1
    assert package["manual_review_count"] == 0
    assert package["verified_learning_count"] == 1
    assert package["preview_only"] is True
    assert package["files_written"] == 0
    assert "backup_csv" in package
    assert "updated_csv_preview" in package
    assert "rollback_csv" in package
    assert "audit_json" in package
    assert package["package_hash"].startswith("offline_package_hash_")


def test_build_offline_update_package_from_text_round_trips():
    locked_csv = "proof_id,sport,league,event,event_start_utc,market_type,selection\np1,tennis,wta,A vs B,2026-06-29T20:00:00Z,moneyline,A\n"
    package = builder.build_offline_update_package_from_text(
        "test_01",
        locked_csv,
        json.dumps(_match_report()),
        json.dumps([_confirmation()]),
        json.dumps([_value()]),
    )

    assert package["changed_row_count"] == 1
    assert "ready_for_manual_import" in package["updated_csv_preview"]


def test_manifest_export_excludes_large_csv_blocks():
    package = builder.build_offline_update_package("test_01", [_locked_row()], _match_report(), [_confirmation()], [_value()])
    manifest = json.loads(builder.export_package_manifest_json(package))

    assert "backup_csv" not in manifest
    assert "updated_csv_preview" not in manifest
    assert "rollback_csv" not in manifest
    assert manifest["changed_row_count"] == 1


def test_empty_package_requires_rows():
    package = builder.build_offline_update_package("test_01", [], {}, [], [])

    assert package["status"] == "NO ROWS"
    assert package["errors"]


def test_package_service_has_no_external_client_paths():
    source = open("autonomous_betting_agent/offline_update_package_builder.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
