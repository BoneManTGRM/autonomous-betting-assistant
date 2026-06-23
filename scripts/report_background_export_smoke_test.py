from __future__ import annotations

from io import BytesIO

import pandas as pd
from PIL import Image, ImageStat

from autonomous_betting_agent.report_background_image_service import (
    PNG_HEADER,
    render_custom_background_card_png,
    render_custom_background_deck_png,
    render_custom_background_summary_png,
)
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat
from autonomous_betting_agent.report_product_layer import MagazineBrand, enrich_rows


def _background_bytes() -> bytes:
    image = Image.new("RGB", (900, 1200), (190, 92, 58))
    out = BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def _sample_cards() -> pd.DataFrame:
    rows = pd.DataFrame([
        {"event": "Iraq at France", "sport": "FIFA World Cup", "prediction": "Game total: Over 2.5", "learned_model_probability": 0.62, "decimal_price": 1.95, "odds_source": "The Odds API"},
        {"event": "Germany at Ecuador", "sport": "FIFA World Cup", "prediction": "Game total: Over 2", "learned_model_probability": 0.64, "decimal_price": 1.90, "odds_source": "The Odds API"},
        {"event": "Australia at Paraguay", "sport": "FIFA World Cup", "prediction": "Game total: Under 2.5", "learned_model_probability": 0.60, "decimal_price": 1.85, "odds_source": "The Odds API"},
    ])
    return apply_learning_layer_compat(enrich_rows(rows))


def _image(payload: bytes) -> Image.Image:
    return Image.open(BytesIO(payload)).convert("RGB")


def _mean_rgb(payload: bytes) -> tuple[float, float, float]:
    return tuple(ImageStat.Stat(_image(payload)).mean)  # type: ignore[return-value]


def _corner_rgb(payload: bytes) -> tuple[int, int, int]:
    return _image(payload).getpixel((24, 24))


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Background Smoke")
    cards = _sample_cards()
    background = _background_bytes()

    summary_default = render_custom_background_summary_png(cards, brand, background_bytes=None)
    summary_custom = render_custom_background_summary_png(cards, brand, background_bytes=background)
    card_custom = render_custom_background_card_png(cards.iloc[0].to_dict(), brand, background_bytes=background)
    deck_custom = render_custom_background_deck_png(cards, brand, background_bytes=background)

    for name, payload in {
        "summary_custom": summary_custom,
        "card_custom": card_custom,
        "deck_custom": deck_custom,
    }.items():
        assert payload.startswith(PNG_HEADER), f"{name} did not start with PNG header"
        assert len(payload) > 20000, f"{name} too small: {len(payload)}"

    # A red/orange background should stay visibly red/orange at the page edge.
    # This catches regressions where the uploaded background is not used and the image goes black.
    corner = _corner_rgb(summary_custom)
    assert corner[0] > 85 and corner[0] > corner[2] + 25, f"background not visibly applied, corner={corner}"

    mean = _mean_rgb(summary_custom)
    assert sum(mean) / 3 > 45, f"custom summary is too dark, mean={mean}"
    assert abs(len(summary_custom) - len(summary_default)) > 500, "custom background render is suspiciously similar to default render"


def main() -> None:
    run_smoke_test()
    print("custom background PNG export smoke test passed")


if __name__ == "__main__":
    main()
