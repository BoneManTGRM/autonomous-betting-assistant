import json

from autonomous_betting_agent import pro_recommendation_cards as cards


def _optimizer_report():
    return {
        "workspace_id": "test_01",
        "preview_only": True,
        "market_hunter_rows": _market_rows(),
        "chain_builder_rows": _chain_rows(),
    }


def _market_rows():
    return [
        {
            "event_id": "e1",
            "event": "A vs B",
            "sport": "tennis",
            "sportsbook": "Book A",
            "market_type": "moneyline",
            "selection": "A",
            "decimal_odds": 2.1,
            "calibrated_probability": 0.58,
            "calibrated_edge": 0.104,
            "ev": 0.218,
            "risk_level": "LOW",
            "suggested_stake_units": 20,
            "chain_eligible": True,
            "final_action": "PLAYABLE VALUE",
            "why_value": "positive EV 0.218",
        },
        {
            "event_id": "e2",
            "event": "C vs D",
            "sport": "soccer",
            "sportsbook": "Book B",
            "market_type": "correct_score",
            "selection": "1-0",
            "decimal_odds": 6.0,
            "calibrated_probability": 0.10,
            "calibrated_edge": -0.066,
            "ev": -0.4,
            "risk_level": "HIGH",
            "chain_eligible": False,
            "final_action": "NO BET",
            "blockers": ["unsupported market type", "non-positive calibrated EV"],
        },
    ]


def _chain_rows():
    return [
        {
            "chain_id": "chain_1",
            "events": ["e1", "e3"],
            "selections": ["A", "E"],
            "combined_decimal_odds": 3.8,
            "combined_probability": 0.34,
            "combined_ev": 0.292,
            "final_action": "CHAIN PREVIEW",
        }
    ]


def _context_rows():
    return [
        {
            "event_id": "e1",
            "form": "A has better recent form",
            "injuries": "No known injury flag",
            "recent_performance": "A has won recent matches",
            "head_to_head": "A leads series",
            "home_away": "neutral",
            "rest_travel": "normal rest",
            "motivation_context": "high motivation",
            "market_movement": "price improved",
            "public_consensus": "market not overloaded",
        }
    ]


def test_build_recommendation_card_contains_issue_51_format():
    ctx = cards.context_map(_context_rows())["e1"]
    card = cards.build_recommendation_card(_market_rows()[0], ctx, _chain_rows())

    for field in cards.CARD_FIELDS:
        assert field in card
    assert card["final_recommendation"] == "BET"
    assert card["single_bet_rating"] == "A"
    assert card["best_chain_pairing"] == "chain_1"
    assert "positive EV" in card["why_this_bet"]
    assert "injuries risk" in card["why_it_could_fail"]
    assert card["mode"] == "PREVIEW ONLY"


def test_final_recommendation_maps_optimizer_actions():
    assert cards.final_recommendation("PLAYABLE VALUE") == "BET"
    assert cards.final_recommendation("WATCH ONLY") == "WATCH"
    assert cards.final_recommendation("WAIT FOR BETTER ODDS") == "WATCH"
    assert cards.final_recommendation("NO BET") == "AVOID"


def test_profit_score_penalizes_high_risk_negative_ev():
    good = cards.profit_score(_market_rows()[0])
    bad = cards.profit_score(_market_rows()[1])

    assert good > bad


def test_build_pro_recommendation_cards_from_report_exports():
    report = cards.build_pro_recommendation_cards("test_01", _optimizer_report(), context_rows=_context_rows())
    payload = json.loads(cards.export_recommendation_cards_json(report))
    marco = json.loads(cards.export_marco_cards_json(report))

    assert payload["schema_version"] == "pro_recommendation_cards_v1"
    assert payload["cards_status"] == "RECOMMENDATION CARDS READY"
    assert payload["card_count"] == 2
    assert payload["bet_count"] == 1
    assert payload["avoid_count"] == 1
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert marco and "source_action" not in json.dumps(marco)
    assert "final_recommendation" in cards.export_recommendation_cards_csv(report)
    assert "check_id" in cards.export_completion_checks_csv(report)
    assert "cards_hash" in cards.export_recommendation_manifest_json(report)


def test_build_pro_recommendation_cards_from_text():
    optimizer_json = json.dumps(_optimizer_report())
    context_csv = cards.csv_from_rows(_context_rows())
    report = cards.build_pro_recommendation_cards_from_text("test_01", optimizer_json, "", "", context_csv)

    assert report["card_count"] == 2
    assert report["cards_status"] == "RECOMMENDATION CARDS READY"


def test_build_pro_recommendation_cards_blocks_empty_input():
    report = cards.build_pro_recommendation_cards("test_01", {})

    assert report["cards_status"] == "BLOCKED"
    assert any(row["status"] == "FAIL" for row in report["completion_checks"])


def test_pro_recommendation_cards_has_no_external_client_paths():
    source = open("autonomous_betting_agent/pro_recommendation_cards.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
