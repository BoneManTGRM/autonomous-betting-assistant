from __future__ import annotations

from typing import Any


def _headline_cap(text: str, width: int, start: int, minimum: int, bold: bool) -> tuple[int, int]:
    """Cap giant one-line matchup names before width fitting.

    Width-only fitting lets short names like BRAZIL render huge and lets medium
    names dominate the hero area. The headline calls are identifiable by their
    wide boxes and high start/minimum sizes, so cap those calls first and then
    still shrink until the text fits the available width.
    """
    if not bold:
        return int(start), int(minimum)
    clean = " ".join(str(text or "").replace("\n", " ").split())
    length = len(clean)
    start = int(start)
    minimum = int(minimum)

    # Away headline: base renderer calls _fit(name, 590, 140, 72, True).
    if width >= 585 and start >= 120:
        if length <= 6:
            return min(start, 82), min(minimum, 36)
        if length <= 12:
            return min(start, 72), min(minimum, 32)
        if length <= 18:
            return min(start, 58), min(minimum, 26)
        return min(start, 44), min(minimum, 20)

    # Home headline: base renderer calls _fit(name, 560, 112, 62, True).
    if 540 <= width < 585 and start >= 95:
        if length <= 7:
            return min(start, 74), min(minimum, 34)
        if length <= 13:
            return min(start, 60), min(minimum, 28)
        if length <= 18:
            return min(start, 46), min(minimum, 22)
        return min(start, 34), min(minimum, 16)

    return start, minimum


def apply_magazine_auto_sizer(module: Any) -> Any:
    """Restore strict text fitting for magazine labels.

    The base renderer sometimes passes a high minimum font size for team names.
    This helper caps headline size, then continues shrinking to a safe hard floor
    when the requested minimum is still too wide for the available box.
    """
    if getattr(module, "_STRICT_MAGAZINE_AUTO_SIZER_PATCHED_V2", False):
        return module

    original_font = module._font
    original_image = module.Image
    original_draw_factory = module.ImageDraw.Draw

    def strict_fit(text: str, width: int, start: int, minimum: int = 12, bold: bool = True):
        start, minimum = _headline_cap(text, int(width), int(start), int(minimum), bool(bold))
        draw = original_draw_factory(original_image.new("RGB", (10, 10)))
        floor = min(int(minimum), 6)
        for size in range(int(start), floor - 1, -1):
            font = original_font(size, bold)
            if draw.textbbox((0, 0), str(text), font=font)[2] <= int(width):
                return font
        return original_font(floor, bold)

    module._fit = strict_fit
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_strict_autosize_v2"
    module._STRICT_MAGAZINE_AUTO_SIZER_PATCHED = True
    module._STRICT_MAGAZINE_AUTO_SIZER_PATCHED_V2 = True
    return module
