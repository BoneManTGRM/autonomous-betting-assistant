from __future__ import annotations

import importlib.util
from pathlib import Path

PNG_HEADER = b"\x89PNG\r\n\x1a\n"

MODULE_PATH = Path(__file__).resolve().parents[1] / "autonomous_betting_agent" / "magazine_book_export.py"
SPEC = importlib.util.spec_from_file_location("magazine_book_export_base", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
magazine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(magazine)


HEADLINE_CASES = [
    ("BRAZIL", "FRANCE"),
    ("QATAR", "IRAQ"),
    ("IVORY COAST", "CURAÇAO"),
    ("UZBEKISTAN", "PORTUGAL"),
    ("BALTIMORE ORIOLES", "LOS ANGELES ANGELS"),
    ("LOS ANGELES DODGERS", "MINNESOTA TWINS"),
    ("BOSNIA AND HERZEGOVINA", "CZECH REPUBLIC"),
    ("UNITED ARAB EMIRATES", "PAPUA NEW GUINEA"),
    ("SPORTING KANSAS CITY", "NEW ENGLAND REVOLUTION"),
    ("CLUB DEPORTIVO GUADALAJARA", "UNIVERSIDAD NACIONAL"),
    ("THE VERY LONG INTERNATIONAL FOOTBALL CLUB NAME", "ANOTHER EXTREMELY LONG CLUB NAME"),
]


def _row(away: str, home: str) -> dict[str, str]:
    return {
        "event_name": f"{away} vs {home}",
        "away_team": away,
        "home_team": home,
        "sport": "FIFA WORLD CUP",
        "market_type": "GAME TOTAL",
        "pick": "OVER 2.5",
        "decimal_price": "1.91",
        "risk": "VOLUME OK",
    }


def test_headline_autosizer_fits_required_cases() -> None:
    for away, home in HEADLINE_CASES:
        row = _row(away, home)
        assert magazine.validate_headline_layout(row) == []
        assert magazine.validate_magazine_layout_no_overflow(row) == []


def test_headline_autosizer_png_smoke() -> None:
    png = magazine.render_full_pick_magazine_page_png(_row("IVORY COAST", "CURAÇAO"), use_team_logo=False)
    assert png.startswith(PNG_HEADER)
    assert len(png) > 10000


def test_headline_autosizer_fuzz_cases() -> None:
    names = [
        "BRAZIL",
        "FRANCE",
        "QATAR",
        "BOSNIA & HERZEGOVINA",
        "LOS ANGELES ANGELS",
        "NEW ENGLAND REVOLUTION",
        "CLUB DEPORTIVO GUADALAJARA",
        "A_SINGLE_SUPERLONGUNBROKENFOOTBALLCLUBNAME",
    ]
    for away in names:
        for home in names:
            assert magazine.validate_headline_layout(_row(away, home)) == []
