from datetime import datetime, timedelta, timezone

from autonomous_betting_agent.report_export_verification import sanitize_export_sections, verify_row_for_export, verify_rows_for_export

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)


def _fresh_row(**extra):
    row = {
        "event_id": "evt-1",
        "away_team": "Seattle Storm",
        "home_team": "Phoenix Mercury",
        "market_type": "spread",
        "prediction": "Phoenix Mercury -1.5",
        "line": "-1.5",
        "decimal_price": "1.91",
        "model_probability": "0.56",
        "odds_verified": "true",
        "odds_status": "LIVE",
        "odds_source": "LIVE_API",
        "verified_timestamp": (NOW - timedelta(minutes=4)).isoformat(),
        "market_snapshot": "provider snapshot payload present",
    }
    row.update(extra)
    return row


def test_verified_live_row_can_export():
    checked, result = verify_row_for_export(_fresh_row(is_live="true"), now=NOW)
    assert result.export_allowed is True
    assert checked["export_public_status"] == "VERIFIED LIVE"
    assert checked["odds_verified"] == "true"


def test_stale_june_row_is_quarantined():
    row = _fresh_row(verified_timestamp="2026-06-29T12:00:00+00:00")
    result = verify_rows_for_export([row], run_capture=False, now=NOW)
    assert result.export_allowed is False
    assert result.stale_ignored_count == 1
    assert result.quarantined_rows[0]["export_verification_status"] == "STALE_TIMESTAMP"
    assert result.quarantined_rows[0]["export_public_status"] == "STALE — EXPORT BLOCKED"


def test_uploaded_unverified_row_is_blocked():
    row = _fresh_row(odds_verified="false", odds_status="UPLOADED_ROW", odds_source="UPLOADED_ROW")
    checked, result = verify_row_for_export(row, source_mode="saved-handoff", now=NOW)
    assert result.export_allowed is False
    assert checked["export_public_status"] == "API UNAVAILABLE — NOT VERIFIED"
    assert "No live verified provider marker" in checked["export_blocked_reason"]


def test_price_mismatch_blocks_export():
    saved = _fresh_row(decimal_price="1.91")
    live = _fresh_row(decimal_price="1.82")
    checked, result = verify_row_for_export(saved, now=NOW, live_snapshot={"row": live})
    assert result.export_allowed is False
    assert checked["export_verification_status"] == "PRICE_MOVED"
    assert checked["export_public_status"] == "PRICE MOVED — EXPORT BLOCKED"


def test_line_mismatch_blocks_export():
    saved = _fresh_row(line="-1.5")
    live = _fresh_row(line="-3.5")
    checked, result = verify_row_for_export(saved, now=NOW, live_snapshot={"row": live})
    assert result.export_allowed is False
    assert checked["export_verification_status"] == "LINE_MOVED"


def test_event_mismatch_blocks_export():
    saved = _fresh_row(event_id="evt-1")
    live = _fresh_row(event_id="evt-2")
    checked, result = verify_row_for_export(saved, now=NOW, live_snapshot={"row": live})
    assert result.export_allowed is False
    assert checked["export_verification_status"] == "EVENT_MISMATCH"


def test_missing_snapshot_blocks_live_export():
    row = _fresh_row()
    row.pop("market_snapshot")
    row.pop("verified_price", None)
    row.pop("current_verified_price", None)
    checked, result = verify_row_for_export(row, now=NOW)
    assert result.export_allowed is False
    assert checked["export_verification_status"] == "SNAPSHOT_MISSING"


def test_placeholder_sections_are_removed_from_blocked_rows():
    row = sanitize_export_sections({
        "export_allowed": "False",
        "injury_report": "Player data not returned for this event",
        "sports_context_summary": "context unavailable",
        "chain_notes": "some parlay text",
    })
    assert row["injury_report"] == ""
    assert row["sports_context_summary"] == ""
    assert row["chain_notes"] == ""
