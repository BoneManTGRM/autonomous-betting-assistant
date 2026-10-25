"""Synthetic temporary-store and observation-only calibration regressions."""
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_betting_agent import storage
from autonomous_betting_agent.local_calibration import brier_score, calibration_buckets, odds_band_summary
from autonomous_betting_agent.sqlite_store import SQLiteStore


class OfflineStorageCalibrationTests(unittest.TestCase):
    def test_sqlite_pending_grade_can_be_resolved_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteStore(Path(folder) / 'synthetic.sqlite')
            for index, pending in enumerate(('pending', 'ungraded', 'open', '')):
                proof = f'synthetic-{index}'
                store.save_row({'proof_id': proof, 'result_status': pending})
                self.assertTrue(store.update_grade(proof, 'win'), pending)
                row = next(r for r in store.load_rows() if r['proof_id'] == proof)
                self.assertEqual(row['grade'], 'win')
                self.assertEqual(row['result_status'], 'win')

    def test_sqlite_preserves_resolved_grade_conflict_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteStore(Path(folder) / 'synthetic.sqlite')
            store.save_row({'proof_id': 'synthetic', 'grade': 'win'})
            self.assertFalse(store.update_grade('synthetic', 'loss'))
            self.assertFalse(store.update_grade('synthetic', 'pending'))
            self.assertEqual(store.load_rows()[0]['grade'], 'win')
            self.assertTrue(store.update_grade('synthetic', 'won'))
            self.assertTrue(store.update_grade('synthetic', 'loss', overwrite=True))
            self.assertEqual(store.load_rows()[0]['grade'], 'loss')
            self.assertEqual(sum(r['action'] == 'grade_conflict' for r in store.load_audit_log()), 2)

    def test_csv_fallback_does_not_load_audit_events_as_pick_rows(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'SQLiteStore', None):
            store = storage.LocalStorage(csv_dir=Path(folder) / 'ledgers')
            store.save_row({'proof_id': 'synthetic', 'event': 'SYNTHETIC Alpha vs Beta'})
            store.add_audit_event('synthetic_audit', {'proof_id': 'synthetic'}, 'test only')
            self.assertEqual(len(store.load_rows()), 1)
            self.assertEqual(len(store.load_audit_log()), 1)
            out = store.export_csv(Path(folder) / 'export.csv')
            with out.open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)

    def test_unknown_stored_grades_still_require_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteStore(Path(folder) / 'synthetic.sqlite')
            for index, grade in enumerate(('half_won', 'custom_provider_status')):
                proof = f'synthetic-custom-{index}'
                store.save_row({'proof_id': proof, 'grade': grade})
                self.assertFalse(store.update_grade(proof, 'loss'))
                self.assertFalse(store.update_grade(proof, 'pending'))
                self.assertFalse(store.update_grade(proof, 'different_custom_status'))
                row = next(r for r in store.load_rows() if r['proof_id'] == proof)
                self.assertEqual(row['grade'], grade)
                self.assertTrue(store.update_grade(proof, grade))
                self.assertTrue(store.update_grade(proof, 'loss', overwrite=True))

    def test_calibration_preserves_zero_probability_and_alias_priority(self):
        self.assertEqual(brier_score([{'model_probability': 0, 'grade': 'win'}]), 1)
        self.assertEqual(brier_score([{'learned_model_probability': 0, 'model_probability': .9, 'grade': 'loss'}]), 0)
        self.assertEqual(calibration_buckets([{'model_probability': 0, 'grade': 'loss'}])[0]['sample_size'], 1)

    def test_calibration_accepts_canonical_results_and_excludes_non_decisions(self):
        rows = [{'probability': .8, 'result_status': 'win'}, {'probability': .2, 'graded_result': 'loss'},
                {'probability': .9, 'grade': 'pending'}, {'probability': .9, 'grade': 'void'}]
        self.assertAlmostEqual(brier_score(rows), .04)
        self.assertEqual(sum(b['sample_size'] for b in calibration_buckets(rows)), 2)

    def test_odds_bands_exclude_invalid_prices(self):
        rows = [{'decimal_price': value, 'grade': 'win'} for value in
                ('NaN', 'Infinity', '-Infinity', 0, 1, -2, 10 ** 400)]
        self.assertEqual(sum(b['sample_size'] for b in odds_band_summary(rows)), 0)

    def test_calibration_huge_or_nonfinite_probability_is_missing(self):
        for value in (10 ** 400, 'NaN', 'Infinity', '-Infinity'):
            with self.subTest(value=value):
                self.assertIsNone(brier_score([{'model_probability': value, 'grade': 'win'}]))

    def test_invalid_bucket_sizes_raise_clear_value_error(self):
        for size in (0, -1, 2, float('nan'), float('inf')):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    calibration_buckets([{'model_probability': .5, 'grade': 'win'}], bucket_size=size)


if __name__ == '__main__':
    unittest.main()
