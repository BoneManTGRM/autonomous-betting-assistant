from __future__ import annotations

import unittest

from autonomous_betting_agent.bankroll_exposure import BankrollPolicy, apply_bankroll_exposure, summarize_bankroll


class BankrollExposureTests(unittest.TestCase):
    def test_bets_strong_accepted_pick(self) -> None:
        rows = [{
            "ensemble_status": "ACCEPT",
            "ensemble_score": "85",
            "calibrated_probability": "0.65",
            "edge": "0.08",
            "best_price": "1.9",
            "profile_trust_level": "HIGH",
            "sport": "nfl",
            "league": "nfl",
            "market": "h2h",
            "selection": "DAL",
        }]
        sized = apply_bankroll_exposure(rows)
        self.assertEqual(sized[0]["bankroll_action"], "BET")
        self.assertGreater(float(sized[0]["recommended_stake_units"]), 0)
        self.assertEqual(sized[0]["risk_tier"], "LOW")

    def test_rejects_non_accepted_ensemble(self) -> None:
        rows = [{"ensemble_status": "WATCH", "calibrated_probability": "0.7", "edge": "0.08", "best_price": "1.9"}]
        sized = apply_bankroll_exposure(rows)
        self.assertEqual(sized[0]["bankroll_action"], "REJECT")
        self.assertIn("ensemble_status_watch", sized[0]["do_not_bet_reason"])

    def test_caps_exposure_by_team(self) -> None:
        rows = []
        for index in range(3):
            rows.append({
                "ensemble_status": "ACCEPT",
                "ensemble_score": str(90 - index),
                "calibrated_probability": "0.75",
                "edge": "0.15",
                "best_price": "2.0",
                "sport": "nfl",
                "league": "nfl",
                "market": "h2h",
                "selection": "DAL",
            })
        sized = apply_bankroll_exposure(rows, BankrollPolicy(max_team_exposure_units=2.0, max_stake_per_pick_units=2.0, max_daily_exposure_units=10.0))
        bet_stakes = [float(row["recommended_stake_units"]) for row in sized if row["bankroll_action"] == "BET"]
        self.assertLessEqual(sum(bet_stakes), 2.0)
        self.assertTrue(any("team_exposure_cap" in row["exposure_warning"] for row in sized))

    def test_summary_reports_exposure(self) -> None:
        rows = apply_bankroll_exposure([{
            "ensemble_status": "ACCEPT",
            "ensemble_score": "85",
            "calibrated_probability": "0.65",
            "edge": "0.08",
            "best_price": "1.9",
            "sport": "nfl",
            "league": "nfl",
            "market": "h2h",
            "selection": "DAL",
        }])
        report = summarize_bankroll(rows)
        self.assertEqual(report.raw_rows, 1)
        self.assertEqual(report.bet_rows, 1)
        self.assertIn("nfl", report.exposure_by_sport)


if __name__ == "__main__":
    unittest.main()
