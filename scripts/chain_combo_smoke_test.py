from __future__ import annotations

from autonomous_betting_agent import chain_notes
from autonomous_betting_agent.magazine_book_export import render_full_pick_magazine_page_png, validate_magazine_layout_no_overflow
from autonomous_betting_agent.report_image_export_service import PNG_HEADER


def check_logic() -> None:
    assert chain_notes.classify({'risk': 'RESEARCH ONLY'}, 'en') == 'Research only'
    assert chain_notes.classify({'model_market_edge': '-0.02'}, 'en') == 'Do not combine'
    assert chain_notes.classify({'risk': 'THIN EDGE FAVORITE'}, 'en') == 'Straight only'
    assert chain_notes.classify({'model_probability': '0.62', 'model_market_edge': '0.04', 'expected_value': '0.06', 'risk': 'LOW', 'odds_source': 'verified'}, 'en') == 'Possible anchor leg'
    assert chain_notes.classify({'model_probability': '0.57', 'model_market_edge': '0.015', 'expected_value': '0.02', 'risk': 'MEDIUM', 'odds_source': 'verified'}, 'en') in {'Small combo only', 'Straight preferred'}
    spanish = ' '.join(chain_notes.notes({'risk': 'RESEARCH ONLY'}, 'es')).lower()
    for token in ('directa', 'combinada', 'momio', 'selección', 'verificación'):
        assert token in spanish
    warning = chain_notes.detect_correlation_warning({'event_name': 'A vs B'}, [{'event_name': 'A vs B'}], 'en')
    assert 'same-game' in warning.lower()


def check_images() -> None:
    rows = [
        {'event_name': 'Research A vs B', 'away_team': 'Research A', 'home_team': 'Research B', 'sport': 'MMA', 'risk': 'RESEARCH ONLY', 'market_type': 'MONEYLINE', 'pick': 'Research A ML'},
        {'event_name': 'Negative A vs B', 'away_team': 'Negative A', 'home_team': 'Negative B', 'sport': 'MLB', 'model_market_edge': '-0.02', 'market_type': 'TOTALS', 'pick': 'UNDER 8.5'},
        {'event_name': 'Thin A vs B', 'away_team': 'Thin A', 'home_team': 'Thin B', 'sport': 'FIFA WORLD CUP', 'risk': 'THIN EDGE FAVORITE', 'market_type': 'GAME TOTAL', 'pick': 'OVER 2.5'},
        {'event_name': 'Anchor A vs B', 'away_team': 'Anchor A', 'home_team': 'Anchor B', 'sport': 'MLB', 'risk': 'LOW', 'model_probability': '0.62', 'model_market_edge': '0.04', 'expected_value': '0.06', 'odds_source': 'verified', 'market_type': 'MONEYLINE', 'pick': 'Anchor B ML'},
    ]
    for row in rows:
        assert validate_magazine_layout_no_overflow(row, language='en') == []
        assert validate_magazine_layout_no_overflow(row, language='es') == []
        png = render_full_pick_magazine_page_png(row, language='en', use_team_logo=False)
        assert png.startswith(PNG_HEADER)
        assert len(png) > 10000


def main() -> None:
    check_logic()
    check_images()
    print('chain combo smoke test passed')


if __name__ == '__main__':
    main()
