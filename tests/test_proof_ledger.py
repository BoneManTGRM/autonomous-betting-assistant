from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import autonomous_betting_agent.local_users as local_users
from autonomous_betting_agent.proof_ledger import (
    append_predictions_to_ledger,
    build_ledger_rows,
    ledger_summary,
    load_ledger,
    verify_hash_chain,
)


class ProofLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = local_users.LOCAL_USERS_DIR
        local_users.LOCAL_USERS_DIR = Path(self.tmp.name) / 'local_users'

    def tearDown(self) -> None:
        local_users.LOCAL_USERS_DIR = self.original_dir
        self.tmp.cleanup()

    def sample_predictions(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                'event': 'A at B',
                'sport': 'basketball',
                'prediction': 'B',
                'model_probability': '72%',
                'decimal_price': 1.80,
                'confidence': 'HIGH',
                'reliability_score': 96,
                'books': 5,
                'api_coverage_score': 1.0,
                'result_status': 'win',
                'stake_units': 1,
            },
            {
                'event': 'C at D',
                'sport': 'soccer',
                'prediction': 'C',
                'model_probability': '61%',
                'decimal_price': 2.05,
                'confidence': 'MEDIUM',
                'reliability_score': 84,
                'books': 3,
                'result_status': 'loss',
                'stake_units': 1,
            },
        ])

    def test_build_rows_has_hash_chain(self) -> None:
        rows = build_ledger_rows(self.sample_predictions(), user_id='Cody Test', previous_hash='GENESIS')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.loc[0, 'previous_hash'], 'GENESIS')
        self.assertEqual(rows.loc[1, 'previous_hash'], rows.loc[0, 'row_hash'])
        self.assertTrue(verify_hash_chain(rows).valid)

    def test_tampering_breaks_hash_chain(self) -> None:
        rows = build_ledger_rows(self.sample_predictions(), user_id='Cody Test', previous_hash='GENESIS')
        rows.loc[0, 'prediction'] = 'Tampered Pick'
        verification = verify_hash_chain(rows)
        self.assertFalse(verification.valid)
        self.assertEqual(verification.first_bad_row, 0)

    def test_append_and_summary(self) -> None:
        combined = append_predictions_to_ledger(self.sample_predictions(), user_id='Cody Test')
        self.assertEqual(len(combined), 2)
        loaded = load_ledger('Cody Test')
        self.assertEqual(len(loaded), 2)
        self.assertTrue(verify_hash_chain(loaded).valid)
        summary = ledger_summary(loaded)
        self.assertEqual(summary['wins'], 1)
        self.assertEqual(summary['losses'], 1)
        self.assertEqual(summary['total_picks'], 2)
        self.assertIsNotNone(summary['win_rate'])

    def test_dedupe_prediction_ids(self) -> None:
        append_predictions_to_ledger(self.sample_predictions(), user_id='Cody Test')
        combined = append_predictions_to_ledger(self.sample_predictions(), user_id='Cody Test')
        self.assertEqual(len(combined), 2)


if __name__ == '__main__':
    unittest.main()
