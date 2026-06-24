from autonomous_betting_agent.daily_chain_report import (
    build_daily_chain_report,
    build_single_game_chain_magazine,
    daily_chain_report_to_rows,
    render_daily_chain_report,
    render_daily_chain_summary_card,
    render_single_game_chain_magazine,
    sanitize_report_filename,
)


def mock_rows():
    return [
        {
            "game": "Yankees vs Red Sox",
            "sport": "MLB Baseball",
            "league": "MLB",
            "start_time": "7:05 PM",
            "sportsbook": "Caliente",
            "exact_bet": "Yankees ML",
            "model_probability": 0.69,
            "edge": 0.054,
            "risk_score": 4.2,
            "main_read": "Yankees ML",
            "correlation_label": "Positive",
            "straight_bet_alternative": "Yankees ML",
            "lineup_status": "Projected starters confirmed",
            "injury_report": "Boston cleanup hitter questionable",
            "weather_impact": "Wind helps right-handed power",
            "market_movement": "Moved -125 to -135",
            "pitcher_handedness": "LHP vs RHB-heavy lineup",
            "bullpen_fatigue": "Boston used top relievers yesterday",
            "why_bullets": "Main read has edge | Prop supports same script",
        },
        {
            "game": "Yankees vs Red Sox",
            "sport": "MLB Baseball",
            "exact_bet": "Judge 1+ Hit",
            "model_probability": 0.66,
            "edge": 0.031,
            "lineup_status": "Projected starters confirmed",
        },
        {
            "game": "Yankees vs Red Sox",
            "sport": "MLB Baseball",
            "exact_bet": "Over 7.5",
            "model_probability": 0.61,
            "edge": 0.022,
            "weather_impact": "Wind helps offense",
        },
        {
            "game": "Dodgers vs Padres",
            "sport": "MLB Baseball",
            "exact_bet": "Random payout filler",
            "model_probability": 0.50,
            "edge": -0.02,
            "filler_leg_risk": "High",
            "was_filler_leg": True,
        },
        {
            "game": "Dodgers vs Padres",
            "sport": "MLB Baseball",
            "exact_bet": "Dodgers ML",
            "model_probability": 0.62,
            "edge": 0.01,
        },
    ]


def test_builds_daily_chain_report_from_mocked_rows():
    report = build_daily_chain_report(mock_rows(), max_cards=5)

    assert report.candidates
    assert report.best_chain is not None
    assert report.best_chain.game == "Yankees vs Red Sox"


def test_selects_best_chain_by_score():
    report = build_daily_chain_report(mock_rows(), max_cards=5)

    scores = [candidate.daily_chain_score for candidate in report.candidates]
    assert scores == sorted(scores, reverse=True)
    assert report.best_chain.daily_chain_score == max(scores)


def test_creates_compact_card_summary():
    report = build_daily_chain_report(mock_rows(), max_cards=3)
    card = render_daily_chain_summary_card(report, title="Marco Daily Chain Summary")

    assert card.startswith("# Marco Daily Chain Summary")
    assert "Daily Summary" in card
    assert "Best Chain" in card


def test_creates_extensive_single_game_magazine():
    game_rows = [row for row in mock_rows() if row["game"] == "Yankees vs Red Sox"]
    game_report = build_single_game_chain_magazine(game_rows)
    magazine = render_single_game_chain_magazine(game_report, title="Yankees Deep Dive")

    assert magazine.startswith("# Yankees Deep Dive")
    assert "Executive Summary" in magazine
    assert "Professional Evidence" in magazine
    assert "Straight vs Chain Decision" in magazine


def test_flags_filler_leg_risk():
    report = build_daily_chain_report(mock_rows(), max_cards=5)

    filler_candidates = [candidate for candidate in report.candidates if candidate.game == "Dodgers vs Padres"]
    assert filler_candidates
    assert any(candidate.filler_leg_risk == "High" for candidate in filler_candidates)


def test_shows_straight_bet_alternative():
    report = build_daily_chain_report(mock_rows(), max_cards=3)
    markdown = render_daily_chain_report(report)

    assert "Straight Alternative" in markdown
    assert "Yankees ML" in markdown


def test_handles_no_qualifying_chains_safely():
    report = build_daily_chain_report([], max_cards=3)
    markdown = render_daily_chain_report(report)

    assert report.best_chain is None
    assert "NO CHAIN RECOMMENDED TODAY" in markdown


def test_works_without_live_api_keys():
    report = build_daily_chain_report(mock_rows(), max_cards=3, learning_memory=None)

    assert report.candidates
    assert "No chain learning memory" in report.learning_warnings[0]


def test_exports_rows_for_csv():
    report = build_daily_chain_report(mock_rows(), max_cards=3)
    rows = daily_chain_report_to_rows(report)

    assert rows[0]["row_type"] == "metadata"
    assert any(row.get("row_type") == "chain_candidate" for row in rows)


def test_does_not_break_existing_magazine_imports():
    from autonomous_betting_agent.bet_catalog import build_catalog_pick

    pick = build_catalog_pick(mock_rows()[0])
    assert pick.game == "Yankees vs Red Sox"


def test_daily_report_uses_editable_title():
    report = build_daily_chain_report(mock_rows())
    markdown = render_daily_chain_report(report, title="Marco Daily Chain Report")

    assert markdown.startswith("# Marco Daily Chain Report")


def test_single_game_report_uses_editable_title():
    game_report = build_single_game_chain_magazine(mock_rows()[:3])
    markdown = render_single_game_chain_magazine(game_report, title="Yankees vs Red Sox Deep Dive")

    assert markdown.startswith("# Yankees vs Red Sox Deep Dive")


def test_sanitize_report_filename():
    assert sanitize_report_filename("Marco Daily Chain Report", "md") == "marco_daily_chain_report.md"
    assert sanitize_report_filename("Yankees vs Red Sox Deep Dive", "md") == "yankees_vs_red_sox_deep_dive.md"
