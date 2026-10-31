from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

from autonomous_betting_agent.report_export_verification import blocked_pdf, manifest, prepare_export_rows


def verify_rows_before_pdf_export(rows, *, require_verified: bool = True):
    return prepare_export_rows(rows, require_verified=require_verified)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ABA Signal Pro rows before PDF export.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--verified-output", type=Path, default=Path("data/verified_export_rows.csv"))
    parser.add_argument("--blocked-output", type=Path, default=Path("data/blocked_export_rows.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/export_verification_manifest.json"))
    parser.add_argument("--blocked-pdf", type=Path, default=Path("data/export_blocked.pdf"))
    parser.add_argument("--allow-unverified", action="store_true")
    args = parser.parse_args()

    frame = pd.read_csv(args.input_csv)
    verified, summary, blocked = verify_rows_before_pdf_export(frame.to_dict("records"), require_verified=not args.allow_unverified)

    args.verified_output.parent.mkdir(parents=True, exist_ok=True)
    args.blocked_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(verified).to_csv(args.verified_output, index=False)
    pd.DataFrame(blocked).to_csv(args.blocked_output, index=False)
    args.manifest_output.write_text(manifest(summary, blocked), encoding="utf-8")
    if blocked:
        args.blocked_pdf.write_bytes(blocked_pdf(summary, blocked))
        print(f"Export blocked for {len(blocked)} row(s). See {args.manifest_output}.", file=sys.stderr)
        return 2
    print(f"Export verification passed for {len(verified)} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
