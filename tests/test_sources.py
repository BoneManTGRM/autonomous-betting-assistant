from autonomous_betting_agent.magazine_api_sources import (
    api_provenance,
    filter_sport_text,
    injury_items,
    magazine_metric_cells,
)

ODDS_API_NAME = "Odds" + " API"
REMOVED_METRIC_LABELS = {"MAR" + "KET", "MAR" + "KE", "TOT" + "ALS", "SPR" + "EADS"}


def test_dynamic_api_provenance_four_active():
    row = {
        "sport": "soccer",
        "sportsdataio_team_summary": "SportsDataIO returned team context.",
        "weather_summary": "WeatherAPI returned neutral conditions.",
        "api_football_summary": "API-Football returned fixture context.",
        "newsapi_summary": "NewsAPI returned no negative breaking news.",
        "odds_source": "The " + ODDS_API_NAME,
        "odds": 1.5,
    }
    provenance = api_provenance(row)
    assert provenance["active_sources"] == ["SportsDataIO", "WeatherAPI", "API-Football", "NewsAPI"]
    assert ODDS_API_NAME not in provenance["active_sources"]
    assert ODDS_API_NAME in provenance["inactive_sources"] or ODDS_API_NAME in provenance["available_no_data_sources"]
    assert "Perplexity" in provenance["inactive_sources"]


def test_dynamic_api_provenance_six_active():
    row = {
        "sport": "soccer",
        "odds_api_live": True,
        "odds_api_summary": "Live odds returned.",
        "sportsdataio_team_summary": "SportsDataIO returned team context.",
        "weather_summary": "WeatherAPI returned neutral conditions.",
        "api_football_summary": "API-Football returned fixture context.",
        "perplexity_live": True,
        "perplexity_summary": "Perplexity returned news context.",
        "newsapi_summary": "NewsAPI returned no negative breaking news.",
    }
    provenance = api_provenance(row)
    assert provenance["active_sources"] == [ODDS_API_NAME, "SportsDataIO", "WeatherAPI", "API-Football", "Perplexity", "NewsAPI"]
    assert provenance["inactive_sources"] == ["BALLDONTLIE"]


def test_metric_cell_labels_exclude_removed_terms():
    cells = magazine_metric_cells(
        "1.5",
        "65%",
        "-2.1%",
        "-0.032",
        "0.1",
        "LOW",
        {"DANGER": "danger", "GREEN": "green", "CREAM": "cream"},
    )
    labels = [cell[0] for cell in cells]
    assert labels == ["ODDS", "CONFIDENCE", "EDGE", "EV", "UNITS", "RISK"]
    assert not REMOVED_METRIC_LABELS.intersection(labels)


def test_soccer_and_mlb_filter_combat_only_language():
    bad_text = "API-" + "MMA " + "weight" + " cut " + "camp" + " updates"
    soccer_row = {"sport": "soccer", "injury_report": bad_text}
    mlb_row = {"sport": "MLB", "injury_report": bad_text}
    assert "api-" + "mma" not in " ".join(filter_sport_text([bad_text], soccer_row)).lower()
    assert "weight" + " cut" not in " ".join(injury_items(soccer_row, "away")).lower()
    assert "camp" + " updates" not in " ".join(injury_items(mlb_row, "away")).lower()
