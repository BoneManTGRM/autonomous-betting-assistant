import json

from autonomous_betting_agent import subscriber_export_center as export_center


def _intelligence_report():
    return {
        "schema_version": "subscriber_intelligence_v1",
        "workspace_id": "test_01",
        "subscriber_hash": "subhash",
        "preview_only": True,
        "live_changes": 0,
        "profiles": [
            {"subscriber_id": "s1", "name": "Sub One", "enabled": True, "partner": "Marco", "plan": "starter", "risk_level": "conservative"},
            {"subscriber_id": "s2", "name": "Sub Two", "enabled": True, "partner": "direct", "plan": "pro", "risk_level": "aggressive"},
        ],
        "subscriber_reports": [
            {
                "subscriber_id": "s1",
                "subscriber_name": "Sub One",
                "bet_count": 1,
                "watch_count": 1,
                "wait_count": 0,
                "no_bet_count": 1,
                "report_hash": "r1",
                "recommendations": [
                    {
                        "subscriber_id": "s1",
                        "subscriber_name": "Sub One",
                        "event": "A vs B",
                        "sport": "tennis",
                        "sportsbook": "caliente",
                        "market_type": "moneyline",
                        "selection": "A",
                        "decimal_odds": 2.1,
                        "minimum_playable_odds": 1.8,
                        "calibrated_probability": 0.58,
                        "ev": 0.218,
                        "edge": 0.104,
                        "risk_label": "LOW",
                        "personal_action": "BET",
                        "filter_reason": "eligible",
                        "recommended_stake": 20,
                        "why": "positive EV",
                        "why_not": "",
                        "private_debug": "should not export",
                    }
                ],
            },
            {
                "subscriber_id": "s2",
                "subscriber_name": "Sub Two",
                "bet_count": 0,
                "watch_count": 0,
                "wait_count": 0,
                "no_bet_count": 1,
                "report_hash": "r2",
                "recommendations": [],
            },
        ],
    }


def _ledger_report():
    return {
        "schema_version": "subscriber_ledger_v1",
        "workspace_id": "test_01",
        "ledger_hash": "ledgerhash",
        "preview_only": True,
        "live_changes": 0,
        "subscriber_summaries": [
            {"subscriber_id": "s1", "row_count": 2, "unique_event_count": 1, "win_rate_ex_push_cancel": 0.5, "roi": 0.4, "profit_loss": 60, "stake": 150},
            {"subscriber_id": "s2", "row_count": 1, "unique_event_count": 1, "win_rate_ex_push_cancel": 0.0, "roi": -1.0, "profit_loss": -50, "stake": 50},
        ],
        "ledger_rows": [
            {"subscriber_id": "s1", "ledger_id": "l1", "event_id": "e1", "stake": 100, "profit_loss": 110, "result": "win"},
            {"subscriber_id": "s1", "ledger_id": "l2", "event_id": "e1", "stake": 50, "profit_loss": -50, "result": "loss"},
            {"subscriber_id": "s2", "ledger_id": "l3", "event_id": "e2", "stake": 50, "profit_loss": -50, "result": "loss"},
        ],
    }


def test_build_export_package_pairs_report_and_ledger():
    profile = _intelligence_report()["profiles"][0]
    report = _intelligence_report()["subscriber_reports"][0]
    ledger_summary = _ledger_report()["subscriber_summaries"][0]
    ledger_rows = [row for row in _ledger_report()["ledger_rows"] if row["subscriber_id"] == "s1"]
    package = export_center.build_export_package(profile, report, ledger_summary, ledger_rows)

    assert package["subscriber_id"] == "s1"
    assert package["package_status"] == "READY"
    assert package["has_report"] is True
    assert package["has_ledger"] is True
    assert package["recommendation_count"] == 1
    assert package["ledger_row_count"] == 2
    assert package["client_safe_rows"]
    assert "private_debug" not in json.dumps(package["client_safe_rows"])


def test_build_export_packages_includes_all_source_subscribers():
    packages = export_center.build_export_packages(
        _intelligence_report()["profiles"],
        _intelligence_report()["subscriber_reports"],
        _ledger_report()["subscriber_summaries"],
        _ledger_report()["ledger_rows"],
    )

    assert len(packages) == 2
    assert {package["subscriber_id"] for package in packages} == {"s1", "s2"}


def test_partner_summary_and_distribution_rows():
    packages = export_center.build_export_packages(
        _intelligence_report()["profiles"],
        _intelligence_report()["subscriber_reports"],
        _ledger_report()["subscriber_summaries"],
        _ledger_report()["ledger_rows"],
    )
    partners = export_center.partner_summary(packages)
    plans = export_center.distribution_rows(packages, "plan")
    risks = export_center.distribution_rows(packages, "risk_level")

    assert any(row["partner"] == "Marco" and row["subscriber_count"] == 1 for row in partners)
    assert any(row["plan"] == "starter" for row in plans)
    assert any(row["risk_level"] == "aggressive" for row in risks)


def test_build_subscriber_export_center_exports():
    report = export_center.build_subscriber_export_center("test_01", _intelligence_report(), _ledger_report())
    payload = json.loads(export_center.export_subscriber_export_center_json(report))

    assert payload["schema_version"] == "subscriber_export_center_v1"
    assert payload["export_status"] == "EXPORT CENTER READY"
    assert payload["package_count"] == 2
    assert payload["admin_dashboard_summary"]["subscriber_count"] == 2
    assert payload["admin_dashboard_summary"]["total_bet_count"] == 1
    assert payload["admin_dashboard_summary"]["total_profit_loss"] == 10
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "package_id" in export_center.export_package_index_csv(report)
    assert "partner" in export_center.export_partner_summary_csv(report)
    assert "plan" in export_center.export_plan_distribution_csv(report)
    assert "risk_level" in export_center.export_risk_distribution_csv(report)
    assert "personal_action" in export_center.export_client_safe_rows_csv(report)
    assert "subscriber_count" in export_center.export_admin_dashboard_json(report)
    assert "check_id" in export_center.export_export_checks_csv(report)
    assert "export_hash" in export_center.export_export_manifest_json(report)


def test_build_subscriber_export_center_warns_missing_ledger():
    ledger_report = dict(_ledger_report())
    ledger_report["subscriber_summaries"] = [ledger_report["subscriber_summaries"][0]]
    report = export_center.build_subscriber_export_center("test_01", _intelligence_report(), ledger_report)

    assert report["export_status"] == "REVIEW REQUIRED"
    assert any(row["check_id"] == "missing_ledgers" and row["status"] == "WARN" for row in report["export_checks"])


def test_build_subscriber_export_center_from_text():
    report = export_center.build_subscriber_export_center_from_text("test_01", json.dumps(_intelligence_report()), json.dumps(_ledger_report()), "")

    assert report["package_count"] == 2
    assert report["export_status"] == "EXPORT CENTER READY"


def test_build_subscriber_export_center_blocks_missing_sources():
    report = export_center.build_subscriber_export_center("test_01", {}, {})

    assert report["export_status"] == "BLOCKED"
    assert any(row["status"] == "FAIL" for row in report["export_checks"])


def test_subscriber_export_center_has_no_external_client_paths():
    source = open("autonomous_betting_agent/subscriber_export_center.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
