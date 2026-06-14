from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.pick_store import create_run, list_unfinished_picks, record_pick_rows
from autonomous_betting_agent.result_reconciler import reconcile_results


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class ResultReconcilerTests(unittest.TestCase):
    def test_reconciles_unfinished_pick(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            db = base / "picks.sqlite"
            games = base / "games.csv"
            run_id = create_run(db)
            record_pick_rows(db, run_id, [{"sdio_game_id": "10", "market": "h2h", "selection": "DAL", "prediction": "DAL", "best_price": "1.8"}])
            self.assertEqual(len(list_unfinished_picks(db)), 1)
            _write_csv(games, [{
                "sdio_game_id": "10",
                "home_team": "DAL",
                "away_team": "NYG",
                "home_score": "24",
                "away_score": "17",
                "winner": "DAL",
                "is_final": "true",
                "status": "Final",
            }])
            report = reconcile_results(db_path=db, canonical_games_csv=games, output_json=base / "report.json")
            self.assertEqual(report.matched_rows, 1)
            self.assertEqual(report.graded_rows, 1)
            self.assertEqual(len(list_unfinished_picks(db)), 0)
            self.assertTrue((base / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
