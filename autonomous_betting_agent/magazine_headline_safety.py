from __future__ import annotations

from typing import Any

HEADLINE_AREA = (20, 90, 610, 455)
AWAY_BOX = (36, 98, 596, 205)
VS_BOX = (36, 212, 102, 284)
HOME_BOX = (116, 210, 596, 315)
SEASON_BOX = (36, 330, 506, 378)
CONTEXT_BOX = (42, 394, 600, 450)
HERO_BOX = (620, 105, 1050, 455)


def _w(rect: tuple[int, int, int, int]) -> int:
    return rect[2] - rect[0]


def _h(rect: tuple[int, int, int, int]) -> int:
    return rect[3] - rect[1]


def _hit(a: tuple[int, int, int, int], b: tuple[int, int, int, int], pad: int = 0) -> bool:
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _wrap(draw: Any, text: str, font: Any, width: int, max_lines: int) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= width:
            current = trial
            continue
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                return lines
            current = ""
        token = ""
        for ch in word:
            trial_token = token + ch
            if draw.textbbox((0, 0), trial_token, font=font)[2] <= width or not token:
                token = trial_token
            else:
                lines.append(token)
                if len(lines) >= max_lines:
                    return lines
                token = ch
        current = token
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [""]


def _trim(draw: Any, text: str, font: Any, width: int) -> str:
    text = str(text or "")
    if draw.textbbox((0, 0), text, font=font)[2] <= width:
        return text
    ell = "…"
    while text and draw.textbbox((0, 0), text + ell, font=font)[2] > width:
        text = text[:-1]
    return text + ell if text else ell


def _draw_name(module: Any, draw: Any, text: str, rect: tuple[int, int, int, int], color: Any, max_size: int) -> list[tuple[int, int, int, int]]:
    label = " ".join(str(text or "").upper().split())
    for size in range(max_size, 5, -1):
        font = module._font(size, True)
        lines = _wrap(draw, label, font, _w(rect), 2)
        line_h = size + 3
        if len(lines) * line_h <= _h(rect):
            y = rect[1] + max(0, (_h(rect) - len(lines) * line_h) // 2)
            boxes: list[tuple[int, int, int, int]] = []
            for line in lines:
                line = _trim(draw, line, font, _w(rect))
                tw = draw.textbbox((0, 0), line, font=font)[2]
                draw.text((rect[0], y), line, font=font, fill=color)
                boxes.append((rect[0], y, rect[0] + tw, y + line_h))
                y += line_h
            return boxes
    font = module._font(6, True)
    line = _trim(draw, label, font, _w(rect))
    tw = draw.textbbox((0, 0), line, font=font)[2]
    draw.text((rect[0], rect[1]), line, font=font, fill=color)
    return [(rect[0], rect[1], rect[0] + tw, rect[1] + 9)]


def _draw_small(module: Any, draw: Any, text: str, rect: tuple[int, int, int, int], color: Any, max_size: int, bold: bool = False, max_lines: int = 2) -> None:
    label = " ".join(str(text or "").split())
    for size in range(max_size, 5, -1):
        font = module._font(size, bold)
        lines = _wrap(draw, label, font, _w(rect), max_lines)
        line_h = size + 3
        if len(lines) * line_h <= _h(rect):
            y = rect[1]
            for line in lines:
                draw.text((rect[0], y), _trim(draw, line, font, _w(rect)), font=font, fill=color)
                y += line_h
            return


def _repaint(module: Any, img: Any, row_like: Any, language: str) -> list[str]:
    row = module._row(row_like)
    away, home = module._teams(row)
    draw = module.ImageDraw.Draw(img, "RGBA")
    draw.rectangle(HEADLINE_AREA, fill=module.PAPER)
    away_boxes = _draw_name(module, draw, module._team_label(away, language), AWAY_BOX, module.RED, 56)
    draw.rounded_rectangle(VS_BOX, radius=7, fill=module.CREAM, outline=module.BLACK, width=2)
    _draw_name(module, draw, "V", (VS_BOX[0] + 14, VS_BOX[1] + 10, VS_BOX[2] - 14, VS_BOX[3] - 10), module.BLACK, 34)
    home_boxes = _draw_name(module, draw, module._team_label(home, language), HOME_BOX, module.BLUE, 48)
    sport = module._get(row, "sport", "league", default="Sport N/A")
    season = module._tr(module._get(row, "season_label", "event_stage", "competition_round", default=f"{sport} REGULAR SEASON"), language).upper()
    draw.rectangle(SEASON_BOX, fill=module.BLACK)
    _draw_small(module, draw, season, (54, 339, 492, 372), module.CREAM, 25, True, 1)
    ctx = []
    for key in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
        ctx += [p.strip(" -•") for p in str(row.get(key, "")).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]
    _draw_small(module, draw, module._tr((ctx or ["Context unavailable."])[0], language), CONTEXT_BOX, module.TEXT, 18, False, 2)
    warnings: list[str] = []
    for box in away_boxes + home_boxes:
        if _hit(box, HERO_BOX, 8):
            warnings.append("headline:hero_overlap")
    for a in away_boxes:
        for h in home_boxes:
            if _hit(a, h, 8):
                warnings.append("headline:away_home_overlap")
    return sorted(set(warnings))


def install(module: Any) -> Any:
    if getattr(module, "_ABA_HEADLINE_SAFETY_V1", False):
        return module
    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    previous_validate = getattr(module, "validate_magazine_layout_no_overflow", None)

    def render(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None):
        img = original_render(row_like, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        lang = module._lang(row_like, language)
        _repaint(module, img, row_like, lang)
        return img

    def render_png(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(row_like, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    def validate(row_like: Any, language: str = "en") -> list[str]:
        warnings: list[str] = []
        if callable(previous_validate):
            warnings.extend(w for w in previous_validate(row_like, language=language) if not str(w).startswith("headline:"))
        img = module.Image.new("RGBA", (module.PAGE_WIDTH, module.PAGE_HEIGHT), module.PAPER + (255,))
        warnings.extend(_repaint(module, img, row_like, module._lang(row_like, language)))
        return sorted(set(warnings))

    module.render_full_pick_magazine_page = render
    module.render_full_pick_magazine_page_png = render_png
    module.validate_magazine_layout_no_overflow = validate
    module.validate_headline_layout = validate
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_headline_safety_v1"
    module._ABA_HEADLINE_SAFETY_V1 = True
    return module
