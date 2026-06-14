from __future__ import annotations

import unittest
from pathlib import Path


class UiPresenceTests(unittest.TestCase):
    def test_streamlit_app_contains_bilingual_page_selector_and_api_fields(self) -> None:
        text = Path("streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("Language / Idioma", text)
        self.assertIn("Pro Predictor", text)
        self.assertIn("market_snapshot_title", text)
        self.assertIn("odds_weather_title", text)
        self.assertIn("odds_api_key", text)
        self.assertIn("sportsdataio_key", text)
        self.assertIn("weatherapi_key", text)
        self.assertIn("render_market_capture", text)
        self.assertIn("render_context_layer", text)

    def test_standalone_pages_contain_fields(self) -> None:
        market = Path("market_capture_page.py").read_text(encoding="utf-8")
        context = Path("context_layer_page.py").read_text(encoding="utf-8")
        self.assertIn("Language / Idioma", market)
        self.assertIn("odds_api_key", market)
        self.assertIn("book_regions", market)
        self.assertIn("max_api_calls", market)
        self.assertIn("Language / Idioma", context)
        self.assertIn("weatherapi_key", context)
        self.assertIn("sportsdataio_key", context)
        self.assertIn("manual_weather", context)


if __name__ == "__main__":
    unittest.main()
