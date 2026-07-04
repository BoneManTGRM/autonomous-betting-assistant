from autonomous_betting_agent.active_magazine_export_guard import normalize_row


def test_guard_cleans_total_label_and_status():
    row = {
        "market_type": "game total",
        "prediction": "Game Total: Over",
        "line_point": "171.5",
        "decimal_price": 1.70,
        "model_probability": 0.57,
        "model_market_edge": -0.022,
        "expected_value_per_unit": -0.038,
        "odds_status": "UPLOADED_ROW",
        "weather_summary": "Weather: Weather: Sunny.",
    }
    out = normalize_row(row)
    assert out["prediction"] == "Game Total: Over 171.5"
    assert out["risk"] == "PRICE REJECTED"
    assert "Weather: Weather" not in out["weather_summary"]


def test_guard_cleans_spread_label():
    out = normalize_row({"sport": "WNBA", "market_type": "spread", "prediction": "Point Spread: Phoenix Mercury -1.5"})
    assert out["prediction"] == "Spread: Phoenix Mercury -1.5"


def test_guard_converts_mlb_spread_to_run_line():
    out = normalize_row({"sport": "MLB", "market_type": "spread", "prediction": "Point Spread: San Diego Padres +1.5"})
    assert out["prediction"] == "Run Line: San Diego Padres +1.5"


def test_installed_guard_cleans_saved_source_page_two_sections():
    from autonomous_betting_agent import magazine_book_export as renderer
    from autonomous_betting_agent.active_magazine_export_guard import install
    from autonomous_betting_agent import magazine_second_page_patch as page2

    install(renderer)
    row = normalize_row({
        "sport": "MLB",
        "event": "San Diego Padres vs Los Angeles Dodgers",
        "market_type": "spread",
        "prediction": "Point Spread: San Diego Padres +1.5",
        "decimal_price": 1.78,
        "model_probability": 0.58,
        "model_market_edge": 0.022,
        "expected_value_per_unit": 0.040,
        "odds_status": "UPLOADED_ROW",
        "odds_source": "consensus_average",
        "timestamp": "2026-07-02T02:26:25Z",
    })
    rendered = "\n".join(item for _title, rows, _color in page2._page_two_sections(row, "en") for item in rows)
    assert "Run Line: San Diego Padres +1.5" in rendered
    assert "Source type: Saved row with provider/context fields" in rendered
    assert "Current provider match: Recheck required" in rendered
    assert "Stored price: 1.78 from consensus_average" in rendered
    assert "Provider: saved-source" not in rendered
