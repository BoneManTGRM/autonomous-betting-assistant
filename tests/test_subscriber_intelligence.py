import json

from autonomous_betting_agent import subscriber_intelligence as sub


def _profiles():
    return [
        {
            "subscriber_id": "s1",
            "name": "Conservative Caliente",
            "plan": "starter",
            "bankroll": "1000",
            "risk_level": "conservative",
            "preferred_sports": "tennis,wnba",
            "sportsbooks": "caliente,playdoit",
            "preferred_bet_types": "moneyline,spread",
            "max_daily_bets": "1",
            "max_stake_per_bet": "20",
            "partner": "Marco",
        },
        {
            "subscriber_id": "s2",
            "name": "Aggressive Multi Book",
            "plan": "pro",
            "bankroll": "5000",
            "risk_level": "aggressive",
            "preferred_sports": "tennis,soccer,wnba",
            "sportsbooks": "caliente,bet365,playdoit",
            "preferred_bet_types": "moneyline,spread,total",
            "max_daily_bets": "3",
            "max_stake_per_bet": "250",
            "partner": "direct",
        },
    ]


def _market_rows():
    return [
        {
            "event_id": "e1",
            "event": "A vs B",
            "sport": "tennis",
            "sportsbook": "caliente",
            "market_type": "moneyline",
            "selection": "A",
            "decimal_odds": 2.1,
            "minimum_playable_odds": 1.8,
            "calibrated_probability": 0.58,
            "calibrated_edge": 0.104,
            "ev": 0.218,
            "risk_level": "LOW",
            "suggested_stake_fraction": 0.02,
            "final_action": "PLAYABLE VALUE",
            "why_value": "positive EV",
        },
        {
            "event_id": "e2",
            "event": "C vs D",
            "sport": "soccer",
            "sportsbook": "bet365",
            "market_type": "total",
            "selection": "Over 2.5",
            "decimal_odds": 2.4,
            "calibrated_probability": 0.50,
            "calibrated_edge": 0.083,
            "ev": 0.20,
            "risk_level": "HIGH",
            "final_action": "PLAYABLE VALUE",
        },
        {
            "event_id": "e3",
            "event": "E vs F",
            "sport": "wnba",
            "sportsbook": "playdoit",
            "market_type": "spread",
            "selection": "E -3",
            "decimal_odds": 1.8,
            "calibrated_probability": 0.50,
            "ev": -0.10,
            "risk_level": "HIGH",
            "final_action": "NO BET",
            "why_fail": "negative EV",
        },
    ]


def test_normalize_profile_sets_defaults_and_hash():
    profile = sub.normalize_profile({"name": "Test", "bankroll": "100"}, 0)

    assert profile["subscriber_id"] == "Test"
    assert profile["risk_level"] == "balanced"
    assert profile["enabled"] is True
    assert profile["profile_hash"].startswith("profile_")


def test_filter_reason_blocks_unavailable_book():
    profile = sub.normalize_profile(_profiles()[0])
    row = dict(_market_rows()[1])

    assert sub.filter_reason(profile, row) == "sport not preferred"


def test_filter_reason_allows_matching_value_pick():
    profile = sub.normalize_profile(_profiles()[0])
    row = _market_rows()[0]

    assert sub.filter_reason(profile, row) == "eligible"


def test_stake_for_profile_respects_max_stake():
    profile = sub.normalize_profile(_profiles()[0])
    row = dict(_market_rows()[0], suggested_stake_fraction=0.5)

    assert sub.stake_for_profile(profile, row) == 20


def test_personalize_for_subscriber_limits_daily_bets():
    profile = sub.normalize_profile(_profiles()[0])
    report = sub.personalize_for_subscriber(profile, _market_rows())

    assert report["bet_count"] == 1
    assert report["subscriber_id"] == "s1"
    assert any(row["personal_action"] == "NO BET" for row in report["recommendations"])


def test_aggressive_subscriber_gets_more_value_rows():
    profile = sub.normalize_profile(_profiles()[1])
    report = sub.personalize_for_subscriber(profile, _market_rows())

    assert report["bet_count"] >= 1
    assert any(row["event_id"] == "e2" and row["personal_action"] == "BET" for row in report["recommendations"])


def test_build_subscriber_intelligence_exports():
    report = sub.build_subscriber_intelligence("test_01", _profiles(), market_rows=_market_rows())
    payload = json.loads(sub.export_subscriber_intelligence_json(report))

    assert payload["schema_version"] == "subscriber_intelligence_v1"
    assert payload["subscriber_status"] == "SUBSCRIBER REPORTS READY"
    assert payload["subscriber_count"] == 2
    assert payload["enabled_subscriber_count"] == 2
    assert payload["admin_summary"]["subscriber_count"] == 2
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "subscriber_id" in sub.export_profiles_csv(report)
    assert "personal_action" in sub.export_personalized_rows_csv(report)
    assert "report_hash" in sub.export_subscriber_reports_json(report)
    assert "subscriber_count" in sub.export_admin_summary_json(report)
    assert "check_id" in sub.export_subscriber_checks_csv(report)
    assert "subscriber_hash" in sub.export_subscriber_manifest_json(report)


def test_build_subscriber_intelligence_from_text():
    profiles_csv = sub.csv_from_rows(_profiles())
    market_csv = sub.csv_from_rows(_market_rows())
    report = sub.build_subscriber_intelligence_from_text("test_01", profiles_csv, "", market_csv)

    assert report["subscriber_count"] == 2
    assert report["market_row_count"] == 3
    assert report["subscriber_status"] == "SUBSCRIBER REPORTS READY"


def test_build_subscriber_intelligence_blocks_missing_market_rows():
    report = sub.build_subscriber_intelligence("test_01", _profiles(), market_rows=[])

    assert report["subscriber_status"] == "BLOCKED"
    assert any(row["check_id"] == "market_rows_present" and row["status"] == "FAIL" for row in report["subscriber_checks"])


def test_subscriber_intelligence_has_no_external_client_paths():
    source = open("autonomous_betting_agent/subscriber_intelligence.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
