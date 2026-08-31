from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import autonomous_betting_agent.magazine_book_export as renderer
from autonomous_betting_agent.magazine_live_api_enrichment import install as install_enrichment
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch


def _leg(event: str, event_id: str, selection: str, odds: float, probability: float, captured: str, start: str) -> dict:
    return {
        "event": event,
        "public_event": event,
        "manual_event_id": event_id,
        "sport": "Soccer",
        "league": "DEMONSTRATION DATA",
        "market_type": "moneyline",
        "selection": selection,
        "prediction": selection,
        "decimal_odds": odds,
        "model_probability": probability,
        "model_market_edge": probability - (1.0 / odds),
        "expected_value_per_unit": probability * odds - 1.0,
        "source_mode": "manual_verified",
        "manual_attestation": True,
        "verification_method": "manual",
        "sportsbook": "Demo Sportsbook",
        "bookmaker": "Demo Sportsbook",
        "captured_at_utc": captured,
        "price_timestamp": captured,
        "event_start_utc": start,
        "report_source_label": "Operator-attested demonstration input",
        "report_data_scope": "Demonstration only - not a current betting recommendation",
        "report_truth_warning": "DEMONSTRATION DATA. Replace every price with a current operator-observed sportsbook price.",
        "demonstration_mode": True,
        "report_language": "en",
    }


def build_fixture() -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    captured = now.isoformat().replace("+00:00", "Z")
    start = (now + timedelta(hours=4)).isoformat().replace("+00:00", "Z")
    anchor = _leg("North Stars vs Harbor City", "demo-north-harbor", "North Stars", 2.00, 0.60, captured, start)
    anchor.update({
        "away_team": "North Stars",
        "home_team": "Harbor City",
        "report_title": "ABA SIGNAL PRO - HYBRID MODE VALIDATION",
        "why_bullets": "Operator supplied a named book, exact market, price, and UTC capture time.\nModel probability and market-implied probability are shown separately.\nPositive edge and EV passed the report gate.",
        "team_snapshot": "Demonstration data only; no live team API was queried.",
        "injury_report": "Not supplied. No injury conclusion is made.",
        "matchup_notes": "Demonstration fixture used to validate report completeness and Page 2 math.",
        "sports_context_summary": "Demonstration fixture used to validate report completeness and Page 2 math.",
        "target_stake_units": 0.10,
        "advanced_market_rows": [
            _leg("River Athletic vs Mountain FC", "demo-river-mountain", "River Athletic", 1.90, 0.58, captured, start),
            _leg("Capital United vs Coastal Town", "demo-capital-coastal", "Capital United", 1.85, 0.59, captured, start),
        ],
        "parlay_price_quotes": [
            {
                "leg_event_ids": ["demo-north-harbor", "demo-river-mountain"],
                "decimal_odds": 3.72,
                "sportsbook": "Demo Sportsbook",
                "captured_at_utc": captured,
                "source_mode": "manual_verified",
                "manual_attestation": True,
                "verification_method": "manual",
            },
            {
                "leg_event_ids": ["demo-north-harbor", "demo-capital-coastal"],
                "decimal_odds": 3.60,
                "sportsbook": "Demo Sportsbook",
                "captured_at_utc": captured,
                "source_mode": "manual_verified",
                "manual_attestation": True,
                "verification_method": "manual",
            },
            {
                "leg_event_ids": ["demo-north-harbor", "demo-river-mountain", "demo-capital-coastal"],
                "decimal_odds": 6.85,
                "sportsbook": "Demo Sportsbook",
                "captured_at_utc": captured,
                "source_mode": "manual_verified",
                "manual_attestation": True,
                "verification_method": "manual",
            },
        ],
    })
    return anchor


def main() -> None:
    active_renderer = apply_magazine_sale_ready_patch(install_enrichment(importlib.reload(renderer)))
    output = Path("output/pdf/ABA_Signal_PRO_Hybrid_Mode_Full_Report.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(active_renderer.render_full_magazine_book_pdf([build_fixture()], report_name="ABA Signal PRO", language="en"))
    print(output.resolve())


if __name__ == "__main__":
    main()
