from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_STUDIO = ROOT / "pages" / "report_studio.py"


def _source() -> str:
    return REPORT_STUDIO.read_text(encoding="utf-8")


def test_report_studio_imports_api_enrichment_helpers() -> None:
    text = _source()
    assert "ENRICHMENT_VERSION" in text
    assert "enrich_rows_with_live_api_data" in text
    assert "from autonomous_betting_agent.magazine_live_api_enrichment import" in text


def test_cards_as_rows_are_enriched_before_book_rendering() -> None:
    text = _source()
    enrich_pos = text.index("cards_as_rows = enrich_rows_with_live_api_data")
    book_png_pos = text.index("render_full_magazine_book_png(cards_as_rows")
    book_pdf_pos = text.index("render_full_magazine_book_pdf(cards_as_rows")
    book_zip_pos = text.index("render_full_magazine_zip(cards_as_rows")
    assert enrich_pos < book_png_pos < book_pdf_pos < book_zip_pos


def test_selected_page_uses_enriched_rows_and_cache_version() -> None:
    text = _source()
    assert "selected_row = cards_as_rows[int(selected_idx)]" in text
    assert "serializable_row(selected_row)" in text
    assert "cached_render_full_pick_magazine_page_png" in text
    assert "NO_MARKET_EXPORT_VERSION, ENRICHMENT_VERSION" in text
    assert "rowd = enrich_rows_with_live_api_data([rowd])[0]" in text


def test_full_book_cache_key_includes_enrichment_version() -> None:
    text = _source()
    assert "report_studio_full_book_export_cache_" in text
    assert "_{ENRICHMENT_VERSION}" in text
    assert "ACTIVE_EXPORT_VERSION = f\"{magazine_book_export.MAGAZINE_STYLE_VERSION}:{NO_MARKET_EXPORT_VERSION}:{ENRICHMENT_VERSION}\"" in text


def test_diagnostics_expose_api_enrichment_status() -> None:
    text = _source()
    required = [
        "api_enrichment_version",
        "first_row_api_enrichment_fields",
        "first_row_has_weather_summary",
        "first_row_has_newsapi_summary",
        "first_row_has_api_football_summary",
        "first_row_has_sportsdataio_context",
        "first_row_weather_summary",
        "first_row_newsapi_summary",
        "first_row_api_football_summary",
        "first_row_sportsdataio_context",
        "\"api_enrichment\": api_diagnostics",
    ]
    for token in required:
        assert token in text
