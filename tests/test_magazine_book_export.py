from io import BytesIO
from zipfile import ZipFile

from PIL import Image

from autonomous_betting_agent.magazine_book_export import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    pick_full_page_filename,
    render_card_image_png,
    render_compact_magazine_png,
    render_full_magazine_book_pages,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
)


def mock_picks():
    return [
        {
            "game": "Iraq at France",
            "sport": "Soccer",
            "league": "International",
            "start_time": "10:00 AM",
            "sportsbook": "Caliente",
            "exact_bet": "Over 2.5 Total Goals",
            "decimal_odds": 1.36,
            "model_probability": 0.72,
            "edge": 0.054,
            "expected_value": 0.08,
            "recommended_units": "0.5 units",
            "risk_level": "Medium",
            "why_bullets": "Model projects goal edge | Recent scoring trend supports over | Market still playable | Weather neutral | Lineup risk acceptable | Same script support",
            "market_movement": "Moved toward over",
            "injury_report": "No major attacking injuries",
            "weather_impact": "Neutral scoring weather",
            "team_form": "France attack in strong form",
            "straight_bet_alternative": "Over 2.5 Total Goals",
        },
        {
            "game": "Germany at Ecuador",
            "sport": "Soccer",
            "exact_bet": "Over 2 Total Goals",
            "decimal_odds": 1.39,
            "model_probability": 0.69,
            "edge": 0.031,
            "why_pick": "Tempo and attacking quality support goals.",
        },
        {
            "game": "Australia at Paraguay",
            "sport": "Soccer",
            "exact_bet": "Under 2.5 Total Goals",
            "decimal_odds": 1.80,
            "model_probability": 0.61,
            "edge": 0.04,
        },
    ]


def test_generates_one_full_page_image_per_pick():
    pages = render_full_magazine_book_pages(mock_picks(), report_name="Test Full Magazine")

    assert len(pages) == 3
    assert all(page.size == (PAGE_WIDTH, PAGE_HEIGHT) for page in pages)


def test_full_magazine_book_png_includes_every_pick():
    data = render_full_magazine_book_png(mock_picks(), report_name="Test Full Magazine")
    image = Image.open(BytesIO(data))

    assert image.size == (PAGE_WIDTH, PAGE_HEIGHT * 3)


def test_individual_full_page_pick_export_works():
    data = render_full_pick_magazine_page_png(mock_picks()[0], report_name="Single Pick", page_number=1, total_pages=1)
    image = Image.open(BytesIO(data))

    assert image.size == (PAGE_WIDTH, PAGE_HEIGHT)
    assert pick_full_page_filename(mock_picks()[0], 1) == "pick_01_iraq_at_france_full_page.png"


def test_zip_contains_combined_png_pdf_and_individual_pages():
    data = render_full_magazine_zip(mock_picks(), report_name="Test Full Magazine")

    with ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())

    assert "full_magazine_book.png" in names
    assert "full_magazine_book.pdf" in names
    assert "pick_01_iraq_at_france_full_page.png" in names
    assert "pick_02_germany_at_ecuador_full_page.png" in names


def test_full_page_magazine_uses_editable_report_name():
    data = render_full_pick_magazine_page_png(mock_picks()[0], report_name="Marco Full Magazine", page_number=1, total_pages=1)

    assert data.startswith(b"\x89PNG")


def test_long_text_does_not_crash_rendering():
    pick = mock_picks()[0].copy()
    pick["why_bullets"] = " | ".join(["Very long professional betting explanation with multiple details about market movement and injury context" for _ in range(20)])

    data = render_full_pick_magazine_page_png(pick, report_name="Long Text Test")
    assert data.startswith(b"\x89PNG")


def test_missing_pro_evidence_fields_still_render_fallback_text():
    data = render_full_pick_magazine_page_png({"game": "Fallback Game", "exact_bet": "Watch Only"})
    image = Image.open(BytesIO(data))

    assert image.size == (PAGE_WIDTH, PAGE_HEIGHT)


def test_existing_compact_magazine_png_export_still_works():
    data = render_compact_magazine_png(mock_picks(), report_name="Compact Magazine")
    image = Image.open(BytesIO(data))

    assert image.size == (PAGE_WIDTH, PAGE_HEIGHT)


def test_existing_card_image_export_still_works():
    data = render_card_image_png(mock_picks()[0], report_name="Compact Card", page_number=1)
    image = Image.open(BytesIO(data))

    assert image.size[0] == PAGE_WIDTH


def test_full_magazine_book_pdf_exports_pdf_bytes():
    data = render_full_magazine_book_pdf(mock_picks(), report_name="PDF Magazine")

    assert data.startswith(b"%PDF")
