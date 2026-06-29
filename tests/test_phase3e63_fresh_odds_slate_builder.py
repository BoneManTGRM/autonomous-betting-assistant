from __future__ import annotations

import json

from autonomous_betting_agent.fresh_odds_slate_builder import (
    SLATE_MISSING_FIELDS,
    SLATE_READY,
    build_slate_rows_from_payload,
    fetch_the_odds_api_payload,
    normalize_sportsdataio_events,
    normalize_the_odds_api_events,
    redact_api_key_from_text,
    slate_builder_report_section,
    slate_builder_summary,
)


def _odds_payload():
    return [
        {
            "id": "event-1",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": "2099-01-01T00:00:00Z",
            "home_team": "Home Team",
            "away_team": "Away Team",
            "bookmakers": [
                {
                    "key": "caliente",
                    "title": "Caliente",
                    "last_update": "2098-12-31T23:50:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Home Team", "price": 1.91},
                                {"name": "Away Team", "price": 2.05},
                            ],
                        }
                    ],
                },
                {
                    "key": "codere",
                    "title": "Codere",
                    "last_update": "2098-12-31T23:51:00Z",
                    "markets": [
                        {"key": "h2h", "outcomes": [{"name": "Home Team", "price": 1.88}]}
                    ],
                },
            ],
        }
    ]


def test_the_odds_api_payload_generates_advisory_compatible_rows():
    rows = normalize_the_odds_api_events(_odds_payload(), sport="basketball_nba", market="h2h")
    assert len(rows) == 3
    first = rows[0]
    assert first["event"] == "Away Team vs Home Team"
    assert first["prediction"] == "Home Team"
    assert first["market_type"] == "h2h"
    assert first["bookmaker"] == "Caliente"
    assert first["decimal_odds"] == 1.91
    assert first["slate_builder_ready_for_advisory_pipeline"] is True
    assert first["slate_builder_price_available"] is True
    assert first["slate_builder_missing_fields"] == ""


def test_bookmaker_filter_and_missing_price_diagnostics():
    payload = _odds_payload()
    payload[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = None
    rows = normalize_the_odds_api_events(payload, bookmaker_filter="caliente")
    assert len(rows) == 2
    assert {row["bookmaker"] for row in rows} == {"Caliente"}
    assert rows[0]["slate_builder_ready_for_advisory_pipeline"] is False
    assert "decimal_odds" in rows[0]["slate_builder_missing_fields"]


def test_sportsdataio_context_rows_are_safe_but_not_price_ready():
    rows = normalize_sportsdataio_events([
        {"GameID": 123, "HomeTeam": "Home", "AwayTeam": "Away", "DateTimeUTC": "2099-01-01T00:00:00Z"}
    ], sport="nba")
    assert len(rows) == 1
    assert rows[0]["slate_builder_api_name"] == "SportsDataIO"
    assert rows[0]["bookmaker"] == "context_only"
    assert rows[0]["slate_builder_ready_for_advisory_pipeline"] is False
    assert "decimal_odds" in rows[0]["slate_builder_missing_fields"]


def test_builder_dispatch_summary_and_report():
    rows = build_slate_rows_from_payload("The Odds API", _odds_payload(), sport="basketball_nba", market="h2h")
    summary = slate_builder_summary(rows)
    report = slate_builder_report_section(rows)
    assert summary.iloc[0]["slate_builder_status"] == SLATE_READY
    assert int(summary.iloc[0]["ready_rows"]) == 3
    assert "Fresh Odds Slate Builder" in report
    assert "no server" in report.lower()


def test_empty_or_unknown_payload_summary_is_safe():
    assert build_slate_rows_from_payload("unknown", {}) == []
    summary = slate_builder_summary([])
    assert list(summary.columns) == [
        "slate_builder_status",
        "row_count",
        "ready_rows",
        "missing_field_rows",
        "price_available_rows",
    ]
    missing = slate_builder_summary([{"event": "x"}])
    assert missing.iloc[0]["slate_builder_status"] == SLATE_MISSING_FIELDS


def test_fetch_payload_uses_user_triggered_requester_without_returning_key_in_rows():
    secret = "test-secret-key"

    def requester(url: str, timeout: int) -> str:
        assert secret in url
        assert timeout == 15
        return json.dumps(_odds_payload())

    payload = fetch_the_odds_api_payload(secret, sport_key="basketball_nba", requester=requester)
    rows = normalize_the_odds_api_events(payload)
    assert rows
    assert secret not in json.dumps(rows)
    assert redact_api_key_from_text(f"abc {secret} xyz", secret) == "abc [REDACTED_API_KEY] xyz"


def test_safety_notes_include_no_persistence_or_live_action():
    rows = normalize_the_odds_api_events(_odds_payload())
    text = rows[0]["slate_builder_safety_notes"].lower()
    assert "no server" in text
    assert "no database" in text
    assert "no live betting" in text
    assert "no proof mutation" in text
