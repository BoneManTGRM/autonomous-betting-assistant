from __future__ import annotations

import unittest
from pathlib import Path


class UiPresenceTests(unittest.TestCase):
    def test_streamlit_app_imports_pro_predictor_page(self) -> None:
        text = Path('streamlit_app.py').read_text(encoding='utf-8')
        self.assertIn('import pages.pro_predictor', text)
        self.assertIn('mobile_safe_file_uploader', text)
        self.assertIn('st.file_uploader = mobile_safe_file_uploader', text)
        self.assertNotIn('runpy.run_path', text)
        self.assertNotIn('PRO_PREDICTOR_PAGE', text)

    def test_pro_predictor_has_current_handoff_flow(self) -> None:
        text = Path('pages/pro_predictor.py').read_text(encoding='utf-8')
        self.assertIn('Highest-confidence output', text)
        self.assertIn('Send only highest-confidence rows to Odds Lock Pro', text)
        self.assertIn('Download highest-confidence CSV', text)
        self.assertIn('pro_predictor_high_confidence_rows', text)
        self.assertIn('pro_predictor_latest_rows', text)
        self.assertIn('ara_latest_predictions', text)

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
