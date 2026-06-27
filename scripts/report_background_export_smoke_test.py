from __future__ import annotations

from io import BytesIO

import pandas as pd
from PIL import Image, ImageDraw, ImageStat

from autonomous_betting_agent.report_background_image_service import (
    PNG_HEADER,
    render_custom_background_card_png,
    render_custom_background_deck_png,
    render_custom_background_summary_png,
)
from autonomous_betting_agent.report_product_layer import MagazineBrand


EXPECTED_SUMMARY_SIZE = (1080, 1620)


def _background_bytes() -> bytes:
    image = Image.new("RGB", (900, 1200), (190, 92, 58))
    draw = ImageDraw.Draw(image)
    for y in range(0, 1200, 24):
        shade = int(40 * y / 1200)
        draw.rectangle((0, y, 900, y + 23), fill=(190 + shade, 92 + shade // 2, 58))
    draw.rectangle((80, 120, 820, 1080), outline=(245, 210, 170), width=18)
    draw.ellipse((260, 360, 640, 740), fill=(220, 130, 70), outline=(250, 235, 210), width=12)
    out = BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def _sample_cards() -> pd.DataFrame:
    return pd.DataFrame([
        {"event": "Team A at Team B", "sport": "Soccer", "prediction": "Total: Over 2.5", "recommended_action": "Research / Learning", "sports_context_summary": "Preview text for the first matchup."},
        {"event": "Team C at Team D", "sport": "Soccer", "prediction": "Total: Over 2", "recommended_action": "Research / Learning", "sports_context_summary": "Preview text for the second matchup."},
        {"event": "Team E at Team F", "sport": "Soccer", "prediction": "Total: Under 2.5", "recommended_action": "Research / Learning", "sports_context_summary": "Preview text for the third matchup."},
    ])


def _image(payload: bytes) -> Image.Image:
    return Image.open(BytesIO(payload)).convert("RGB")


def _mean_rgb(payload: bytes) -> tuple[float, float, float]:
    return tuple(ImageStat.Stat(_image(payload)).mean)  # type: ignore[return-value]


def _pixel_rgb(payload: bytes, xy: tuple[int, int]) -> tuple[int, int, int]:
    return _image(payload).getpixel(xy)


def _is_red_orange(pixel: tuple[int, int, int]) -> bool:
    return pixel[0] > 45 and pixel[0] > pixel[2] + 5


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Background Smoke")
    cards = _sample_cards()
    background = _background_bytes()

    summary_custom = render_custom_background_summary_png(cards, brand, background_bytes=background)
    card_custom = render_custom_background_card_png(cards.iloc[0].to_dict(), brand, background_bytes=background)
    deck_custom = render_custom_background_deck_png(cards, brand, background_bytes=background)

    for name, payload in {
        "summary_custom": summary_custom,
        "card_custom": card_custom,
        "deck_custom": deck_custom,
    }.items():
        assert payload.startswith(PNG_HEADER), f"{name} did not start with PNG header"
        assert len(payload) > 1000, f"{name} too small: {len(payload)}"

    summary = _image(summary_custom)
    assert summary.size == EXPECTED_SUMMARY_SIZE, f"unexpected summary size: {summary.size}"

    width, height = summary.size
    points = [(24, 24), (width - 24, 24), (24, height - 24), (width - 24, height - 24)]
    pixels = [_pixel_rgb(summary_custom, point) for point in points]
    custom_mean = _mean_rgb(summary_custom)
    print({
        "edge_pixels": pixels,
        "custom_mean": custom_mean,
        "summary_custom_size": len(summary_custom),
        "card_custom_size": len(card_custom),
        "deck_custom_size": len(deck_custom),
    })

    assert sum(1 for pixel in pixels if _is_red_orange(pixel)) >= 2, f"background not visibly applied at edges: {pixels}"
    assert sum(custom_mean) / 3 > 25, f"custom summary is too dark, mean={custom_mean}"


def main() -> None:
    run_smoke_test()
    print("custom background PNG export smoke test passed")


if __name__ == "__main__":
    main()
