from __future__ import annotations

from autonomous_betting_agent import magazine_book_export as magazine
from autonomous_betting_agent.magazine_sale_ready_patch import (
    _es,
    apply_magazine_sale_ready_patch,
    sale_ready_matchup_items,
    translate_country_terms_in_text,
    translate_team_label,
)


def test_global_spanish_country_team_labels():
    pairs = {
        "Haiti": "HAITÍ",
        "Morocco": "MARRUECOS",
        "Canada": "CANADÁ",
        "Switzerland": "SUIZA",
        "Brazil": "BRASIL",
        "Scotland": "ESCOCIA",
        "Uzbekistan": "UZBEKISTÁN",
        "Belgium": "BÉLGICA",
        "New Zealand": "NUEVA ZELANDA",
        "Panama": "PANAMÁ",
        "Netherlands": "PAÍSES BAJOS",
        "Ivory Coast": "COSTA DE MARFIL",
        "Curacao": "CURAZAO",
        "Iran": "IRÁN",
        "Egypt": "EGIPTO",
    }
    for source, expected in pairs.items():
        assert translate_team_label(source, "es").upper() == expected


def test_country_terms_translate_inside_events_with_safe_boundaries():
    examples = {
        "Haiti vs Morocco": "Haití vs Marruecos",
        "Canada vs Switzerland": "Canadá vs Suiza",
        "Brazil vs Scotland": "Brasil vs Escocia",
        "Uzbekistan vs Portugal": "Uzbekistán vs Portugal",
        "Belgium vs New Zealand": "Bélgica vs Nueva Zelanda",
        "Croatia vs Panama": "Croacia vs Panamá",
        "Netherlands vs Tunisia": "Países Bajos vs Túnez",
        "Ivory Coast vs Curacao": "Costa de Marfil vs Curazao",
        "Iran vs Egypt": "Irán vs Egipto",
    }
    for source, expected in examples.items():
        assert translate_country_terms_in_text(source, "es") == expected


def test_spanish_translation_layer_patches_base_renderer_labels():
    apply_magazine_sale_ready_patch(magazine)

    assert magazine._team_label("Haiti", "es").upper() == "HAITÍ"
    assert magazine._team_label("Morocco", "es").upper() == "MARRUECOS"
    assert magazine._team_label("Belgium", "es").upper() == "BÉLGICA"
    assert magazine._team_label("Uzbekistan", "es").upper() == "UZBEKISTÁN"
    assert magazine._tr("Haiti vs Morocco", "es") == "Haití vs Marruecos"


def test_non_country_names_and_provider_brands_are_protected():
    assert _es("Liam Paro vs Lewis Crocker", "es") == "Liam Paro vs Lewis Crocker"
    for brand in (
        "The Odds API",
        "Odds API",
        "SportsDataIO",
        "WeatherAPI",
        "API-Football",
        "NewsAPI",
        "Perplexity",
        "Playdoit",
    ):
        assert _es(brand, "es") == brand
    assert _es("The Cuotas API", "es") == "The Odds API"


def test_spanish_weather_matchup_notes_are_readable_and_translated():
    row = {
        "report_language": "es",
        "event_name": "Haiti vs Morocco",
        "away_team": "Haiti",
        "home_team": "Morocco",
        "weather_summary": "Weather: Light rain, 23.3°C, wind 5.8 kph. Location: Philadelphia, Pennsylvania, United States of America.",
        "api_football_summary": "API-FB lookup checked Haiti / Morocco; no match returned.",
        "newsapi_summary": "News checked; no injury/lineup headline.",
    }

    text = "\n".join(sale_ready_matchup_items(row))

    assert "Clima:" in text
    assert "lluvia ligera" in text
    assert "viento" in text
    assert "Ubicación:" in text or "Ubic.:" in text
    assert "Estados Unidos" in text
    assert "Weather:" not in text
    assert "Light rain" not in text
    assert "wind" not in text
    assert "United States of America" not in text


def test_tipster_brand_changes_full_magazine_masthead_output():
    apply_magazine_sale_ready_patch(magazine)
    row = {
        "report_language": "es",
        "event_name": "Haiti vs Morocco",
        "away_team": "Haiti",
        "home_team": "Morocco",
        "report_title": "Análisis Deportivo Diario",
        "pick": "Game total: Over 2.5",
        "model_probability": "0.71",
        "market_probability": "0.73",
        "model_market_edge": "-0.021",
        "expected_value_per_unit": "-0.029",
    }

    aba = magazine.render_full_pick_magazine_page_png(row, report_name="ABA Signal Pro", language="es")
    los_reyes = magazine.render_full_pick_magazine_page_png(row, report_name="LOS REYES", language="es")

    assert "sale_ready_risk_chain_v4" in magazine.MAGAZINE_STYLE_VERSION
    assert aba != los_reyes
