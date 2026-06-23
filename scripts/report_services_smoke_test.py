from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_export_service import build_report_export_bundle
from autonomous_betting_agent.report_feed_service import build_report_feed
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat
from autonomous_betting_agent.report_product_layer import MagazineBrand, enrich_rows


def sample_cards() -> pd.DataFrame:
    rows = pd.DataFrame([
        {"event": "Official Edge", "sport": "MLB", "prediction": "Moneyline: A", "learned_model_probability": 0.62, "decimal_price": 2.10, "odds_source": "The Odds API", "proof_id": "P1", "grade": "WIN"},
        {"event": "High Probability Research", "sport": "Boxing", "prediction": "Game total: Over 10.5", "learned_model_probability": 0.745, "decimal_price": 1.30, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "Missing Odds", "sport": "WNBA", "prediction": "Moneyline: B", "learned_model_probability": 0.66, "odds_source": "api limit", "grade": "PENDING"},
        {"event": "Unsupported Tennis", "sport": "tennis", "prediction": "Moneyline: C", "learned_model_probability": 0.72, "decimal_price": 2.00, "odds_source": "The Odds API", "grade": "WIN"},
    ])
    return apply_learning_layer_compat(enrich_rows(rows))


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Service Smoke Test", workspace_id="service_test")
    cards = sample_cards()
    feed = build_report_feed(cards, brand)
    assert feed["schema_version"] == "aba-report-feed-v2"
    assert feed["counts"]["total_cards"] == 4
    assert feed["counts"]["official_publish_ready"] == 1
    assert feed["counts"]["client_report_ready"] == 2
    assert feed["counts"]["data_issues"] == 2
    assert feed["counts"]["graded_results"] == 2
    assert len(feed["groups"]["official_ev"]) == 1
    assert len(feed["groups"]["data_blocked"]) == 2
    assert all(row.get("event") != "Unsupported Tennis" for row in feed["groups"]["graded_results"])

    bundle = build_report_export_bundle(cards, brand)
    assert bundle.html
    assert bundle.markdown
    assert bundle.whatsapp
    assert bundle.json_text
    assert bundle.csv_text
    assert bundle.pdf_bytes.startswith(b"%PDF")
    assert bundle.feed["counts"]["total_cards"] == 4
    assert "Price Watch" in bundle.whatsapp or "Research" in bundle.whatsapp
    assert "No Play" not in bundle.html
    assert "No Play" not in bundle.markdown
    assert "No Play" not in bundle.whatsapp


if __name__ == "__main__":
    run_smoke_test()
    print("report services smoke test passed")
