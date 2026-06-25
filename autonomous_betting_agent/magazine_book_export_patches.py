from __future__ import annotations

from typing import Any, Iterable
import re


def install() -> None:
    """Deterministic magazine renderer patch.

    Keeps the public magazine API stable while improving global text fitting,
    Mexico-friendly Spanish labels, and visible row-context usage in the
    Team Snapshots panel.
    """
    from . import magazine_book_export as m

    if getattr(m, "_aba_magazine_metric_patch_v4", False):
        return

    original_tr = m._tr
    original_render = m.render_full_pick_magazine_page
    original_wrap = m._wrap

    country_es = {
        "qatar": "Qatar",
        "bosnia & herzegovina": "Bosnia y Herzegovina",
        "bosnia and herzegovina": "Bosnia y Herzegovina",
        "bosnia-herzegovina": "Bosnia y Herzegovina",
        "bosnia": "Bosnia y Herzegovina",
        "netherlands": "Países Bajos",
        "ivory coast": "Costa de Marfil",
        "iraq": "Irak",
        "france": "Francia",
        "germany": "Alemania",
        "tunisia": "Túnez",
    }
    sport_es = {
        "BOXING": "BOXEO",
        "BASEBALL": "BÉISBOL",
        "SOCCER": "FÚTBOL",
        "FOOTBALL": "FÚTBOL AMERICANO",
        "BASKETBALL": "BALONCESTO",
        "TENNIS": "TENIS",
        "FIFA WORLD CUP": "COPA MUNDIAL FIFA",
        "MMA": "MMA",
        "MLB": "MLB",
        "NCAA BASEBALL": "BÉISBOL NCAA",
    }
    risk_display_es = {
        "THIN EDGE FAVORITE": "VENTAJA DELGADA",
        "THIN EDGE FAVOURITE": "VENTAJA DELGADA",
        "FAVORITO DE VENTAJA DELGADA": "VENTAJA DELGADA",
        "RESEARCH ONLY": "INVESTIGACIÓN",
        "WATCHLIST ONLY": "SEGUIMIENTO",
        "VOLUME OK": "VOLUMEN OK",
        "VOLUME_OK": "VOLUMEN OK",
    }
    risk_display_en = {
        "THIN EDGE FAVORITE": "THIN EDGE",
        "THIN EDGE FAVOURITE": "THIN EDGE",
        "RESEARCH ONLY": "RESEARCH",
        "WATCHLIST ONLY": "WATCHLIST",
        "VOLUME OK": "VOLUME OK",
        "VOLUME_OK": "VOLUME OK",
    }

    def patched_team_label(team: str, lang: str) -> str:
        text = str(team or "").strip()
        return country_es.get(text.lower(), text) if lang == "es" else text

    def patched_tr(v: Any, lang: str) -> str:
        text = original_tr(v, lang)
        if m._bad(text):
            return text
        raw = str(text)
        if lang == "es":
            raw = re.sub(r"\bCUOTA\b", "MOMIO", raw, flags=re.I)
            raw = re.sub(r"\bcuota\b", "momio", raw, flags=re.I)
            raw = re.sub(r"\bcuotas\b", "momios", raw, flags=re.I)
            raw = re.sub(r"\bPrice Watch / Research\b", "Seguimiento de momio / investigación", raw, flags=re.I)
            raw = re.sub(r"\bPrice Watch\b", "Seguimiento de momio", raw, flags=re.I)
            raw = re.sub(r"\bNegative at listed odds\b", "Negativo con el momio actual", raw, flags=re.I)
            for src, dst in sport_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
            for src, dst in risk_display_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
            for src, dst in country_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        return raw

    def safe_wrap(d, text: str, f, width: int, max_lines: int | None = None) -> list[str]:
        out: list[str] = []
        cur = ""
        for word in str(text or "").replace("\n", " ").split():
            trial = word if not cur else f"{cur} {word}"
            if d.textbbox((0, 0), trial, font=f)[2] <= width:
                cur = trial
                continue
            if cur:
                out.append(cur)
                if max_lines is not None and len(out) >= max_lines:
                    return out
                cur = ""
            token = ""
            for ch in word:
                trial_token = token + ch
                if d.textbbox((0, 0), trial_token, font=f)[2] <= width or not token:
                    token = trial_token
                else:
                    out.append(token)
                    if max_lines is not None and len(out) >= max_lines:
                        return out
                    token = ch
            cur = token
        if cur and (max_lines is None or len(out) < max_lines):
            out.append(cur)
        return out or original_wrap(d, text, f, width, max_lines)

    def safe_fit(text: str, width: int, start: int, minimum: int = 16, bold: bool = True):
        d = m.ImageDraw.Draw(m.Image.new("RGB", (10, 10)))
        floor = max(4, min(8, int(minimum)))
        for size in range(int(start), floor - 1, -1):
            f = m._font(size, bold)
            if d.textbbox((0, 0), str(text), font=f)[2] <= width:
                return f
        return m._font(floor, bold)

    def safe_txt_auto(d, x: int, y: int, text: str, width: int, height: int, start: int, minimum: int, fill: Any, bold: bool = False, max_lines: int | None = None) -> int:
        floor = max(4, min(8, int(minimum)))
        text = str(text or "")
        if max_lines == 1:
            f = safe_fit(text, width, start, floor, bold)
            d.text((x, y), text, font=f, fill=fill)
            return y + m._line_height(f)
        for size in range(int(start), floor - 1, -1):
            f = m._font(size, bold)
            lines = safe_wrap(d, text, f, width, max_lines)
            if lines and len(lines) * m._line_height(f) <= height:
                for line in lines:
                    d.text((x, y), line, font=f, fill=fill)
                    y += m._line_height(f)
                return y
        f = m._font(floor, bold)
        bottom = y + height
        for line in safe_wrap(d, text, f, width, max_lines):
            if y + m._line_height(f) > bottom:
                break
            d.text((x, y), line, font=f, fill=fill)
            y += m._line_height(f)
        return y

    def safe_bullets_auto(d, x: int, y: int, items: list[str], width: int, height: int, color: tuple[int, int, int], start: int = 18, minimum: int = 11, limit: int | None = None, lang: str = "en") -> None:
        data = [patched_tr(item, lang) for item in (items[:limit] if limit is not None else items)]
        floor = max(5, min(8, int(minimum)))
        chosen = None
        chosen_lines: list[list[str]] = []
        for size in range(int(start), floor - 1, -1):
            f = m._font(size)
            blocks = [safe_wrap(d, item, f, width - 30, None) for item in data]
            need = sum(max(1, len(block)) * m._line_height(f) + 6 for block in blocks)
            if need <= height:
                chosen = f
                chosen_lines = blocks
                break
        if chosen is None:
            chosen = m._font(floor)
            chosen_lines = [safe_wrap(d, item, chosen, width - 30, None) for item in data]
        bottom = y + height
        for block in chosen_lines:
            if y + m._line_height(chosen) > bottom:
                break
            d.ellipse((x, y + 7, x + 12, y + 19), fill=color)
            for line in block:
                if y + m._line_height(chosen) > bottom:
                    break
                d.text((x + 25, y), line, font=chosen, fill=m.TEXT)
                y += m._line_height(chosen)
            y += 6

    def safe_headline_font(text: str, width: int, preferred: int, minimum: int):
        text = str(text or "").upper()
        clean_len = len(text)
        if clean_len <= 5:
            start = preferred
        elif clean_len <= 8:
            start = min(preferred, 106)
        elif clean_len <= 10:
            start = min(preferred, 88)
        elif clean_len <= 14:
            start = min(preferred, 70)
        elif clean_len <= 18:
            start = min(preferred, 56)
        elif clean_len <= 24:
            start = min(preferred, 44)
        else:
            start = min(preferred, 34)
        return safe_fit(text, width, start, 5, True)

    def compact_risk(value: Any, lang: str) -> str:
        raw = str(value or "").strip().upper().replace("_", " ")
        mapping = risk_display_es if lang == "es" else risk_display_en
        return mapping.get(raw, raw)

    def metric_fit(d, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int], lang: str) -> None:
        label = patched_tr(label, lang)
        value = str(value or "").upper()
        d.rectangle((x, y, x + w, y + 94), fill=m.BLACK, outline=(230, 224, 204), width=1)
        d.text((x + 7, y + 10), label, font=safe_fit(label, w - 12, 16, 7, True), fill=(232, 230, 220))
        safe_txt_auto(d, x + 7, y + 43, value, w - 14, 42, 18, 5, color, True, 2)

    def split_value(value: Any) -> list[str]:
        if m._bad(value):
            return []
        return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]

    def first(row: dict[str, Any], keys: Iterable[str]) -> str:
        for key in keys:
            value = row.get(key)
            if not m._bad(value):
                return str(value).strip()
        return ""

    def team_items(row: dict[str, Any], prefix: str, lang: str) -> list[str]:
        labels = {
            "record": "Récord" if lang == "es" else "Record",
            "last_10": "Últimos 10" if lang == "es" else "Last 10",
            "form": "Forma" if lang == "es" else "Form",
            "rank": "Ranking" if lang == "es" else "Rank",
            "goals": "Goles por partido" if lang == "es" else "Goals per game",
            "runs": "Carreras por partido" if lang == "es" else "Runs per game",
            "injuries": "Lesiones" if lang == "es" else "Injuries",
        }
        specs = [
            (labels["record"], (f"{prefix}_record", f"{prefix}_season_record", f"{prefix}_team_record")),
            (labels["last_10"], (f"{prefix}_last_10", f"{prefix}_recent_record", f"{prefix}_recent_form")),
            (labels["form"], (f"{prefix}_form", f"{prefix}_team_form", f"{prefix}_form_note", f"{prefix}_trend")),
            (labels["rank"], (f"{prefix}_rank", f"{prefix}_standing", f"{prefix}_table_position")),
            (labels["goals"], (f"{prefix}_goals_per_game", f"{prefix}_avg_goals", f"{prefix}_xg")),
            (labels["runs"], (f"{prefix}_runs_per_game", f"{prefix}_rpg")),
            (labels["injuries"], (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status")),
        ]
        out: list[str] = []
        for label, keys in specs:
            value = first(row, keys)
            if value:
                out.append(f"{label}: {patched_tr(value, lang)}")
        for key in (f"{prefix}_snapshot", f"{prefix}_notes", f"{prefix}_team_notes"):
            out.extend(split_value(row.get(key)))
        if not out:
            for key in ("team_form", "recent_form", "form_angle", "sports_context_summary", "game_preview", "preview_summary"):
                out.extend(split_value(row.get(key)))
        return [patched_tr(item, lang) for item in out[:4]]

    def repaint_team_snapshots(img, pick: Any, lang: str, use_team_logo: bool) -> None:
        row = dict(m._row(pick))
        away, home = m._teams(row)
        away_label, home_label = patched_team_label(away, lang), patched_team_label(home, lang)
        right_x, right_w = 352, 708
        divider = right_x + right_w // 2
        snap_w = right_w // 2 - 52
        y = 585
        d = m.ImageDraw.Draw(img, "RGBA")
        d.rectangle((right_x + 3, y + 58, right_x + right_w - 3, y + 362), fill=m.CREAM)
        d.line((divider, 660, divider, 922), fill=m.BLACK + (170,), width=1)
        for x, label, color, prefix in (
            (right_x + 24, away_label, m.RED, "away"),
            (divider + 24, home_label, m.BLUE, "home"),
        ):
            m._badge(img, d, label, x, 675, 50, 50, color, use_team_logo)
            d.text((x + 66, 684), label.upper(), font=safe_fit(label.upper(), snap_w - 70, 25, 7, True), fill=color)
            items = team_items(row, prefix, lang)
            if not items:
                items = [m.TEAM_DATA_FALLBACK, "Use team form, injuries, and market movement before publishing."]
            safe_bullets_auto(d, x, 751, items, snap_w - 10, 170, color, 18, 6, 4, lang)

    def repaint_risk_market(img, pick: Any, lang: str, sy: int = 456) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        risk_raw = m._clean(m._get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=m.NO_VERIFIED), True)
        risk = compact_risk(patched_tr(risk_raw, lang), lang)
        market = patched_tr(m._clean(m._get(pick, "market_type", "market", "bet_type", default=m.NO_VERIFIED), True), lang)
        metric_fit(d, 830, sy + 6, 148, "RISK", risk, m.GREEN, lang)
        m._metric(d, 978, sy + 6, 82, "MARKET", market, m.CREAM, lang)

    def validate_magazine_layout_no_overflow(pick: Any, language: str = "en") -> list[str]:
        lang = m._lang(pick, language)
        row = dict(m._row(pick))
        away, home = m._teams(row)
        d = m.ImageDraw.Draw(m.Image.new("RGB", (10, 10)))
        checks = [
            ("away_headline", patched_team_label(away, lang).upper(), 574, 132),
            ("home_headline", patched_team_label(home, lang).upper(), 498, 104),
            ("risk_metric", compact_risk(m._get(row, "risk", "risk_level", "risk_label", default="RESEARCH ONLY"), lang), 134, 18),
            ("market_metric", m._get(row, "market", "market_type", default="TOTALS"), 70, 18),
        ]
        warnings: list[str] = []
        for name, text, width, start in checks:
            value = patched_tr(text, lang).upper()
            font = safe_fit(value, width, start, 5, True)
            if any(d.textbbox((0, 0), line, font=font)[2] > width for line in safe_wrap(d, value, font, width, 2)):
                warnings.append(name)
        return warnings

    def patched_render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None):
        m._wrap = safe_wrap
        m._fit = safe_fit
        m._txt_auto = safe_txt_auto
        m._bullets_auto = safe_bullets_auto
        m._headline_font = safe_headline_font
        m._team_label = patched_team_label
        img = original_render(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        lang = m._lang(pick, language)
        repaint_team_snapshots(img, pick, lang, use_team_logo)
        repaint_risk_market(img, pick, lang)
        return img

    m._tr = patched_tr
    m._wrap = safe_wrap
    m._fit = safe_fit
    m._txt_auto = safe_txt_auto
    m._bullets_auto = safe_bullets_auto
    m._headline_font = safe_headline_font
    m._team_label = patched_team_label
    m.render_full_pick_magazine_page = patched_render_full_pick_magazine_page
    m.validate_magazine_layout_no_overflow = validate_magazine_layout_no_overflow
    m._aba_magazine_metric_patch_v1 = True
    m._aba_magazine_metric_patch_v2 = True
    m._aba_magazine_metric_patch_v3 = True
    m._aba_magazine_metric_patch_v4 = True
