from autonomous_betting_agent.magazine_live_api_enrichment import enrich_row_with_live_api_data


def test_spanish_report_enrichment_translates_dynamic_text_fields():
    row = {
        "report_language": "es",
        "event": "Iraq at France",
        "prediction": "TOTAL DEL PARTIDO: MÁS DE 2.5",
        "model_probability": 0.71,
        "market_probability": 0.73,
        "model_market_edge": -0.021,
        "expected_value_per_unit": -0.029,
        "final_decision": "WATCHLIST",
        "bookmaker": "consensus average",
        "news_injury_summary": "No lineup/injury headline returned.",
        "api_football_summary": "API-FB: no fixture match.",
    }

    enriched = enrich_row_with_live_api_data(row)
    combined = "\n".join(str(enriched.get(key, "")) for key in ("why_bullets", "risk_reason", "parlay_notes", "final_explanation"))

    assert enriched["final_decision"] == "LISTA DE SEGUIMIENTO"
    assert enriched["bookmaker"] == "promedio consenso"
    assert enriched["news_injury_summary"] == "Sin titular de lesiones/alineación."
    assert enriched["api_football_summary"] == "API-FB: sin coincidencia de partido."
    assert "El modelo proyecta" in combined
    assert "La probabilidad implícita" in combined
    assert "No encadenar señales" in combined
    assert "No jugar con la cuota listada" in combined
