from __future__ import annotations

from typing import Any
import re


def install() -> None:
    """Apply small runtime patches to the magazine renderer.

    This keeps the public renderer API stable while fixing production layout issues:
    1. Spanish sport labels like Boxing should render as Latin American Spanish.
    2. Long risk labels should fit inside the top metrics strip.
    """
    from . import magazine_book_export as m

    if getattr(m, "_aba_magazine_metric_patch_v2", False):
        return

    original_tr = m._tr
    original_render = m.render_full_pick_magazine_page

    sport_es = {
        "BOXING": "BOXEO",
        "BASEBALL": "BÉISBOL",
        "SOCCER": "FÚTBOL",
        "FOOTBALL": "FÚTBOL AMERICANO",
        "BASKETBALL": "BALONCESTO",
        "TENNIS": "TENIS",
        "MMA": "MMA",
        "MLB": "MLB",
        "NCAA BASEBALL": "BÉISBOL NCAA",
    }

    # Full text is too long for the magazine metric strip. These are public-facing
    # compact labels, not grading logic.
    risk_display_es = {
        "THIN EDGE FAVORITE": "VENTAJA DELGADA",
        "THIN EDGE FAVOURITE": "VENTAJA DELGADA",
        "FAVORITO DE VENTAJA DELGADA": "VENTAJA DELGADA",
        "VOLUME OK": "VOLUMEN OK",
        "VOLUME_OK": "VOLUMEN OK",
    }
    risk_display_en = {
        "THIN EDGE FAVORITE": "THIN EDGE",
        "THIN EDGE FAVOURITE": "THIN EDGE",
        "VOLUME OK": "VOLUME OK",
        "VOLUME_OK": "VOLUME OK",
    }

    def _compact_risk(value: Any, lang: str) -> str:
        raw = str(value or "").strip().upper().replace("_", " ")
        mapping = risk_display_es if lang == "es" else risk_display_en
        return mapping.get(raw, raw)

    def patched_tr(v: Any, lang: str) -> str:
        text = original_tr(v, lang)
        if m._bad(text):
            return text
        raw = str(text)
        if lang == "es":
            for src, dst in sport_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
            for src, dst in risk_display_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        return raw

    def _metric_fit(d, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int], lang: str) -> None:
        label = patched_tr(label, lang)
        value = str(value or "").upper()
        d.rectangle((x, y, x + w, y + 94), fill=m.BLACK, outline=(230, 224, 204), width=1)
        d.text((x + 7, y + 10), label, font=m._fit(label, w - 12, 16, 9, True), fill=(232, 230, 220))
        # Let long values wrap to two compact lines instead of clipping into the next cell.
        m._txt_auto(d, x + 7, y + 43, value, w - 14, 42, 20, 7, color, True, 2)

    def repaint_risk_market(img, pick: Any, lang: str, sy: int = 456) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        risk_raw = m._clean(
            m._get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=m.NO_VERIFIED),
            True,
        )
        risk = _compact_risk(patched_tr(risk_raw, lang), lang)
        market = patched_tr(
            m._clean(m._get(pick, "market_type", "market", "bet_type", default=m.NO_VERIFIED), True),
            lang,
        )
        # Repaint the far-right metric cells on top of the original strip. Risk gets
        # more space and may wrap; market stays compact and readable.
        _metric_fit(d, 830, sy + 6, 148, "RISK", risk, m.GREEN, lang)
        m._metric(d, 978, sy + 6, 82, "MARKET", market, m.CREAM, lang)

    def patched_render_full_pick_magazine_page(
        pick: Any,
        background_image: Any = None,
        report_name: str | None = None,
        page_number: int = 1,
        total_pages: int = 1,
        logo_image: Any = None,
        background_mode: str = "hero_right",
        logo_mode: str = "header",
        background_opacity: float = 0.9,
        logo_opacity: float = 1.0,
        use_team_logo: bool = True,
        language: str | None = None,
    ):
        img = original_render(
            pick,
            background_image,
            report_name,
            page_number,
            total_pages,
            logo_image,
            background_mode,
            logo_mode,
            background_opacity,
            logo_opacity,
            use_team_logo,
            language,
        )
        repaint_risk_market(img, pick, m._lang(pick, language))
        return img

    m._tr = patched_tr
    m.render_full_pick_magazine_page = patched_render_full_pick_magazine_page
    m._aba_magazine_metric_patch_v1 = True
    m._aba_magazine_metric_patch_v2 = True
