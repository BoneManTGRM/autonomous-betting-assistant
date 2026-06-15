from __future__ import annotations

import unittest
from pathlib import Path


class UiPresenceTests(unittest.TestCase):
    def test_streamlit_app_launches_full_pro_predictor_page(self) -> None:
        text = Path("streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("pages", text)
        self.assertIn("pro_predictor.py", text)
        self.assertIn("runpy.run_path", text)
        self.assertIn("PRO_PREDICTOR_PAGE", text)

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
