from __future__ import annotations

from autonomous_betting_agent.report_studio_spanish_ui import selected_raw_sport_values, sport_league_display_text


def test_sport_league_display_text_spanish():
    assert sport_league_display_text("Boxing", "es") == "Boxeo"
    assert sport_league_display_text("FIFA World Cup", "es") == "Copa Mundial FIFA"
    assert sport_league_display_text("League of Ireland", "es") == "Liga de Irlanda"
    assert sport_league_display_text("Brazil Série B", "es") == "Brasil Série B"
    assert sport_league_display_text("Brazil Serie B", "es") == "Brasil Série B"
    assert sport_league_display_text("NCAA Baseball", "es") == "Béisbol NCAA"
    assert sport_league_display_text("Allsvenskan - Sweden", "es") == "Allsvenskan - Suecia"
    assert sport_league_display_text("Eliteserien - Norway", "es") == "Eliteserien - Noruega"
    assert sport_league_display_text("Veikkausliiga - Finland", "es") == "Veikkausliiga - Finlandia"
    assert sport_league_display_text("MLB", "es") == "MLB"
    assert sport_league_display_text("Boxing", "en") == "Boxing"


def test_spanish_display_labels_map_back_to_raw_values():
    options = ["Boxing", "FIFA World Cup", "League of Ireland", "MLB", "Brazil Serie B"]
    assert selected_raw_sport_values(["Boxeo", "Liga de Irlanda"], options, "es") == ["Boxing", "League of Ireland"]
    assert selected_raw_sport_values(["Boxing", "MLB"], options, "es") == ["Boxing", "MLB"]
    assert selected_raw_sport_values(["Brasil Série B"], options, "es") == ["Brazil Serie B"]
