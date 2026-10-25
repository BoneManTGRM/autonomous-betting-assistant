from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
import unittest

from autonomous_betting_agent.learning import ProbabilityCalibrator
from autonomous_betting_agent.learning_memory_tools import (
    build_memory_bank,
    build_segments,
    make_ara_memory_csv,
    memory_metrics,
    merge_dedupe_rows,
    prune_rows,
    read_compact_csv_bytes,
    rows_to_graded,
)


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    # These are explicit synthetic evidence fixtures, not reconstructed history.
    supplied = []
    for index, row in enumerate(rows):
        start = datetime.fromisoformat(str(row['event_start_utc']).replace('Z', '+00:00'))
        before = (start - timedelta(hours=1)).isoformat()
        supplied.append({**row, 'event_id': f'synthetic-{index}', 'market_id': 'synthetic-market',
                         'selection_id': 'home', 'event_start': row['event_start_utc'],
                         'decision_time': before, 'prediction_recorded_at': before,
                         'result_available_at': (start + timedelta(hours=4)).isoformat(),
                         'verified_at': (start + timedelta(hours=5)).isoformat(), 'outcome_verified': 'true',
                         'raw_model_probability': row['model_probability_clean'],
                         'baseline_probability': row['model_probability_clean'],
                         'raw_probability_available_at': before, 'baseline_probability_available_at': before,
                         'raw_model_version': 'synthetic-v1', 'baseline_model_version': 'synthetic-v1',
                         'event_source': 'synthetic', 'prediction_source': 'synthetic', 'result_source': 'synthetic',
                         'features': json.dumps({})})
    fields = list(supplied[0])
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(supplied)
    return buffer.getvalue().encode("utf-8")


class LearningMemoryToolsTests(unittest.TestCase):
    def test_high_confidence_result_only_file_is_rejected_without_fabricated_probability(self) -> None:
        csv_text = "event,sport,prediction,result\nA at B,Soccer,B,won\nC at D,Soccer,C,lost\nE at F,Soccer,E,unknown\n"
        rows, stats = read_compact_csv_bytes(csv_text.encode("utf-8"), "High confidence.csv")
        self.assertEqual(stats["input_rows"], 3)
        self.assertEqual(stats["usable_rows"], 0)
        self.assertEqual(stats["wins"], 0)
        self.assertEqual(stats["losses"], 0)
        self.assertEqual(stats["missing_result"], 1)
        self.assertEqual(stats["fallback_probability_rows"], 0)
        self.assertEqual(rows, [])
        self.assertEqual(stats['admission_report']['rejected_rows'], 3)
        self.assertEqual(len(stats['admission_report']['records']), 3)
        metrics = memory_metrics(rows)
        self.assertEqual(metrics["resolved"], 0)
        self.assertEqual(metrics["wins"], 0)
        self.assertEqual(metrics["losses"], 0)

    def test_explicit_probability_without_provenance_is_not_training_evidence(self) -> None:
        csv_text = "event,prediction,model_probability,result\nA at B,B,62%,won\n"
        rows, stats = read_compact_csv_bytes(csv_text.encode("utf-8"), "regular.csv")
        self.assertEqual(stats["usable_rows"], 0)
        self.assertEqual(stats["fallback_probability_rows"], 0)
        self.assertEqual(rows, [])
        self.assertEqual(stats['admission_report']['records'][0]['record']['model_probability'], '62%')

    def test_learning_memory_parses_roi_clv_and_segments(self) -> None:
        data = _csv_bytes(
            [
                {
                    "event": "A at B",
                    "event_start_utc": "2026-06-20T20:00:00Z",
                    "sport": "NBA",
                    "market_type": "spreads",
                    "prediction": "B -3.5",
                    "model_probability_clean": "0.64",
                    "result_status": "win",
                    "decimal_price": "1.91",
                    "closing_price": "1.80",
                    "stake_units": "1",
                    "bookmaker_count": "20",
                    "api_coverage_score": "1.0",
                },
                {
                    "event": "C at D",
                    "event_start_utc": "2026-06-21T20:00:00Z",
                    "sport": "NBA",
                    "market_type": "spreads",
                    "prediction": "D -2.5",
                    "model_probability_clean": "0.61",
                    "result_status": "loss",
                    "decimal_price": "1.95",
                    "closing_price": "1.88",
                    "stake_units": "1",
                    "bookmaker_count": "18",
                    "api_coverage_score": "1.0",
                },
            ]
        )
        rows, stats = read_compact_csv_bytes(data, "unit-test.csv")
        segments = build_segments(rows, min_records=2, max_segments=50)
        metrics = memory_metrics(rows)
        ara_csv = make_ara_memory_csv(segments)
        self.assertEqual(stats["usable_rows"], 2)
        self.assertEqual(metrics["resolved"], 2)
        self.assertAlmostEqual(metrics["profit_units"], -0.09)
        self.assertAlmostEqual(metrics["roi"], -0.045)
        self.assertTrue(any(segment["area_type"] == "sport_market" for segment in segments))
        self.assertIn("roi", ara_csv)
        self.assertIn("avg_clv_percent", ara_csv)
        self.assertIn("beat_close_rate", ara_csv)

    def test_learning_memory_merge_preserves_large_dataset_until_max_rows(self) -> None:
        uploaded = []
        for index in range(600):
            uploaded.append(
                {
                    "event": f"Game {index}",
                    "start": f"2026-07-{(index % 28) + 1:02d}",
                    "sport": "MLB" if index % 2 else "NBA",
                    "market_type": "h2h" if index % 3 else "spreads",
                    "prediction": f"Team {index}",
                    "probability": 0.62,
                    "outcome": 1 if index % 3 else 0,
                    "best_price": 1.85,
                    "stake_units": 1.0,
                }
            )
        merged, duplicates = merge_dedupe_rows([], uploaded)
        pruned, report = prune_rows(merged, max_rows=1000)
        self.assertEqual(duplicates, 0)
        self.assertEqual(len(merged), 600)
        self.assertEqual(len(pruned), 600)
        self.assertEqual(report["rows_pruned"], 0)

    def test_learning_memory_bank_keeps_patterns_and_summary(self) -> None:
        rows = []
        for index in range(40):
            rows.append(
                {
                    "event": f"Proof {index}",
                    "start": f"2026-08-{(index % 28) + 1:02d}",
                    "sport": "NBA",
                    "market_type": "spreads",
                    "prediction": f"Team {index}",
                    "probability": 0.64,
                    "outcome": 1 if index % 4 else 0,
                    "best_price": 1.91,
                    "stake_units": 1.0,
                    "profit_units": 0.91 if index % 4 else -1.0,
                }
            )
        segments = build_segments(rows, min_records=3, max_segments=200)
        # This test covers bank serialization, not a fitting operation.
        calibrator = ProbabilityCalibrator(events_trained=len(rows), source="synthetic serialization fixture")
        bank = build_memory_bank(
            compact_rows=rows,
            calibrator=calibrator,
            segments=segments,
            parse_stats={},
            prune_report={},
            mode="merge",
            existing_count=0,
            uploaded_count=len(rows),
            duplicates_removed=0,
        )
        self.assertTrue(bank["version"].startswith("learning-memory-bank"))
        self.assertEqual(bank["summary"]["rows_after_pruning"], 40)
        self.assertEqual(bank["summary"]["patterns_saved"], len(segments))
        self.assertIsNotNone(bank["summary"]["roi"])
        self.assertTrue(bank["pattern_leaderboards"]["best_roi"])


if __name__ == "__main__":
    unittest.main()
