from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_package_fingerprint_ignores_nested_volatile_fields():
    original = {
        "schema_version": "dashboard_refresh_package_v1",
        "row_count": 2,
        "manifest": {
            "generated_at_utc": "2026-01-01T00:00:00Z",
            "dashboard_refresh_id": "a",
            "dashboard_refresh_hash": "b",
            "row_count": 2,
        },
        "nested": [
            {
                "generated_at_utc": "2026-01-01T00:00:00Z",
                "local_review_hash": "x",
                "status": "PASS",
            }
        ],
    }
    rebuilt = {
        "schema_version": "dashboard_refresh_package_v1",
        "row_count": 2,
        "manifest": {
            "generated_at_utc": "2026-02-01T00:00:00Z",
            "dashboard_refresh_id": "c",
            "dashboard_refresh_hash": "d",
            "row_count": 2,
        },
        "nested": [
            {
                "generated_at_utc": "2026-02-01T00:00:00Z",
                "local_review_hash": "y",
                "status": "PASS",
            }
        ],
    }

    assert package_fingerprint(original) == package_fingerprint(rebuilt)
