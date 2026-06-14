from __future__ import annotations

import unittest

from autonomous_betting_agent.profit_goal import (
    ProfitGoalPolicy,
    closing_line_value,
    parse_price,
    review_profit_goal_rows,
)


class ProfitGoalTests(unittest.TestCase):
    def test_parse_price_accepts_decimal_and_american(self) -> None:
        self.assertAlmostEqual(parse_price(1.50) or 0, 1.50)
        self.assertAlmostEqual(parse_price(+150) or 0, 2.50)
        self.assertAlmostEqual(parse_price(-200) or 0, 1.50)

    def test_clv_positive_when_entry_price_beats_close(self) -> None:
        row = {"closing_odds": 1.40}
        self.assertAlmostEqual(closing_line_value(row, 1.50) or 0, (1.50 - 1.40) / 1.50)

    def test_goal_met_for_profitable_deduped_dataset(self) -> None:
        rows = []
        for index in range(70):
            rows.append({"event": f"win {index}", "prediction": "A", "result": "won", "best_price": 1.50, "closing_odds": 1.45})
        for index in range(30):
            rows.append({"event": f"loss {index}", "prediction": "A", "result": "lost", "best_price": 1.50, "closing_odds": 1.45})
        report = review_profit_goal_rows(rows, ProfitGoalPolicy(min_finished=100))
        self.assertEqual(report.status, "GOAL_MET")
        self.assertEqual(report.wins, 70)
        self.assertEqual(report.losses, 30)
        self.assertAlmostEqual(report.win_rate or 0, 0.70)
        self.assertGreater(report.roi or 0, 0)
        self.assertGreater(report.average_clv or 0, 0)

    def test_low_odds_prevent_goal_even_with_high_win_rate(self) -> None:
        rows = []
        for index in range(80):
            rows.append({"event": f"win {index}", "prediction": "A", "result": "won", "best_price": 1.10, "closing_odds": 1.09})
        for index in range(20):
            rows.append({"event": f"loss {index}", "prediction": "A", "result": "lost", "best_price": 1.10, "closing_odds": 1.09})
        report = review_profit_goal_rows(rows, ProfitGoalPolicy(min_finished=100))
        self.assertEqual(report.status, "NOT_MET_YET")
        self.assertFalse(report.goal_checks["average_odds_above_minimum"])
        self.assertFalse(report.goal_checks["positive_roi"])

    def test_duplicates_are_not_counted_as_finished_padding(self) -> None:
        rows = [
            {"event": "same", "start": "1", "market": "h2h", "prediction": "A", "result": "won", "best_price": 1.50, "closing_odds": 1.45},
            {"event": "same", "start": "1", "market": "h2h", "prediction": "A", "result": "won", "best_price": 1.50, "closing_odds": 1.45},
        ]
        report = review_profit_goal_rows(rows, ProfitGoalPolicy(min_finished=1))
        self.assertEqual(report.duplicate_rows, 1)
        self.assertFalse(report.goal_checks["no_duplicate_padding"])

    def test_game_id_market_pick_dedupe_allows_same_pick_on_different_games(self) -> None:
        rows = [
            {"sdio_result_game_id": "10", "market": "h2h", "prediction": "A", "result": "won", "best_price": 1.50},
            {"sdio_result_game_id": "11", "market": "h2h", "prediction": "A", "result": "lost", "best_price": 1.50},
        ]
        report = review_profit_goal_rows(rows, ProfitGoalPolicy(min_finished=1, require_positive_clv=False))
        self.assertEqual(report.duplicate_rows, 0)
        self.assertEqual(report.finished_rows, 2)

    def test_same_game_id_market_pick_is_duplicate(self) -> None:
        rows = [
            {"sdio_result_game_id": "10", "market": "h2h", "prediction": "A", "result": "won", "best_price": 1.50},
            {"sdio_result_game_id": "10", "market": "h2h", "prediction": "A", "result": "won", "best_price": 1.50},
        ]
        report = review_profit_goal_rows(rows, ProfitGoalPolicy(min_finished=1, require_positive_clv=False))
        self.assertEqual(report.duplicate_rows, 1)
        self.assertEqual(report.finished_rows, 1)


if __name__ == "__main__":
    unittest.main()
