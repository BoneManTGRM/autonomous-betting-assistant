from __future__ import annotations

from PIL import Image

from autonomous_betting_agent import magazine_export_state_guard


class FakeMagazineModule:
    PAGE_WIDTH = 16
    PAGE_HEIGHT = 16
    PAPER = (244, 235, 211)
    _ABA_FORCED_TWO_PAGE_TRUTH_RENDERER = "truth_contract_v12"

    def __init__(self):
        self.last_rows = []

    def render_full_magazine_book_pages(self, picks, *_args, **_kwargs):
        rows = list(picks)
        self.last_rows = rows
        return [Image.new("RGB", (self.PAGE_WIDTH, self.PAGE_HEIGHT), self.PAPER) for _ in rows]

    def render_full_pick_magazine_page_png(self, *_args, **_kwargs):
        image = Image.new("RGB", (self.PAGE_WIDTH, self.PAGE_HEIGHT), self.PAPER)
        return magazine_export_state_guard._png(image)


def test_export_guard_recovers_preview_rows_instead_of_no_verified_fallback():
    module = FakeMagazineModule()
    magazine_export_state_guard.install(module)
    good_rows = [
        {
            "event": "Pittsburgh Pirates vs Washington Nationals",
            "prediction": "Run Line: Pittsburgh Pirates +1",
            "decimal_price": "1.81",
            "model_probability": "0.58",
            "model_market_edge": "0.03",
            "expected_value_per_unit": "0.054",
        }
    ]
    fallback_rows = [
        {
            "event": "NO VERIFIED PICKS",
            "prediction": "NO PICK",
            "report_truth_warning": "NO VERIFIED BUYER PICKS AVAILABLE FROM CURRENT PROVIDER DATA YET",
        }
    ]

    module.render_full_magazine_book_pages(good_rows, report_name="ABA Signal Pro", language="en")
    module.render_full_magazine_book_pdf(fallback_rows, report_name="ABA Signal Pro", language="en")

    assert module.last_rows[0]["event"] == "Pittsburgh Pirates vs Washington Nationals"
    assert module.last_rows[0].get("export_source_recovered_from_preview_state") == "true"
