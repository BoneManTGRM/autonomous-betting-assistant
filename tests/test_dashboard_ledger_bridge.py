import pandas as pd
import pytest

from autonomous_betting_agent import proof_performance_store as store
from autonomous_betting_agent.dashboard_ledger_bridge import (
    DASHBOARD_COMPATIBILITY_FIELDS,
    build_dashboard_from_ledger,
    choose_dashboard_rows,
    dashboard_source_summary,
    load_ledger_dashboard_rows,
    load_session_dashboard_rows,
    load_uploaded_dashboard_rows,
)
from autonomous_betting_agent.ledger_sync_service import sync_odds_lock_rows


@pytest.fixture()
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LEDGER_CSV_PATH", tmp_path / "proof_performance_ledger.csv")
    monkeypatch.setattr(store, "LEDGER_JSON_PATH", tmp_path / "proof_performance_ledger.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "ledger_backups")
    return tmp_path


def _row(event="Alpha vs Beta", pick="Alpha ML", locked="2026-06-29T10:00:00Z", **overrides):
    row = {
        "event": event,
        "pick": pick,
        "market_type": "h2h",
        "sportsbook": "Book A",
        "locked_at_utc": locked,
        "decimal_odds": 2.0,
        "model_probability": 0.6,
        "raw_implied_probability": 0.5,
        "no_vig_implied_probability": 0.52,
        "edge": 0.10,
        "no_vig_edge": 0.08,
        "expected_value": 0.20,
        "clv": 0.03,
        "stake_units": 1.0,
        "result": "win",
        "report_lane": "playable",
        "official_publish_ready": True,
        "odds_verified": True,
    }
    row.update(overrides)
    return row


def test_load_ledger_dashboard_rows_preserves_compatibility_fields(isolated_ledger):
    sync_odds_lock_rows([_row()], "client_a")

    rows = load_ledger_dashboard_rows("client_a")

    assert len(rows) == 1
    for field in DASHBOARD_COMPATIBILITY_FIELDS:
        assert field in rows.columns
    assert rows.iloc[0]["public_event"] == "Alpha vs Beta"
    assert rows.iloc[0]["prediction"] == "Alpha ML"
    assert rows.iloc[0]["bookmaker"] == "Book A"
    assert rows.iloc[0]["model_market_edge"] == 0.10
    assert rows.iloc[0]["expected_value_per_unit"] == 0.20
    assert rows.iloc[0]["manual_clv"] == 0.03


def test_dashboard_bridge_prefers_persistent_ledger_rows_over_stale_session_uploads(isolated_ledger):
    sync_odds_lock_rows([_row("Ledger Game", "Ledger ML")], "client_a")
    session_state = {"pro_predictor_latest_rows": [_row("Session Game", "Session ML")]}
    uploaded = [pd.DataFrame([_row("Upload Game", "Upload ML")])]

    choice = choose_dashboard_rows("client_a", session_state=session_state, uploaded_frames=uploaded)
    summary = dashboard_source_summary("client_a", session_state=session_state, uploaded_frames=uploaded)
    dashboard = build_dashboard_from_ledger("client_a", session_state=session_state, uploaded_frames=uploaded)

    assert choice["selected_source"] == "ledger"
    assert choice["rows"].iloc[0]["event"] == "Ledger Game"
    assert summary["selected_source"] == "ledger"
    assert summary["ledger_rows"] == 1
    assert summary["session_rows"] == 1
    assert summary["uploaded_rows"] == 1
    assert dashboard["events_scanned"] == 1
    assert dashboard["sync_summary"]["selected_source"] == "ledger"


def test_dashboard_bridge_falls_back_to_session_when_ledger_empty(isolated_ledger):
    session_state = {"pro_predictor_latest_rows": [_row("Session Game", "Session ML")]}

    choice = choose_dashboard_rows("client_a", session_state=session_state)
    summary = dashboard_source_summary("client_a", session_state=session_state)
    dashboard = build_dashboard_from_ledger("client_a", session_state=session_state)

    assert choice["selected_source"] == "session"
    assert choice["rows"].iloc[0]["event"] == "Session Game"
    assert summary["selected_source"] == "session"
    assert summary["selected_rows"] == 1
    assert dashboard["events_scanned"] == 1
    assert dashboard["sync_summary"]["warnings"]


def test_dashboard_bridge_falls_back_to_uploaded_when_ledger_and_session_empty(isolated_ledger):
    uploaded = [pd.DataFrame([_row("Upload Game", "Upload ML")])]

    choice = choose_dashboard_rows("client_a", uploaded_frames=uploaded)
    summary = dashboard_source_summary("client_a", uploaded_frames=uploaded)
    dashboard = build_dashboard_from_ledger("client_a", uploaded_frames=uploaded)

    assert choice["selected_source"] == "uploaded"
    assert choice["rows"].iloc[0]["event"] == "Upload Game"
    assert summary["selected_source"] == "uploaded"
    assert summary["uploaded_rows"] == 1
    assert dashboard["events_scanned"] == 1
    assert dashboard["positive_ev_picks"] == 1


def test_dashboard_bridge_empty_safe_path(isolated_ledger):
    choice = choose_dashboard_rows("client_a")
    summary = dashboard_source_summary("client_a")
    dashboard = build_dashboard_from_ledger("client_a")

    assert choice["selected_source"] == "empty"
    assert choice["rows"].empty
    assert summary["selected_source"] == "empty"
    assert summary["selected_rows"] == 0
    assert summary["warnings"]
    assert dashboard["events_scanned"] == 0
    assert dashboard["top_positive_ev_picks"] == []


def test_session_and_uploaded_loaders_are_read_only_and_no_fake_demo_data(isolated_ledger):
    session_row = _row("Session Game", "Session ML")
    upload_frame = pd.DataFrame([_row("Upload Game", "Upload ML")])
    session_state = {"pro_predictor_latest_rows": [dict(session_row)]}

    session_rows = load_session_dashboard_rows(session_state)
    uploaded_rows = load_uploaded_dashboard_rows([upload_frame])

    assert session_rows.iloc[0]["event"] == "Session Game"
    assert uploaded_rows.iloc[0]["event"] == "Upload Game"
    assert session_state["pro_predictor_latest_rows"][0] == session_row
    assert "John Doe" not in session_rows.to_json()
    assert "NY Liberty -120" not in uploaded_rows.to_json()


def test_dashboard_bridge_rows_compatible_with_build_dashboard_data(isolated_ledger):
    sync_odds_lock_rows([_row("Alpha vs Beta", "Alpha ML")], "client_a")

    dashboard = build_dashboard_from_ledger(
        "client_a",
        learning_rows=pd.DataFrame([{"row": 1}]),
        api_usage={"used_calls": 10, "call_limit": 100},
        bankroll=1000,
        unit_size=10,
    )

    assert dashboard["events_scanned"] == 1
    assert dashboard["positive_ev_picks"] == 1
    assert dashboard["learning_rows_scanned"] == 1
    assert dashboard["api_usage"]["usage_display"] == "10.0%"
    assert dashboard["bankroll_summary"]["recommended_bets"] == 1
