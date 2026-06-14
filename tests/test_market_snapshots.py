from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.live_odds import LiveEventSummary, OutcomePrice
from autonomous_betting_agent.market_snapshots import add_line_movement, event_snapshot_rows, latest_snapshot_with_movement


def sample_summary(probability: float, best_price: float) -> LiveEventSummary:
    return LiveEventSummary(
        event_id="event-1",
        sport_key="baseball_mlb",
        sport_title="MLB",
        commence_time="2026-06-14T20:00:00Z",
        home_team="Home",
        away_team="Away",
        favorite="Home",
        favorite_probability=probability,
        outcomes=[
            OutcomePrice("Home", 1.9, 0.52, probability, 4, best_price=best_price, worst_price=1.8, price_range=best_price - 1.8, best_bookmaker="Book A"),
            OutcomePrice("Away", 2.1, 0.48, 1 - probability, 4, best_price=2.2, worst_price=2.0, price_range=0.2, best_bookmaker="Book B"),
        ],
        bookmaker_count=4,
        cycle_notes=[],
        market_overround=0.03,
        spreads=[],
        totals=[],
    )


class MarketSnapshotTests(unittest.TestCase):
    def test_event_snapshot_rows(self) -> None:
        rows = event_snapshot_rows(sample_summary(0.55, 1.95), "2026-06-14T10:00:00+00:00")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["event_id"], "event-1")
        self.assertEqual(rows[0]["snapshot_time_utc"], "2026-06-14T10:00:00+00:00")

    def test_line_movement(self) -> None:
        first = pd.DataFrame(event_snapshot_rows(sample_summary(0.55, 1.95), "2026-06-14T10:00:00+00:00"))
        second = pd.DataFrame(event_snapshot_rows(sample_summary(0.60, 1.85), "2026-06-14T11:00:00+00:00"))
        frame = pd.concat([first, second], ignore_index=True)
        moved = latest_snapshot_with_movement(frame)
        home = moved[moved["outcome"] == "Home"].iloc[0]
        self.assertAlmostEqual(home["opening_probability"], 0.55)
        self.assertAlmostEqual(home["current_probability"], 0.60)
        self.assertAlmostEqual(home["probability_move"], 0.05)
        self.assertAlmostEqual(home["best_price_move"], -0.10)

    def test_empty_frame(self) -> None:
        moved = add_line_movement(pd.DataFrame())
        self.assertIn("probability_move", moved.columns)
        self.assertEqual(len(moved), 0)


if __name__ == "__main__":
    unittest.main()
