from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import io
import math
import unittest
from unittest.mock import patch

from autonomous_betting_agent.offline_learning_validation import (
    _metrics, decision_features, devig_market, run_offline_validation, validate_observation,
)

START = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)


def stamp(value):
    return value.isoformat()


def observation(index, **changes):
    decision = START + timedelta(days=index)
    row = {
        "event_id": f"event-{index}", "selection_id": "home", "market_id": "moneyline-full-game",
        "sport": "synthetic", "market_type": "moneyline_2way",
        "decision_time": stamp(decision), "prediction_recorded_at": stamp(decision),
        "event_start": stamp(decision + timedelta(hours=1)),
        "result_available_at": stamp(decision + timedelta(hours=5)),
        "verified_at": stamp(decision + timedelta(hours=6)), "outcome_verified": True,
        "raw_model_probability": 0.8, "baseline_probability": 0.8,
        "raw_probability_available_at": stamp(decision), "baseline_probability_available_at": stamp(decision),
        "raw_model_version": "synthetic-raw-v1", "baseline_model_version": "synthetic-baseline-v1",
        "result_status": "win" if index % 5 < 3 else "loss",
        "event_source": "synthetic-event-fixture", "prediction_source": "synthetic-locked-fixture",
        "result_source": "synthetic-result-fixture", "features": {},
    }
    row.update(changes)
    return row


def run(rows, **kwargs):
    args = {"train_before": stamp(START + timedelta(days=100)),
            "holdout_from": stamp(START + timedelta(days=110)),
            "evaluation_as_of": stamp(START + timedelta(days=220))}
    args.update(kwargs)
    return run_offline_validation(rows, **args)


def market(row, **changes):
    quote = {"event_id": row["event_id"], "market_id": row["market_id"], "bookmaker": "synthetic-book",
             "snapshot_id": "snapshot-1", "available_at": row["decision_time"]}
    result = {**quote, "market_type": "moneyline_2way",
              "outcomes": [{**quote, "selection_id": "home", "decimal_odds": 1.8},
                           {**quote, "selection_id": "away", "decimal_odds": 2.2}]}
    result.update(changes)
    return result


