from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.final_pick_pipeline import run_final_pick_pipeline
from autonomous_betting_agent.multi_source_fusion import fuse_row, fuse_rows, market_probability_from_row


class MultiSourceFusionTests(unittest.TestCase):
    def test_market_probability_from_decimal_odds(self) -> None:
        self.assertAlmostEqual(market_probability_from_row({"best_price": "2.0"}) or 0.0, 0.5)

    def test_fusion_caps_stats_adjustment(self) -> None:
        row = {"best_price": "2.0", "stats_probability": "0.80", "injury_risk_score": "100", "weather_risk_score": "100"}
        result = fuse_row(row)
        self.assertAlmostEqual(result.stats_adjustment, 0.06)
        self.assertAlmostEqual(result.final_probability or 0.0, 0.56)
        self.assertGreater(result.reliability_score, 70)

    def test_injury_and_weather_can_reduce_probability(self) -> None:
        row = {"best_price": "1.8", "stats_probability": "0.60", "key_player_out": "true", "lineup_confirmed": "false", "weather_risk_score": "40"}
        result = fuse_row(row)
        self.assertLess(result.injury_adjustment, 0)
        self.assertLess(result.weather_adjustment, 0)
        self.assertLess(result.final_probability or 1.0, result.market_probability or 1.0)

    def test_fuse_rows_overrides_model_probability_for_calibration(self) -> None:
        rows = fuse_rows([{"best_price": "2.0", "model_probability": "0.70"}])
        self.assertEqual(rows[0]["raw_model_probability"], "0.70")
        self.assertEqual(rows[0]["model_probability"], rows[0]["final_probability"])

    def test_final_pipeline_includes_fusion_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "predictions.csv"
            path.write_text(
                "event,start_time,pick_time,market,selection,best_price,model_probability,edge\n"
                "A at B,2026-09-10T20:00:00Z,2026-09-10T12:00:00Z,h2h,A,2.0,0.70,0.05\n",
                encoding="utf-8",
            )
            report = run_final_pick_pipeline(predictions_csv=path, output_dir=Path(temp_dir) / "out")
            self.assertIn("multi_source_fusion", report.steps_run)
            scored = Path(report.outputs.all_scored_csv).read_text(encoding="utf-8")
            self.assertIn("market_probability", scored)
            self.assertIn("final_probability", scored)


if __name__ == "__main__":
    unittest.main()
