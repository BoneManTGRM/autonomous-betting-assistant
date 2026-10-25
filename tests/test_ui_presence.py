from __future__ import annotations

import unittest
from pathlib import Path


class UiPresenceTests(unittest.TestCase):
    def test_streamlit_app_uses_current_app_shell(self) -> None:
        text = Path('streamlit_app.py').read_text(encoding='utf-8')
        self.assertIn('from app_streamlit import render_home', text)
        self.assertIn('render_home()', text)
        self.assertIn('Streamlit Cloud entrypoint', text)
        self.assertNotIn('runpy.run_path', text)
        self.assertNotIn('PRO_PREDICTOR_PAGE', text)

    def test_pro_predictor_has_current_handoff_flow(self) -> None:
        text = Path('pages/pro_predictor.py').read_text(encoding='utf-8')
        self.assertIn('Large-list volume output', text)
        self.assertIn('Send large-list volume rows to Odds Lock Pro', text)
        self.assertIn('Download large-list CSV', text)
        self.assertIn('persist_handoff', text)
        self.assertIn('pro_predictor_high_confidence_rows', text)
        self.assertIn('pro_predictor_latest_rows', text)
        self.assertIn('ara_latest_predictions', text)
        self.assertIn('market_type = getattr(outcome', text)
        self.assertIn('line_point', text)

    def test_standalone_pages_contain_fields(self) -> None:
        market = Path('market_capture_page.py').read_text(encoding='utf-8')
        context = Path('context_layer_page.py').read_text(encoding='utf-8')
        self.assertIn('Language / Idioma', market)
        self.assertIn('odds_api_key', market)
        self.assertIn('book_regions', market)
        self.assertIn('max_api_calls', market)
        self.assertIn('Language / Idioma', context)
        self.assertIn('weatherapi_key', context)
        self.assertIn('sportsdataio_key', context)
        self.assertIn('manual_weather', context)


if __name__ == '__main__':
    unittest.main()