class OfflineLearningValidationTests(unittest.TestCase):
    def test_clean_synthetic_improvement_is_review_only_never_live_permission(self):
        report = run([observation(i) for i in range(210)])
        self.assertEqual(report["status"], "REVIEW_CANDIDATE")
        self.assertTrue(report["candidate"]["fitted"])
        self.assertLess(report["holdout"]["delta"]["brier"], 0)
        self.assertLess(report["holdout"]["delta"]["log_loss"], 0)
        for key in ("live_mutation_allowed", "promotion_allowed", "predictive_gain_proven"):
            self.assertIs(report[key], False)

    def test_no_input_mutation_and_deterministic_report(self):
        rows = [observation(i) for i in range(210)]
        before = deepcopy(rows)
        first = run(rows)
        self.assertEqual(rows, before)
        self.assertEqual(first, run(rows))

    def test_synthetic_training_gain_cannot_mask_bad_holdout(self):
        rows = [observation(i) for i in range(210)]
        # Candidate learns 60%; unseen set is 90%, so reducing 80% hurts.
        for i in range(110, 210):
            rows[i]["result_status"] = "win" if i % 10 else "loss"
        report = run(rows)
        self.assertEqual(report["status"], "INSUFFICIENT_EVIDENCE")
        self.assertGreater(report["holdout"]["delta"]["brier"], 0)

    def test_holdout_outcomes_and_closing_features_never_change_predictions(self):
        rows = [observation(i) for i in range(210)]
        first = run(rows)
        for row in rows[110:]:
            row["result_status"] = "loss" if row["result_status"] == "win" else "win"
            row["closing_line_value"] = 1000
            row["clv"] = 1000
            row["profit_units"] = 100000
            row["closing_decimal_price"] = 99
        second = run(rows)
        self.assertEqual(first["candidate"], second["candidate"])
        self.assertEqual(first["holdout"]["predictions"], second["holdout"]["predictions"])

    def test_development_outcomes_do_not_tune_frozen_candidate(self):
        rows = [observation(i) for i in range(210)]
        first = run(rows)
        for row in rows[100:110]:
            row["result_status"] = "loss"
        self.assertEqual(first["candidate"], run(rows)["candidate"])

    def test_exact_duplicates_do_not_increase_event_evidence(self):
        rows = [observation(i) for i in range(210)]
        first = run(rows)
        second = run(rows + deepcopy(rows))
        self.assertEqual(second["coverage"]["duplicate_rows_removed"], 210)
        self.assertEqual(first["partitions"], second["partitions"])
        self.assertEqual(first["holdout"], second["holdout"])

    def test_conflicting_duplicate_quarantines_event(self):
        first = observation(1)
        second = {**first, "result_status": "loss"}
        report = run([first, second])
        self.assertEqual(report["partitions"]["train"]["rows"], 0)
        self.assertEqual(report["coverage"]["rejected_rows"], 2)

    def test_event_groups_cannot_cross_split(self):
        first = observation(99)
        second = observation(100, event_id=first["event_id"], selection_id="away")
        report = run([first, second])
        self.assertEqual(report["partitions"]["train"]["rows"], 0)
        self.assertEqual(report["partitions"]["development"]["rows"], 0)

    def test_malformed_member_quarantines_entire_event_not_just_bad_row(self):
        first = observation(1)
        second = {**first, "selection_id": "away", "outcome_verified": False}
        report = run([first, second])
        self.assertEqual(report["partitions"]["train"]["rows"], 0)
        self.assertEqual(report["coverage"]["rejected_rows"], 2)

    def test_label_availability_uses_verification_time_not_just_event_time(self):
        row = observation(1, verified_at=stamp(START + timedelta(days=101)))
        report = run([row])
        self.assertEqual(report["partitions"]["train"]["rows"], 0)
        self.assertIn("training label", report["rejected"][0]["reason"])

    def test_label_equal_to_training_cutoff_is_unavailable(self):
        row = observation(1, verified_at=stamp(START + timedelta(days=100)))
        self.assertEqual(run([row])["partitions"]["train"]["rows"], 0)

    def test_late_final_outcome_is_not_evaluated(self):
        row = observation(120, verified_at=stamp(START + timedelta(days=300)))
        self.assertEqual(run([row])["partitions"]["holdout"]["rows"], 0)

    def test_missing_or_invalid_aware_timestamps_fail_closed(self):
        for value in (None, "", "2025-01-02", "garbage", "2025-01-02T12:00:00"):
            with self.subTest(value=value):
                self.assertEqual(run([observation(1, decision_time=value)])["coverage"]["admitted_unique_rows"], 0)

    def test_bad_cutoffs_raise_instead_of_silent_reordering(self):
        with self.assertRaises(ValueError):
            run([], holdout_from=stamp(START))

    def test_numeric_zero_and_false_outcomes_are_losses(self):
        for value in (0, 0.0, "0", "0.0", False):
            self.assertEqual(validate_observation(observation(1, result_status=value)).outcome, 0)

    def test_unverified_or_ambiguous_labels_are_rejected(self):
        for changes in ({"outcome_verified": "true"}, {"outcome_verified": False},
                        {"result_status": "incorrect prediction"}, {"result_status": "win if home"},
                        {"result_status": "pending win verification"}, {"result_status": "push"},
                        {"result_status": "win", "result": "loss"},
                        {"result_status": "win", "Result Status": "loss"},
                        {"result_status": "win", "status": "pending win verification"}):
            self.assertEqual(run([observation(1, **changes)])["coverage"]["admitted_unique_rows"], 0)

    def test_missing_identity_sources_and_baseline_do_not_get_fallbacks(self):
        for field in ("event_id", "selection_id", "market_id", "event_source", "prediction_source", "result_source",
                      "raw_model_version", "baseline_model_version", "raw_model_probability", "baseline_probability"):
            row = observation(1)
            del row[field]
            with self.subTest(field=field):
                self.assertEqual(run([row])["coverage"]["admitted_unique_rows"], 0)

    def test_probabilities_are_finite_explicit_decimals(self):
        for value in (float("nan"), float("inf"), -0.1, 70, True, 10 ** 1000):
            with self.assertRaises(ValueError):
                validate_observation(observation(1, raw_model_probability=value))
        self.assertEqual(validate_observation(observation(1, raw_model_probability=0)).raw_probability, 0)
        self.assertEqual(run([observation(1, baseline_probability=10 ** 1000)])["coverage"]["rejected_rows"], 1)

    def test_future_probability_is_rejected(self):
        row = observation(1, raw_probability_available_at=stamp(START + timedelta(days=2)))
        self.assertEqual(run([row])["coverage"]["admitted_unique_rows"], 0)

    def test_postevent_feature_names_are_not_allowlisted(self):
        for name in ("clv", "CLV", "closing_line_value", "result", "profit_units", "winner"):
            row = observation(1, features={name: {"value": 1, "available_at": observation(1)["decision_time"], "source": "synthetic"}})
            self.assertEqual(run([row])["coverage"]["admitted_unique_rows"], 0)

    def test_feature_provenance_freshness_and_availability(self):
        row = observation(1)
        good = {"value": 2, "available_at": row["decision_time"], "source": "synthetic"}
        row["features"] = {"rest_days": good}
        view = decision_features(validate_observation(row))
        self.assertEqual(view, {"raw_model_probability": 0.8, "context": {"rest_days": 2}})
        for changes in ({"available_at": stamp(START + timedelta(days=3))},
                        {"available_at": stamp(START - timedelta(days=3))}, {"source": ""}, {"value": None}):
            row["features"] = {"rest_days": {**good, **changes}}
            with self.assertRaises(ValueError):
                validate_observation(row)

    def test_hand_computed_metrics_and_event_balancing(self):
        rows = [validate_observation(observation(1, result_status="win")), validate_observation(observation(2, result_status="loss"))]
        metrics = _metrics(rows, [0.8, 0.2])
        self.assertAlmostEqual(metrics["brier"], 0.04)
        self.assertAlmostEqual(metrics["log_loss"], -math.log(0.8))
        self.assertAlmostEqual(metrics["ece_10_bins"], 0.2)
        repeated = _metrics([rows[0], rows[0], rows[1]], [0.8, 0.8, 0.2])
        for key in ("brier", "log_loss", "ece_10_bins"):
            self.assertAlmostEqual(metrics[key], repeated[key])

    def test_frozen_model_versions_and_minimum_evidence_not_bypassable(self):
        rows = [observation(i) for i in range(210)]
        rows[-1]["baseline_model_version"] = "other-version"
        self.assertFalse(run(rows)["candidate"]["fitted"])
        small = run([observation(i) for i in range(20)])
        self.assertEqual(small["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(small["candidate"]["fitted"])

    def test_subgroup_regression_or_small_sample_blocks_review(self):
        rows = [observation(i) for i in range(210)]
        rows[-1]["sport"] = "sparse-sport"
        self.assertEqual(run(rows)["status"], "INSUFFICIENT_EVIDENCE")

    def test_devig_requires_complete_same_book_same_time_market(self):
        row = observation(1)
        snap = market(row)
        kwargs = {"event_id": row["event_id"], "market_id": row["market_id"], "selection_id": "home",
                  "decision_time": datetime.fromisoformat(row["decision_time"])}
        self.assertAlmostEqual(devig_market(snap, **kwargs), 0.55)
        for change in ("missing", "book", "time", "event", "duplicate"):
            bad = deepcopy(snap)
            if change == "missing":
                bad["outcomes"].pop()
            elif change == "book":
                bad["outcomes"][1]["bookmaker"] = "other"
            elif change == "time":
                bad["outcomes"][1]["available_at"] = stamp(START)
            elif change == "event":
                bad["outcomes"][1]["event_id"] = "other"
            else:
                bad["outcomes"][1]["selection_id"] = "home"
            with self.subTest(change=change), self.assertRaises(ValueError):
                devig_market(bad, **kwargs)

    def test_three_way_market_cannot_omit_draw(self):
        row = observation(1, market_type="moneyline_3way")
        row["market_snapshot"] = market(row, market_type="moneyline_3way")
        checked = validate_observation(row)
        self.assertIsNone(checked.market_probability)
        self.assertIn("complete", checked.market_baseline_reason)

    def test_market_type_mismatch_does_not_produce_a_baseline(self):
        row = observation(1, market_type="total_2way")
        row["market_snapshot"] = market(row)
        self.assertIsNone(validate_observation(row).market_probability)

    def test_market_price_overflow_is_unavailable_not_a_crash(self):
        row = observation(1)
        row["market_snapshot"] = market(row)
        row["market_snapshot"]["outcomes"][0]["decimal_odds"] = 10 ** 1000
        self.assertIsNone(validate_observation(row).market_probability)

    def test_conflicting_duplicate_accounting_does_not_double_count_rejections(self):
        row = observation(1)
        report = run([row, deepcopy(row), {**row, "result_status": "loss"}])
        self.assertEqual(report["coverage"]["rejected_rows"], 3)
        self.assertEqual(report["coverage"]["duplicate_rows_removed"], 0)

    def test_absent_market_data_is_unavailable_not_invented(self):
        report = run([observation(120)])
        self.assertIsNone(report["holdout"]["market_baseline"]["metrics"])
        self.assertEqual(report["holdout"]["market_baseline"]["coverage_rows"], 0)

    def test_empty_input_does_not_claim_success(self):
        report = run([])
        self.assertEqual(report["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(report["holdout"]["candidate"])

    def test_cli_rejects_duplicate_json_evidence_keys_before_normalization(self):
        from tools.run_offline_learning_validation import main
        for key in ("result_status", "decision_time", "outcome_verified"):
            data = '[{"' + key + '": "first", "' + key + '": "second"}]'
            stderr = io.StringIO()
            with self.subTest(key=key), patch("tools.run_offline_learning_validation.Path.read_text", return_value=data), redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as failure:
                    main(["explicit-fixture.json", "--train-before", stamp(START),
                          "--holdout-from", stamp(START + timedelta(days=1)),
                          "--evaluation-as-of", stamp(START + timedelta(days=2))])
            self.assertEqual(failure.exception.code, 2)
            self.assertIn("duplicate JSON key", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
