from autonomous_betting_agent.magazine_live_api_enrichment import enrich_rows_with_live_api_data


def test_enriched_report_page_rows_collapse_same_event_after_live_api_layer():
    rows = [
        {
            "report_language": "en",
            "event": "Mexico at Czech Republic",
            "public_event": "Mexico at Czech Republic",
            "public_action": "Price Watch / Research",
            "market": "totals",
        },
        {
            "report_language": "en",
            "event": "Mexico at Czech Republic",
            "public_event": "Mexico at Czech Republic",
            "public_action": "Research / Track for Learning",
            "market": "spread",
        },
        {
            "report_language": "en",
            "event": "Germany at Ecuador",
            "public_event": "Germany at Ecuador",
            "public_action": "Price Watch / Research",
            "market": "totals",
        },
    ]

    enriched = enrich_rows_with_live_api_data(rows)

    assert len(enriched) == 2
    assert [row["event"] for row in enriched] == ["Mexico at Czech Republic", "Germany at Ecuador"]
