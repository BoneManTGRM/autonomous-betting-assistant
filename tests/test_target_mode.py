from __future__ import annotations

import unittest

from autonomous_betting_agent.target_mode import (
    TargetModePolicy,
    api_coverage_score,
    estimated_ev,
    evaluate_target_mode,
    implied_probability,
    price_probability_gap,
)


def clean_row(**overrides):
    row = {
        "final_probability_value": 0.70,
        "market_probability_value": 0.68,
        "books": 5,
        "reliability_score": 97.0,
        "price_probability_gap_value": 0.03,
        "estimated_ev_value": 0.05,
        "duplicate_event_pick": False,
        "market_type": "h2h",
        "confidence": "high",
        "configured_api_sources_count": 3,
        "api_sources_used_count": 3,
        "api_coverage_score": 1.0,
        "all_configured_apis_used": True,
    }
    row.update(overrides)
    return row


class TargetModeTests(unittest.TestCase):
    def test_implied_probability_and_gap(self) -> None:
        self.assertEqual(round(implied_probability(2.0), 4), 0.5)
        self.assertIsNone(implied_probability(1.0))
        self.assertEqual(round(price_probability_gap(2.0, 0.55), 4), 0.05)

    def test_estimated_ev(self) -> None:
        self.assertEqual(round(estimated_ev(0.70, 1.55), 4), 0.085)
        self.assertIsNone(estimated_ev(0.70, 1.0))

    def test_api_coverage_score(self) -> None:
        self.assertEqual(api_coverage_score({"configured_api_sources_count": 3, "api_sources_used_count": 2}), 0.666667)
        self.assertEqual(api_coverage_score({"configured_api_sources_count": 0, "api_sources_used_count": 0}), 0.0)

    def test_target_mode_passes_clean_70_candidate(self) -> None:
        result = evaluate_target_mode(clean_row())
        self.assertTrue(result.passed)
        self.assertEqual(result.rejection_reason, "")
        self.assertGreaterEqual(result.quality_score, 90)

    def test_target_mode_rejects_outside_probability_band(self) -> None:
        result = evaluate_target_mode(clean_row(final_probability_value=0.735))
        self.assertFalse(result.passed)
        self.assertIn("outside 69%-71% band", result.rejection_reason)

    def test_target_mode_rejects_low_market_probability(self) -> None:
        result = evaluate_target_mode(clean_row(market_probability_value=0.55))
        self.assertFalse(result.passed)
        self.assertIn("market probability below floor", result.rejection_reason)

    def test_target_mode_rejects_low_books_and_reliability(self) -> None:
        result = evaluate_target_mode(clean_row(books=2, reliability_score=80.0))
        self.assertFalse(result.passed)
        self.assertIn("not enough books", result.rejection_reason)
        self.assertIn("reliability below target", result.rejection_reason)

    def test_target_mode_rejects_price_mismatch_and_negative_ev(self) -> None:
        result = evaluate_target_mode(clean_row(price_probability_gap_value=0.20, estimated_ev_value=-0.03))
        self.assertFalse(result.passed)
        self.assertIn("price/probability mismatch", result.rejection_reason)
        self.assertIn("EV below target", result.rejection_reason)

    def test_target_mode_rejects_duplicate_or_non_h2h_or_not_high(self) -> None:
        result = evaluate_target_mode(clean_row(duplicate_event_pick=True, market_type="spreads", confidence="medium"))
        self.assertFalse(result.passed)
        self.assertIn("duplicate event/pick", result.rejection_reason)
        self.assertIn("not h2h", result.rejection_reason)
        self.assertIn("not high confidence", result.rejection_reason)

    def test_target_mode_rejects_low_api_coverage(self) -> None:
        policy = TargetModePolicy(min_api_coverage_score=1.0)
        result = evaluate_target_mode(clean_row(api_coverage_score=0.666667, api_sources_used_count=2))
        self.assertFalse(result.passed)
        self.assertIn("API coverage below target", result.rejection_reason)

    def test_target_mode_rejects_when_not_all_configured_apis_used(self) -> None:
        policy = TargetModePolicy(require_all_configured_apis=True)
        result = evaluate_target_mode(clean_row(api_coverage_score=0.666667, api_sources_used_count=2, all_configured_apis_used=False), policy)
        self.assertFalse(result.passed)
        self.assertIn("not all configured APIs used", result.rejection_reason)

    def test_policy_can_relax_probability_band(self) -> None:
        policy = TargetModePolicy(tolerance=0.03)
        result = evaluate_target_mode(clean_row(final_probability_value=0.72), policy)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
