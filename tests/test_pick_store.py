from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.pick_store import (
    create_run,
    export_history_rows,
    initialize_store,
    list_unfinished_picks,
    record_pick_rows,
    summarize_store,
    update_pick_result,
)


class PickStoreTests(unittest.TestCase):
    def test_store_records_and_updates_picks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "picks.sqlite"
            initialize_store(db)
            run_id = create_run(db, run_type="manual", run_mode="manual")
            count = record_pick_rows(db, run_id, [{
                "event": "A at B",
                "market": "h2h",
                "selection": "B",
                "bankroll_action": "BET",
                "recommended_stake_units": "1.0",
                "best_price": "1.8",
            }])
            self.assertEqual(count, 1)
            summary = summarize_store(db)
            self.assertEqual(summary.pick_count, 1)
            self.assertEqual(summary.final_bet_count, 1)
            unfinished = list_unfinished_picks(db)
            self.assertEqual(len(unfinished), 1)
            update_pick_result(db, unfinished[0]["pick_id"], result="win", actual_winner="B", profit_loss_units=0.8)
            self.assertEqual(len(list_unfinished_picks(db)), 0)
            history = export_history_rows(db)
            self.assertEqual(history[0]["result"], "win")

    def test_upsert_prevents_duplicate_rows_per_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "picks.sqlite"
            run_id = create_run(db)
            row = {"sdio_game_id": "10", "market": "h2h", "selection": "DAL", "bankroll_action": "WATCH"}
            record_pick_rows(db, run_id, [row, row])
            self.assertEqual(summarize_store(db).pick_count, 1)


if __name__ == "__main__":
    unittest.main()
