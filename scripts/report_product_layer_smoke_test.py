from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_product_layer import (
    MagazineBrand,
    enrich_rows,
    render_consumer_magazine_html,
    render_markdown_summary,
)


def run_smoke_test() -> None:
    rows = pd.DataFrame(
        [
            {
                "event": "A at B",
                "sport": "baseball",
                "prediction": "Moneyline: A",
                "learned_model_probability": 0.62,
                "decimal_price": 2.0,
                "odds_source": "The Odds API",
                "proof_id": "P1",
                "pitching_matchup": "Projected starter advantage available.",
            },
            {
                "event": "C at D",
                "sport": "boxing",
                "prediction": "Game total: Over 10.5",
                "learned_model_probability": 0.745,
                "decimal_price": 1.30,
                "odds_source": "The Odds API",
                "proof_id": "P2",
            },
            {
                "event": "E at F",
                "sport": "tennis",
                "prediction": "Moneyline: E",
                "learned_model_probability": 0.70,
                "decimal_price": 2.0,
                "odds_source": "The Odds API",
                "proof_id": "P3",
            },
            {
                "event": "G at H",
                "sport": "basketball",
                "prediction": "Game total: Under 210.5",
                "learned_model_probability": 0.60,
                "odds_source": "api limit",
            },
            {
                "event": "I at J",
                "sport": "soccer",
                "prediction": "Point spread: I +0",
                "model_probability": 0.50,
                "model_probability_source": "base_market_probability_no_learning_adjustment",
                "decimal_price": 2.0,
                "odds_source": "The Odds API",
            },
        ]
    )

    cards = enrich_rows(rows, language="es")

    assert cards.loc[0, "report_lane"] == "best_play"
    assert bool(cards.loc[0, "publish_ready"]) is True
    assert round(float(cards.loc[0, "market_probability"]), 3) == 0.5
    assert round(float(cards.loc[0, "model_market_edge"]), 3) == 0.12
    assert round(float(cards.loc[0, "expected_value_per_unit"]), 3) == 0.24

    assert cards.loc[1, "report_lane"] == "no_play"
    assert bool(cards.loc[1, "publish_ready"]) is False
    assert cards.loc[2, "report_lane"] == "no_play"
    assert cards.loc[3, "report_lane"] == "no_play"
    assert cards.loc[4, "report_lane"] == "no_play"

    html = render_consumer_magazine_html(cards, MagazineBrand(language="es"))
    assert "ODDS" not in html
    assert "MODEL" not in html
    assert "EDGE" not in html
    assert "Data check" not in html
    assert "Ganador: A" in html
    assert "Total del partido: Más de 10.5" in html

    markdown = render_markdown_summary(cards, MagazineBrand(language="en"))
    assert "Today’s Best Plays" in markdown
    assert "Watchlist / Leans" in markdown
    assert "No Play / Removed" in markdown


if __name__ == "__main__":
    run_smoke_test()
    print("report_product_layer smoke test passed")
