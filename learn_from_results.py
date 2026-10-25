"""Review supplied learning evidence; intentionally does not train or save state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonomous_betting_agent.learning_evidence_admission import review_learning_records
from autonomous_betting_agent.learning_memory_tools import read_compact_csv_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Observation-only evidence readiness review. Never trains or writes learned state.')
    parser.add_argument('results_csv', type=Path, help='Original evidence CSV; deficient legacy records are reported, not reconstructed')
    parser.add_argument('--output', type=Path, default=Path('learned_state.json'), help='Legacy option: reported only; NO file will be written')
    parser.add_argument('--epochs', type=int, default=2500, help='Legacy option ignored; no fitting occurs')
    parser.add_argument('--learning-rate', type=float, default=0.05, help='Legacy option ignored')
    parser.add_argument('--l2', type=float, default=0.01, help='Legacy option ignored')
    parser.add_argument('--min-events', type=int, default=50, help='Readiness event minimum; cannot lower the existing 50-event minimum')
    parser.add_argument('--keep-duplicates', action='store_true', help='Legacy option: all original records are always preserved in the review')
    args = parser.parse_args(argv)
    try:
        _compact_preview, stats = read_compact_csv_bytes(args.results_csv.read_bytes(), str(args.results_csv))
        report = review_learning_records([entry['record'] for entry in stats['admission_report']['records']], minimum_events=args.min_events)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    report.update({'requested_output': str(args.output), 'output_written': False,
                   'command_outcome': 'REVIEW_ONLY_NOT_TRAINED',
                   'legacy_training_options_ignored': True})
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report['status'] == 'READY_FOR_OBSERVATION_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
