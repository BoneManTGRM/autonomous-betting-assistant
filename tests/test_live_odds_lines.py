from autonomous_betting_agent.live_odds import summarize_event


def test_spread_total_only_event_becomes_candidate_rows():
    event = {
        "id": "evt-1",
        "sport_key": "basketball_nba",
        "sport_title": "NBA",
        "commence_time": "2026-07-01T00:00:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "bookmakers": [
            {
                "key": "book_a",
                "title": "Book A",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Home", "price": 1.91, "point": -3.5},
                            {"name": "Away", "price": 1.91, "point": 3.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.9, "point": 221.5},
                            {"name": "Under", "price": 1.9, "point": 221.5},
                        ],
                    },
                ],
            }
        ],
    }

    summary = summarize_event(event)

    assert summary is not None
    markets = {outcome.market for outcome in summary.outcomes}
    assert "spreads" in markets
    assert "totals" in markets
    assert len(summary.outcomes) == 4
