#!/usr/bin/env python3
"""Generate honest English and Spanish reports through ABA Signal PRO's real renderer."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import autonomous_betting_agent.magazine_book_export as magazine
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch


def _market(event: str, event_id: str, selection: str, odds: float, probability: float, captured: str, start: str) -> dict:
    return {
        "event": event,
        "event_id": event_id,
        "sport": "Soccer",
        "market_type": "moneyline",
        "selection": selection,
        "prediction": selection,
        "decimal_odds": odds,
        "model_probability": probability,
        "model_market_edge": probability - (1.0 / odds),
        "expected_value_per_unit": probability * odds - 1.0,
        "provider": "ABA test harness",
        "sportsbook": "TEST FIXTURE",
        "captured_at_utc": captured,
        "event_start_utc": start,
        "source_mode": "synthetic_test_fixture",
        "verification_method": "test_fixture",
        "manual_attestation": False,
        "demonstration_mode": True,
    }


def build_fixture(captured: datetime) -> dict:
    captured_text = captured.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    start_text = (captured + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    row = _market("TEST TEAM A vs TEST TEAM B", "test-a-b", "TEST TEAM A", 2.0, 0.60, captured_text, start_text)
    row.update({
        "away_team": "TEST TEAM A",
        "home_team": "TEST TEAM B",
        "season_label": "Soccer Regular Season",
        "report_title": "ABA SIGNAL PRO - BILINGUAL VALIDATION",
        "report_source_label": "Synthetic validation fixture",
        "report_data_scope": "No live sports data; test only.",
        "report_truth_warning": "SYNTHETIC TEST DATA - NOT LIVE SPORTS INFORMATION",
        "sports_context_summary": "SYNTHETIC TEST DATA - NOT LIVE SPORTS INFORMATION",
        "context_status": "No live news, lineup, injury, weather, or odds feed used",
        "matchup_note": "Synthetic fixture used only to validate report completeness and Page 2 calculations.",
        "line_movement_summary": "Unavailable - no live market feed used.",
        "advanced_market_rows": [
            _market("TEST TEAM C vs TEST TEAM D", "test-c-d", "TEST TEAM C", 1.9, 0.58, captured_text, start_text),
            _market("TEST TEAM E vs TEST TEAM F", "test-e-f", "TEST TEAM E", 1.85, 0.59, captured_text, start_text),
        ],
        "parlay_price_quotes": [
            {
                "leg_event_ids": ["test-a-b", "test-c-d"],
                "decimal_odds": 3.72,
                "provider": "ABA test harness",
                "sportsbook": "TEST FIXTURE",
                "captured_at_utc": captured_text,
                "source_mode": "synthetic_test_fixture",
                "verification_method": "test_fixture",
                "manual_attestation": False,
                "demonstration_mode": True,
            },
            {
                "leg_event_ids": ["test-a-b", "test-c-d", "test-e-f"],
                "decimal_odds": 6.85,
                "provider": "ABA test harness",
                "sportsbook": "TEST FIXTURE",
                "captured_at_utc": captured_text,
                "source_mode": "synthetic_test_fixture",
                "verification_method": "test_fixture",
                "manual_attestation": False,
                "demonstration_mode": True,
            },
        ],
    })
    return row


def main() -> None:
    output_dir = Path("output/pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    captured = datetime.now(timezone.utc).replace(microsecond=0)
    fixture = build_fixture(captured)
    renderer = apply_magazine_sale_ready_patch(magazine)
    manifest = {
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "facts_sha256": sha256(json.dumps(fixture, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        "renderer_style": renderer.MAGAZINE_STYLE_VERSION,
        "truth_contract": renderer._ABA_FORCED_TWO_PAGE_TRUTH_RENDERER,
        "reports": {},
    }
    targets = {
        "en": output_dir / "ABA_Signal_PRO_English_Test_Report.pdf",
        "es-MX": output_dir / "ABA_Signal_PRO_Spanish_MX_Test_Report.pdf",
    }
    for language, path in targets.items():
        row = deepcopy(fixture)
        row["report_language"] = language
        payload = renderer.render_full_magazine_book_pdf([row], report_name="ABA Signal PRO", language=language)
        path.write_bytes(payload)
        manifest["reports"][language] = {
            "path": str(path),
            "bytes": len(payload),
            "sha256": sha256(payload).hexdigest(),
        }
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
