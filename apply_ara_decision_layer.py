from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.ara_filters import apply_ara_decision_layer, dedupe_ara_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply ARA odds/weather decision filters to a prediction CSV.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("pro_predictor_with_ara_decision_layer.csv"))
    parser.add_argument("--deduped-output", type=Path, default=Path("pro_predictor_deduped_with_ara_decision_layer.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.input_csv)
    enriched = apply_ara_decision_layer(frame)
    enriched.to_csv(args.output, index=False)
    dedupe_ara_records(enriched).to_csv(args.deduped_output, index=False)
    print(f"Saved enriched CSV to {args.output}")
    print(f"Saved deduped CSV to {args.deduped_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
