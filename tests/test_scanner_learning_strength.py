import unittest

import pandas as pd

from autonomous_betting_agent.learning_memory_tools import build_segments, read_compact_csv_bytes
from autonomous_betting_agent.learning_strength import learning_memory_health
from autonomous_betting_agent.scanner_strength import scanner_strength_summary, score_scanner_frame


class ScannerAndLearningStrengthTests(unittest.TestCase):
    def test_scanner_strength_scores_deeper_markets_higher(self):
        frame = pd.DataFrame([
            {
                'event': 'A at B',
                'sport': 'Basketball',
                'market_type': 'h2h',
                'prediction': 'B',
                'decimal_price': 2.10,
                'average_price': 2.00,
                'best_price': 2.10,
                'price_range': 0.14,
                'bookmaker_count': 8,
                'market_overround': 1.04,
            },
            {
                'event': 'C at D',
                'sport': 'Basketball',
                'market_type': 'h2h',
                'prediction': 'D',
                'decimal_price': '',
                'bookmaker_count': 1,
            },
        ])
        scored = score_scanner_frame(frame)
        self.assertEqual(scored.iloc[0]['scanner_strength_tier'], 'premium_scan')
        self.assertGreater(scored.iloc[0]['scanner_strength_score'], scored.iloc[1]['scanner_strength_score'])
        summary = scanner_strength_summary(frame)
        self.assertEqual(summary['rows'], 2)
        self.assertEqual(summary['premium_scan'], 1)

    def test_learning_memory_health_detects_stronger_memory(self):
        rows = []
        for idx in range(30):
            rows.append({
                'event': f'Event {idx}',
                'sport': 'Tennis' if idx % 2 == 0 else 'Soccer',
                'market_type': 'h2h' if idx % 3 else 'totals',
                'prediction': 'Pick',
                'probability': 0.62,
                'outcome': 1 if idx % 3 else 0,
            })
        health = learning_memory_health(rows)
        self.assertGreaterEqual(health['resolved_rows'], 30)
        self.assertIn(health['learning_health_tier'], {'usable_learning_memory', 'rough_learning_memory', 'strong_learning_memory'})
        self.assertGreater(health['sport_count'], 1)
        self.assertGreater(health['market_count'], 1)

    def test_learning_parser_rejects_missing_evidence_without_losing_result_or_market_fields(self):
        csv_text = 'event,sport,market_type,prediction,model_probability,result_status,bookmaker\nA at B,Tennis,h2h,B,0.64,win,BookA\nC at D,Soccer,totals,Over,58,loss,BookB\n'
        rows, stats = read_compact_csv_bytes(csv_text.encode('utf-8'), 'unit_test.csv')
        self.assertEqual(rows, [])
        self.assertEqual(stats['usable_rows'], 0)
        self.assertEqual(stats['direct_probability_rows'], 0)
        report = stats['admission_report']
        self.assertEqual(report['rejected_rows'], 2)
        self.assertFalse(report['trained'])
        self.assertFalse(report['artifacts_written'])
        originals = [entry['record'] for entry in report['records']]
        self.assertEqual([row['result_status'] for row in originals], ['win', 'loss'])
        self.assertEqual([row['market_type'] for row in originals], ['h2h', 'totals'])
        self.assertEqual([row['model_probability'] for row in originals], ['0.64', '58'])
        self.assertTrue(all(entry['reasons'] for entry in report['records']))

    def test_segment_builder_retains_sport_and_market_dimensions(self):
        # Preserve this independent aggregation check without treating a legacy
        # provenance-free upload as admissible learning evidence.
        rows = [
            {'sport': 'synthetic-tennis', 'market_type': 'h2h', 'probability': .64, 'outcome': 1},
            {'sport': 'synthetic-soccer', 'market_type': 'totals', 'probability': .58, 'outcome': 0},
        ]
        segments = build_segments(rows, min_records=1, max_segments=20)
        area_types = {row['area_type'] for row in segments}
        self.assertIn('market_type', area_types)
        self.assertIn('sport_market', area_types)


if __name__ == '__main__':
    unittest.main()
