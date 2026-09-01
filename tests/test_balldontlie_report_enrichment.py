from __future__ import annotations

from autonomous_betting_agent import balldontlie_integration as bdl


def test_balldontlie_returns_traceable_team_game_injury_and_prop_fields(monkeypatch) -> None:
    monkeypatch.setenv("BALLDONTLIE_API_KEY", "bdl-secret")

    alpha = {"id": 1, "full_name": "Alpha Aces", "city": "Alpha", "name": "Aces"}
    beta = {"id": 2, "full_name": "Beta Bears", "city": "Beta", "name": "Bears"}

    def fake_request(slug, path, params=None):
        assert slug == "nba"
        if path == "/teams":
            return {"data": [alpha, beta]}
        if path == "/games":
            return {"data": [{"id": 99, "home_team": beta, "visitor_team": alpha, "status": "Scheduled"}]}
        if path == "/player_injuries":
            return {"data": [{"status": "Out", "player": {"full_name": "A Player", "team": alpha}}]}
        if path == "/odds":
            return {"data": [{"vendor": "Book One", "market": "moneyline"}]}
        if path == "/odds/player_props":
            return {"data": [{"player_name": "B Player", "prop_type": "points", "line": 20.5, "decimal_odds": 1.9, "vendor": "Book One"}]}
        return {"data": []}

    monkeypatch.setattr(bdl, "_request_json", fake_request)
    row = bdl.enrich_row_with_balldontlie({
        "event": "Alpha Aces vs Beta Bears",
        "away_team": "Alpha Aces",
        "home_team": "Beta Bears",
        "sport": "NBA",
        "event_date": "2026-09-02",
    })

    assert row["balldontlie_status"] == "LIVE"
    assert "Alpha Aces / Beta Bears" in row["balldontlie_team_summary"]
    assert "game matched" in row["balldontlie_game_summary"]
    assert "A Player" in row["balldontlie_injury_summary"]
    assert "Book One moneyline" in row["balldontlie_odds_summary"]
    assert row["player_prop_markets"][0]["provider_event_id"] == "99"
    assert "model probability" in row["player_prop_markets"][0]["source_note"]
    assert "bdl-secret" not in str(row)


def test_balldontlie_empty_team_result_is_not_live(monkeypatch) -> None:
    monkeypatch.setenv("BALLDONTLIE_API_KEY", "bdl-secret")
    monkeypatch.setattr(bdl, "_request_json", lambda *args, **kwargs: {"data": []})

    row = bdl.enrich_row_with_balldontlie({"event": "Alpha vs Beta", "sport": "NBA"})

    assert row["balldontlie_status"] == "NO_TEAM_MATCH"
    assert "no team match" in row["balldontlie_team_summary"].lower()
