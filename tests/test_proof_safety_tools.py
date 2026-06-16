from __future__ import annotations

from datetime import datetime, timezone
import unittest

import pandas as pd

from autonomous_betting_agent.proof_safety_tools import (
    client_safe_frame,
    confidence_tier,
    enrich_safety_columns,
    explain_pick,
    operator_checklist_frame,
    proof_eligibility,
)


class ProofSafetyToolsTest(unittest.TestCase):
    def test_proof_eligibility_future_row(self):
        row = {
            'event': 'Away at Home',
            'prediction': 'Home',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'bookmaker': 'TestBook',
            'event_start_utc': '2099-01-01T00:00:00Z',
        }
        result = proof_eligibility(row, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(result['official_proof_eligible'])
        self.assertEqual(result['proof_blockers'], '')

    def test_confidence_tier_a_plus(self):
        row = {
            'odds_trust_grade': 'A+',
            'recommended_action': 'lock_candidate',
            'odds_accuracy_score': 92,
            'expected_value_per_unit': 0.10,
        }
        self.assertEqual(confidence_tier(row), 'A+')

    def test_client_safe_frame_hides_private_columns(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'bookmaker': 'TestBook',
            'event_start_utc': '2099-01-01T00:00:00Z',
            'decision_reasons': 'private reason',
        }])
        safe = client_safe_frame(frame, client_safe=True)
        self.assertNotIn('decision_reasons', safe.columns)
        self.assertIn('public_explanation', safe.columns)

    def test_operator_checklist_flags_rows(self):
        frame = pd.DataFrame([{'event': 'Away at Home'}])
        checklist = operator_checklist_frame(frame)
        self.assertFalse(checklist.empty)
        self.assertIn('status', checklist.columns)

    def test_explain_pick_contains_probability(self):
        text = explain_pick({'event': 'Away at Home', 'prediction': 'Home', 'model_probability': 0.62, 'decimal_price': 1.95})
        self.assertIn('Home', text)
        self.assertIn('62.0%', text)


if __name__ == '__main__':
    unittest.main()
