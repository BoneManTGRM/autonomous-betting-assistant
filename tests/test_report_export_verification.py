from datetime import datetime, timezone, timedelta

from autonomous_betting_agent.report_export_verification import (
    STATUS_API_UNAVAILABLE,
    STATUS_LINE_MOVED,
    STATUS_STALE_BLOCKED,
    STATUS_VERIFIED_RECENT,
    prepare_export_rows,
    safe_provider_error,
    validate_parlay_legs,
    verify_export_row,
)


def _fresh_live_row(now):
    return {
        "event_id": "evt-1",
        "event": "A vs B",
        "sport": "WNBA",
        "market_type": "spread",
        "selection": "A -1.5",
        "spread_line": "-1.5",
        "decimal_price": "1.91",
        "model_probability": "0.57",
        "odds_status": "LIVE",
        "odds_source": "LIVE_API",
        "last_api_refresh_time": now.isoformat(),
        "market_snapshot": "provider snapshot present",
    }


def test_stale_june_row_is_blocked():
    now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    row = _fresh_live_row(now)
    row["last_api_refresh_time"] = "2026-06-29T12:00:00+00:00"
    checked = verify_export_row(row, now=now)
    assert checked["export_verification_status"] == STATUS_STALE_BLOCKED
    assert checked["export_blocked"] == "true"
    assert "STALE_TIMESTAMP" in checked["export_block_reason"]


def test_uploaded_or_saved_odds_are_not_verified():
    now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    row = _fresh_live_row(now)
    row["odds_status"] = "UPLOADED_ROW"
    row["odds_source"] = "consensus_average"
    checked = verify_export_row(row, now=now)
    assert checked["export_verification_status"] == STATUS_API_UNAVAILABLE
    assert checked["odds_verified"] == "false"


def test_missing_line_blocks_spread_export():
    now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    row = _fresh_live_row(now)
    row.pop("spread_line")
    row.pop("selection")
    row["selection"] = "A spread"
    checked = verify_export_row(row, now=now)
    assert checked["export_verification_status"] == STATUS_LINE_MOVED
    assert "LINE_MOVED" in checked["export_block_reason"]


def test_verified_live_recent_row_passes():
    now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    row = _fresh_live_row(now - timedelta(minutes=5))
    checked = verify_export_row(row, now=now)
    assert checked["export_verification_status"] == STATUS_VERIFIED_RECENT
    assert checked["export_blocked"] == "false"
    assert checked["odds_verified"] == "true"


def test_prepare_export_rows_quarantines_blocked_rows():
    now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    verified, summary, blocked = prepare_export_rows([_fresh_live_row(now), {"event": "old", "timestamp": "2026-06-01T00:00:00+00:00"}], now=now)
    assert len(verified) == 1
    assert summary.blocked_rows == 1
    assert blocked[0]["export_blocked"] == "true"


def test_safe_provider_error_redacts_secret_query_params():
    err = safe_provider_error("SportsDataIO", "scores", "https://api.test/games?key=SECRET123", status=401, section="injuries")
    assert "SECRET123" not in err["message"]
    assert err["blocking"] is True


def test_duplicate_parlay_legs_are_rejected():
    now = datetime.now(timezone.utc)
    leg = _fresh_live_row(now)
    verified, meta = validate_parlay_legs([leg, dict(leg)])
    assert len(verified) == 1
    assert meta["playable"] is False
    assert meta["rejected"][0]["reason"] == "DUPLICATE_PARLAY_LEG"
