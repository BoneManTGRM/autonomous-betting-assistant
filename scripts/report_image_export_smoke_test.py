from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_image_export_service import (
    PNG_HEADER,
    card_image_filename,
    render_card_deck_png,
    render_card_png,
    render_magazine_summary_png,
    safe_filename_part,
)
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat
from autonomous_betting_agent.report_product_layer import MagazineBrand, enrich_rows


def sample_cards() -> pd.DataFrame:
    rows = pd.DataFrame([
        {"event": "Official Edge / Team A @ Team B", "sport": "MLB", "prediction": "Moneyline: A", "learned_model_probability": 0.62, "decimal_price": 2.10, "odds_source": "The Odds API", "proof_id": "P1", "grade": "WIN"},
        {"event": "High Probability Winner", "sport": "Boxing", "prediction": "Game total: Over 10.5", "learned_model_probability": 0.745, "decimal_price": 1.30, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "Missing Odds", "sport": "WNBA", "prediction": "Moneyline: B", "learned_model_probability": 0.66, "odds_source": "api limit", "grade": "PENDING"},
        {"event": "Unsupported Tennis", "sport": "tennis", "prediction": "Moneyline: C", "learned_model_probability": 0.72, "decimal_price": 2.00, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "", "sport": "", "prediction": "", "odds_source": "", "grade": ""},
    ])
    return apply_learning_layer_compat(enrich_rows(rows))


def assert_png(payload: bytes, label: str) -> None:
    assert isinstance(payload, bytes), label
    assert payload.startswith(PNG_HEADER), label
    assert len(payload) > 5000, f"{label} was too small to be a useful image"


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Image Smoke Test", workspace_id="image_test")
    cards = sample_cards()
    first = cards.iloc[0].to_dict()
    assert_png(render_card_png(first, brand), "single-card PNG")
    assert_png(render_card_deck_png(cards, brand), "card-deck PNG")
    assert_png(render_magazine_summary_png(cards, brand), "magazine-summary PNG")

    for idx, row in cards.iterrows():
        assert_png(render_card_png(row.to_dict(), brand), f"row {idx} PNG")

    filename = card_image_filename(first, workspace="Test Workspace / A", index=0)
    assert filename.endswith(".png")
    assert "/" not in filename and " " not in filename
    assert filename.startswith("test_workspace_a_001_")
    assert safe_filename_part("Bad / Name @ 100%") == "bad_name_100"

    empty_card = render_card_png({}, brand)
    assert_png(empty_card, "empty-card PNG")


if __name__ == "__main__":
    run_smoke_test()
    print("report image export smoke test passed")
