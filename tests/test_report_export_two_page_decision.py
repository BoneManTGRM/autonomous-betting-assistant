import pandas as pd

from autonomous_betting_agent.report_export_service import build_report_export_bundle
from autonomous_betting_agent.report_product_layer import MagazineBrand


def _brand() -> MagazineBrand:
    return MagazineBrand(brand_name="ABA Signal Pro", tagline="Powered by Reparodynamics", report_title="Daily Sports Analysis")


def test_report_export_bundle_includes_two_page_decision_columns_and_markdown():
    rows = pd.DataFrame([
        {
            "event": "Mexico vs Ecuador",
            "sport": "soccer",
            "prediction": "Mexico ML",
            "market_type": "moneyline",
            "decimal_odds": 2.0,
            "model_probability": 0.60,
            "market_completeness_status": "complete",
            "sportsbook": "Book A",
            "sportsbook_count": 2,
            "odds_timestamp": "2026-07-02T04:00:00Z",
        },
        {
            "event": "Brazil vs Chile",
            "sport": "soccer",
            "prediction": "Brazil Over 1.5",
            "market_type": "team total",
            "decimal_odds": 1.95,
            "model_probability": 0.58,
            "market_completeness_status": "complete",
            "sportsbook": "Book B",
            "sportsbook_count": 2,
            "odds_timestamp": "2026-07-02T04:00:00Z",
        },
    ])

    bundle = build_report_export_bundle(rows, _brand())

    assert "two_page_raw_EV" in bundle.csv_text
    assert "two_page_bet_status" in bundle.csv_text
    assert "Two-Page Betting Decision Engine" in bundle.markdown
    assert "Provider Capability Audit" in bundle.markdown
    assert bundle.decision_markdown
    assert "raw_EV" in bundle.decision_csv_text
    assert "pregame_odds_available" in bundle.provider_capability_csv_text
    assert bundle.page1_decision is not None
    assert bundle.page2_decision is not None
    assert bundle.provider_capabilities


def test_report_export_bundle_keeps_unavailable_page2_markets_honest():
    rows = pd.DataFrame([
        {
            "event": "A vs B",
            "sport": "soccer",
            "prediction": "A ML",
            "market_type": "moneyline",
            "decimal_odds": 2.1,
            "model_probability": 0.52,
            "market_completeness_status": "complete",
            "sportsbook": "consensus_average",
        }
    ])

    bundle = build_report_export_bundle(rows, _brand())

    assert "Data unavailable" in bundle.decision_markdown
    assert "Flash bet unavailable: missing live event feed." in bundle.decision_markdown
    assert "consensus-only" in bundle.csv_text
