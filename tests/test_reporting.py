from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.reporting import build_daily_markdown_report


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class ReportingTests(unittest.TestCase):
    def test_build_daily_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            final_bets = base / "final.csv"
            watch = base / "watch.csv"
            rejected = base / "rejected.csv"
            output = base / "summary.md"
            _write_csv(final_bets, [{"sport": "nfl", "market": "h2h", "selection": "DAL", "recommended_stake_units": "1.5", "ensemble_score": "80"}])
            _write_csv(watch, [{"sport": "mlb", "market": "total", "selection": "Over", "recommended_stake_units": "0"}])
            _write_csv(rejected, [{"sport": "nfl", "market": "h2h", "selection": "NYG", "do_not_bet_reason": "low_edge"}])
            text = build_daily_markdown_report(final_bets_csv=final_bets, watchlist_csv=watch, rejected_picks_csv=rejected, output_md=output, warnings=["test warning"])
            self.assertTrue(output.exists())
            self.assertIn("Final bets: 1", text)
            self.assertIn("test warning", text)
            self.assertIn("Rejected Picks", text)


if __name__ == "__main__":
    unittest.main()
