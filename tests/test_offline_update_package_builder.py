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

    assert rows[0]["proof_id"] == "p1"
    assert "match_rows" in obj
    assert list_rows[0]["a"] == 1


def test_csv_from_rows_keeps_headers():
    text = builder.csv_from_rows([{"a": 1, "b": 2}], ["a", "b"])
    assert "a,b" in text


def test_package_rows_separates_ready_and_review_rows():
    ready = builder.build_package_rows([_locked_row()], _match_report(), [_confirmation()], [_value()])
    review = builder.build_package_rows([_locked_row()], _match_report("LOW CONFIDENCE", True), [], [])

    assert len(ready["updated_rows"]) == 1
    assert len(ready["diff_rows"]) == 1
    assert len(ready["verified_learning_rows"]) == 1
    assert len(ready["manual_review_rows"]) == 0
    assert len(review["manual_review_rows"]) == 1
    assert len(review["diff_rows"]) == 0


def test_build_offline_update_package_outputs_package_files():
    package = builder.build_offline_update_package("test_01", [_locked_row()], _match_report(), [_confirmation()], [_value()])

    assert package["schema_version"] == "offline_update_package_v1"
    assert package["locked_row_count"] == 1
    assert package["changed_row_count"] >= 0
    assert package["preview_only"] is True
    assert package["files_written"] == 0
    assert package["backup_csv"]
    assert package["updated_csv_preview"]
    assert package["rollback_csv"]
    assert package["audit_json"]
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

    assert package["locked_row_count"] == 1
    assert "p1" in package["updated_csv_preview"]


def test_manifest_export_excludes_large_csv_blocks():
    package = builder.build_offline_update_package("test_01", [_locked_row()], _match_report(), [_confirmation()], [_value()])
    manifest = json.loads(builder.export_package_manifest_json(package))

    assert "backup_csv" not in manifest
    assert "updated_csv_preview" not in manifest
    assert "rollback_csv" not in manifest
    assert "package_hash" in manifest


def test_empty_package_requires_rows():
    package = builder.build_offline_update_package("test_01", [], {}, [], [])

    assert package["status"] == "NO ROWS"
    assert package["errors"]


def test_package_service_has_no_external_client_paths():
    source = open("autonomous_betting_agent/offline_update_package_builder.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
