import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.commercial_platform_tools import (
    add_clv_columns,
    apply_result_updates,
    dashboard_metrics,
    demo_ledger,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    proof_audit_frame,
    proof_audit_summary,
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
        results = pd.DataFrame([{'proof_id': locked.iloc[0]['proof_id'], 'result_status': 'win', 'closing_decimal_price': 1.9}])
        updated, stats = apply_result_updates(locked, results)
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(updated.iloc[0]['result_status'], 'win')
        self.assertGreater(float(updated.iloc[0]['profit_units']), 0)
        self.assertGreater(float(updated.iloc[0]['clv_percent']), 0)

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

    def test_clv_columns_are_added(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'closing_decimal_price': 1.8, 'agent_decision': 'play_small'}
        ]))
        with_clv = add_clv_columns(locked)
        self.assertIn('clv_percent', with_clv.columns)
        self.assertGreater(float(with_clv.iloc[0]['clv_percent']), 0)
        self.assertTrue(bool(with_clv.iloc[0]['beat_close']))

    def test_proof_audit_detects_hash_match(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small', 'event_start_utc': '2099-01-01T00:00:00Z'}
        ]))
        audit = proof_audit_frame(locked)
        summary = proof_audit_summary(locked)
        self.assertEqual(audit.iloc[0]['hash_status'], 'hash_match')
        self.assertGreater(summary['proof_quality_score'], 0)

    def test_demo_ledger_is_buyer_ready(self):
        demo = demo_ledger()
        self.assertGreaterEqual(len(demo), 3)
        self.assertFalse(public_dashboard_table(demo).empty)
        self.assertGreater(dashboard_metrics(demo)['proof_quality_score'], 0)

    def test_dashboard_and_report_cards(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'closing_decimal_price': 1.9, 'agent_decision': 'play_small', 'result_status': 'win'}
        ]))
        metrics = dashboard_metrics(locked)
        public = public_dashboard_table(locked)
        markdown = report_card_markdown(locked)
        html = report_card_html(locked)
        self.assertEqual(metrics['wins'], 1)
        self.assertFalse(public.empty)
        self.assertIn('Proof Dashboard', markdown)
        self.assertIn('Avg CLV', markdown)
        self.assertIn('<div', html)

    def test_dashboard_metrics_separate_unique_events_from_pick_rows(self):
        locked = lock_rows(pd.DataFrame([
            {'event_id': 'event-1', 'event': 'A at B', 'market_type': 'spreads', 'line_point': 1.5, 'prediction': 'A +1.5', 'model_probability': 0.64, 'decimal_price': 1.91, 'agent_decision': 'play_small', 'result_status': 'win'},
            {'event_id': 'event-1', 'event': 'A at B', 'market_type': 'totals', 'line_point': 2.5, 'prediction': 'Under 2.5', 'model_probability': 0.61, 'decimal_price': 1.85, 'agent_decision': 'play_small', 'result_status': 'loss'},
        ]))
        metrics = dashboard_metrics(locked)
        self.assertEqual(metrics['pick_rows'], 2)
        self.assertEqual(metrics['unique_events'], 1)
        self.assertEqual(metrics['completed_events'], 1)
        self.assertEqual(metrics['events_with_multiple_pick_rows'], 1)
        self.assertEqual(metrics['extra_same_event_pick_rows'], 1)
        self.assertEqual(metrics['row_level_record'], '1-1')


if __name__ == '__main__':
    unittest.main()
