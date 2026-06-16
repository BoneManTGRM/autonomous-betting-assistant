import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.commercial_platform_tools import (
    apply_result_updates,
    dashboard_metrics,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
    save_persistent_ledger,
)
from autonomous_betting_agent.odds_lock_tools import lock_rows


class CommercialPlatformToolsTests(unittest.TestCase):
    def test_save_and_load_persistent_ledger(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.05, 'agent_decision': 'play_small'}
        ]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.csv'
            saved = save_persistent_ledger(locked, path=path)
            loaded = load_persistent_ledger(path=path)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(loaded), 1)
        self.assertIn('proof_id', loaded.columns)

    def test_apply_result_updates_by_proof_id(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small'}
        ]))
        results = pd.DataFrame([{'proof_id': locked.iloc[0]['proof_id'], 'result_status': 'win'}])
        updated, stats = apply_result_updates(locked, results)
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(updated.iloc[0]['result_status'], 'win')
        self.assertGreater(float(updated.iloc[0]['profit_units']), 0)

    def test_merge_ledgers_dedupes_proof_id(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small'}
        ]))
        merged = merge_ledgers(locked, locked)
        self.assertEqual(len(merged), 1)

    def test_raw_non_proof_rows_are_ignored(self):
        raw = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small'}
        ])
        self.assertTrue(filter_locked_proof_rows(raw).empty)
        self.assertEqual(dashboard_metrics(raw)['locked_picks'], 0)
        self.assertTrue(public_dashboard_table(raw).empty)

    def test_mixed_ledger_keeps_only_locked_proof_rows(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small'}
        ]))
        raw = pd.DataFrame([
            {'event': 'C at D', 'prediction': 'D', 'model_probability': 0.61, 'decimal_price': 1.95, 'agent_decision': 'play_small'}
        ])
        merged = merge_ledgers(locked, raw)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.iloc[0]['proof_id'], locked.iloc[0]['proof_id'])

    def test_dashboard_and_report_cards(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small', 'result_status': 'win'}
        ]))
        metrics = dashboard_metrics(locked)
        public = public_dashboard_table(locked)
        markdown = report_card_markdown(locked)
        html = report_card_html(locked)
        self.assertEqual(metrics['wins'], 1)
        self.assertFalse(public.empty)
        self.assertIn('Proof Dashboard', markdown)
        self.assertIn('<div', html)


if __name__ == '__main__':
    unittest.main()
