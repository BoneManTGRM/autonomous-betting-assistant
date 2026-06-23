from __future__ import annotations

import json

import pandas as pd

from autonomous_betting_agent.app_feed_delivery import build_app_feed
from autonomous_betting_agent.pdf_report import render_report_pdf
from autonomous_betting_agent.report_product_layer import (
    MagazineBrand,
    enrich_rows,
    render_consumer_magazine_html,
    render_markdown_summary,
)
from autonomous_betting_agent.sports_context import enrich_sports_context
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, save_profile, load_profile


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

    contextual = enrich_sports_context(rows, language="es")
    assert "sports_context_summary" in contextual.columns
    assert contextual.loc[0, "sports_context_available"] is True or bool(contextual.loc[0, "sports_context_available"])

    cards = enrich_rows(contextual, language="es")
    cards.loc[cards["sports_context_available"].astype(bool), "game_preview"] = cards.loc[cards["sports_context_available"].astype(bool), "sports_context_summary"]

    assert cards.loc[0, "report_lane"] == "best_play"
    assert bool(cards.loc[0, "publish_ready"]) is True
    assert round(float(cards.loc[0, "market_probability"]), 3) == 0.5
    assert round(float(cards.loc[0, "model_market_edge"]), 3) == 0.12
    assert round(float(cards.loc[0, "expected_value_per_unit"]), 3) == 0.24

    assert cards.loc[1, "report_lane"] == "no_play"
    assert bool(cards.loc[1, "publish_ready"]) is False
    assert cards.loc[2, "report_lane"] == "no_play"
    assert bool(cards.loc[2, "tennis_blocked"]) is True
    assert cards.loc[3, "report_lane"] == "no_play"
    assert cards.loc[4, "report_lane"] == "no_play"
    assert bool(cards.loc[4, "publish_ready"]) is False

    html = render_consumer_magazine_html(cards, MagazineBrand(language="es"))
    assert "ODDS" not in html
    assert "MODEL" not in html
    assert "EDGE" not in html
    assert "Data check" not in html
    assert "Ganador: A" in html
    assert "Total del partido: Más de 10.5" in html

    analyst_html = render_consumer_magazine_html(cards, MagazineBrand(language="en"), mode="analyst")
    assert "Model:" in analyst_html
    assert "Edge:" in analyst_html

    markdown = render_markdown_summary(cards, MagazineBrand(language="en"))
    assert "Today’s Best Plays" in markdown
    assert "Watchlist / Leans" in markdown
    assert "No Play / Removed" in markdown

    pdf = render_report_pdf(cards, MagazineBrand(language="en", workspace_id="smoke"), mode="consumer")
    assert pdf.startswith(b"%PDF-1.4")
    assert b"Today" in pdf

    consumer_feed = build_app_feed(cards, MagazineBrand(language="en", workspace_id="smoke"), mode="consumer", public=False)
    analyst_feed = build_app_feed(cards, MagazineBrand(language="en", workspace_id="smoke"), mode="analyst", public=False)
    assert consumer_feed["visibility"] == "private"
    assert "best_plays" in consumer_feed["groups"]
    consumer_text = json.dumps(consumer_feed)
    analyst_text = json.dumps(analyst_feed)
    assert "model_market_edge" not in consumer_text
    assert "model_market_edge" in analyst_text

    saved_profile = save_profile(WhiteLabelProfile(profile_id="smoke_profile", workspace_id="smoke", brand_name="Smoke Brand", preferred_sports=["baseball"]))
    loaded_profile = load_profile("smoke_profile")
    assert loaded_profile.profile_id == saved_profile.profile_id
    assert loaded_profile.brand_name == "Smoke Brand"
    assert loaded_profile.preferred_sports == ["baseball"]

    avg = cards["model_probability"].dropna().mean()
    assert round(float(avg), 3) == round((0.62 + 0.745 + 0.70 + 0.60) / 4, 3)


if __name__ == "__main__":
    run_smoke_test()
    print("report product layer smoke test passed")
