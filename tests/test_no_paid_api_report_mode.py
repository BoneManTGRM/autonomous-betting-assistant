from __future__ import annotations

from datetime import datetime, timezone

from autonomous_betting_agent.magazine_live_api_enrichment import (
    enrich_row_with_live_api_data,
    generate_modeled_parlays,
)
from autonomous_betting_agent import magazine_second_page_patch as page2
from autonomous_betting_agent.report_verification_gate import (
    VERIFIED_BUYER_PICK,
    classify_report_row,
)


CAPTURED = "2026-08-31T16:00:00Z"


def _manual_leg(event: str, event_id: str, selection: str, odds: float, probability: float) -> dict:
    return {
        "event": event,
        "manual_event_id": event_id,
        "sport": "Soccer",
        "market_type": "moneyline",
        "selection": selection,
        "decimal_odds": odds,
        "model_probability": probability,
        "model_market_edge": probability - (1.0 / odds),
        "expected_value_per_unit": probability * odds - 1.0,
        "source_mode": "manual_verified",
        "manual_attestation": True,
        "verification_method": "manual",
        "sportsbook": "Bet365",
        "captured_at_utc": CAPTURED,
        "event_start_utc": "2026-08-31T20:00:00Z",
    }


def test_manual_verified_price_is_playable_but_not_labeled_live_api() -> None:
    row = _manual_leg("Alpha vs Beta", "manual-alpha", "Alpha", 2.0, 0.60)
    classified = classify_report_row(row, now=datetime(2026, 8, 31, 16, 5, tzinfo=timezone.utc))

    assert classified["report_verification_class"] == VERIFIED_BUYER_PICK
    assert classified["verification_status"] == "MANUALLY VERIFIED INPUT / PLAYABLE VALUE"
    assert classified["risk"] == "MANUALLY VERIFIED PRICE"
    assert classified["manual_verified_input"] is True
    assert classified["automated_live_provider_verified"] is False


def test_generic_upload_does_not_become_manual_verified() -> None:
    row = _manual_leg("Alpha vs Beta", "manual-alpha", "Alpha", 2.0, 0.60)
    row.update({"source_mode": "uploaded_row", "manual_attestation": False})
    classified = classify_report_row(row, now=datetime(2026, 8, 31, 16, 5, tzinfo=timezone.utc))

    assert classified["report_verification_class"] != VERIFIED_BUYER_PICK
    assert classified["manual_verified_input"] is False


def test_page_two_builds_real_two_leg_chain_from_attested_manual_prices() -> None:
    anchor = _manual_leg("Alpha vs Beta", "manual-alpha", "Alpha", 2.0, 0.60)
    anchor["advanced_market_rows"] = [
        _manual_leg("Gamma vs Delta", "manual-gamma", "Gamma", 1.9, 0.58)
    ]

    parlays, diagnostics = page2.generate_parlay_candidates(anchor)
    conditional = [candidate for candidate in parlays if candidate.status == page2.PARLAY_WATCHLIST and candidate.parlay_type == "2-leg"]

    assert diagnostics["eligible_legs"] == 2
    assert len(conditional) == 1
    candidate = conditional[0]
    assert round(candidate.combined_decimal_odds or 0, 3) == 3.8
    assert round(candidate.combined_probability or 0, 3) == 0.348
    assert round(candidate.combined_ev or 0, 3) == 0.322
    assert candidate.pricing_source == page2.SYNTHETIC_PRODUCT_PRICE
    assert candidate.correlation_risk == "independent product"
    assert candidate.data_quality == "manual verified inputs; exact combined quote required"
    rendered = page2._parlay_line(candidate, "en")
    assert "Alpha vs Beta" in rendered
    assert "Gamma vs Delta" in rendered
    assert "Bet365" in rendered
    assert CAPTURED in rendered
    assert "min " in rendered and "stake " in rendered and "profit " in rendered


def test_exact_leg_matched_manual_parlay_quote_is_playable() -> None:
    anchor = _manual_leg("Alpha vs Beta", "manual-alpha", "Alpha", 2.0, 0.60)
    anchor["advanced_market_rows"] = [
        _manual_leg("Gamma vs Delta", "manual-gamma", "Gamma", 1.9, 0.58)
    ]
    anchor["parlay_price_quotes"] = [{
        "leg_event_ids": ["manual-alpha", "manual-gamma"],
        "decimal_odds": 3.72,
        "sportsbook": "Bet365",
        "captured_at_utc": "now",
        "source_mode": "manual_verified",
        "manual_attestation": True,
        "verification_method": "manual",
    }]

    parlays, diagnostics = page2.generate_parlay_candidates(anchor)
    playable = [candidate for candidate in parlays if candidate.status == page2.PARLAY_PLAYABLE and candidate.parlay_type == "2-leg"]

    assert diagnostics["playable_parlays"] == 1
    assert len(playable) == 1
    candidate = playable[0]
    assert candidate.combined_decimal_odds == 3.72
    assert candidate.pricing_source == page2.SPORTSBOOK_RETURNED_PARLAY_PRICE
    assert candidate.quoted_book == "Bet365"
    assert candidate.quoted_timestamp == "now"


def test_same_game_price_without_joint_model_remains_blocked() -> None:
    anchor = _manual_leg("Alpha vs Beta", "manual-alpha", "Alpha", 2.0, 0.60)
    second = _manual_leg("Alpha vs Beta", "manual-alpha", "Over 2.5", 1.9, 0.58)
    second.update({"market_type": "total", "line": "2.5"})
    anchor.update({"advanced_market_rows": [second], "sportsbook_parlay_price": 3.55, "captured_at_utc": "now", "price_timestamp": "now"})

    parlays, _ = page2.generate_parlay_candidates(anchor)
    same_game = [candidate for candidate in parlays if candidate.parlay_type == "same-game parlay"]

    assert same_game
    assert all(candidate.status == page2.PARLAY_BLOCKED for candidate in same_game)
    assert any("joint probability" in candidate.reason.lower() for candidate in same_game)


def test_iraq_france_negative_ev_upload_has_no_chain_and_no_fake_context(monkeypatch) -> None:
    for names in __import__(
        "autonomous_betting_agent.magazine_live_api_enrichment",
        fromlist=["API_SECRET_DEFS"],
    ).API_SECRET_DEFS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    row = {
        "event": "Iraq vs France",
        "event_id": "iraq-france",
        "sport": "FIFA WORLD CUP",
        "market_type": "total",
        "selection": "Over",
        "line": "2.5",
        "decimal_odds": 1.36,
        "model_probability": 0.71,
        "model_market_edge": -0.021,
        "expected_value_per_unit": -0.029,
        "odds_status": "UPLOADED_ROW",
    }

    enriched = enrich_row_with_live_api_data(row)
    assert "team_snapshot" not in enriched
    assert "injury_report" not in enriched
    assert "matchup_notes" not in enriched
    assert generate_modeled_parlays(row, [{"ev": 0.20}]) == []

    parlays, diagnostics = page2.generate_parlay_candidates(enriched)
    assert diagnostics["playable_parlays"] == 0
    assert not [candidate for candidate in parlays if candidate.status == page2.PARLAY_PLAYABLE]
    sections = page2._page_two_sections(enriched, "en")
    text = "\n".join(item for _title, items, _color in sections for item in items)
    assert "No verified parlay or chain bet qualifies" in text
