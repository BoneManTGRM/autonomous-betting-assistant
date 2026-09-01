from __future__ import annotations

from typing import Any, Iterable
import re


def install() -> None:
    """Deterministic magazine renderer patch.

    Keeps the public magazine API stable while improving text fitting,
    public risk labels, Mexico-friendly Spanish, and row-context display.
    """
    from . import magazine_book_export as m

    if getattr(m, "_aba_magazine_layout_patch_v1", False):
        return

    original_tr = m._tr
    original_render = m.render_full_pick_magazine_page
    original_wrap = m._wrap

    Rect = tuple[int, int, int, int]
    MAGAZINE_LAYOUT_RECTS: dict[str, Rect] = {
        "headline_area": (20, 90, 610, 455),
        "away_headline": (36, 102, 596, 204),
        "vs_badge": (38, 218, 102, 284),
        "home_headline": (116, 214, 596, 308),
        "season_bar": (36, 330, 506, 378),
        "context_line": (42, 394, 600, 450),
        "hero_image": (620, 105, 1050, 455),
        "trend_pick": (50, 508, 260, 548),
        "metric_risk": (830, 462, 978, 556),
        "metric_market": (978, 462, 1060, 556),
        "final_action": (284, 1392, 630, 1455),
        "final_pick": (284, 1460, 650, 1505),
        "final_explanation": (670, 1412, 1010, 1496),
    }

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
        "LOW": "BAJO",
        "MEDIUM": "MEDIO",
        "HIGH": "ALTO",
        "RESEARCH": "INVESTIGACIÓN",
        "REVIEW": "REVISAR",
    }
    risk_display_en = {
        "LOW": "LOW",
        "MEDIUM": "MEDIUM",
        "HIGH": "HIGH",
        "RESEARCH": "RESEARCH",
        "REVIEW": "REVIEW",
    }

    def patched_team_label(team: str, lang: str) -> str:
        text = str(team or "").strip()
        return country_es.get(text.lower(), text) if lang == "es" else text

    def patched_tr(v: Any, lang: str) -> str:
        protected = str(v or "")
        provider_tokens = {
            "API-Football": "__ABA_PROVIDER_API_FOOTBALL__",
            "SportsDataIO": "__ABA_PROVIDER_SPORTSDATAIO__",
            "WeatherAPI": "__ABA_PROVIDER_WEATHERAPI__",
            "NewsAPI": "__ABA_PROVIDER_NEWSAPI__",
            "Perplexity": "__ABA_PROVIDER_PERPLEXITY__",
            "BALLDONTLIE": "__ABA_PROVIDER_BALLDONTLIE__",
            "The Odds API": "__ABA_PROVIDER_THE_ODDS_API__",
            "Odds API": "__ABA_PROVIDER_ODDS_API__",
        }
        for brand, token in provider_tokens.items():
            protected = protected.replace(brand, token)
        text = original_tr(protected, lang)
        if m._bad(text):
            return text
        raw = str(text)
        if lang == "es":
            phrase_map = {
                "ABA SIGNAL PRO - BILINGUAL VALIDATION": "ABA SIGNAL PRO - VALIDACIÓN BILINGÜE",
                "SYNTHETIC TEST DATA - NOT LIVE SPORTS INFORMATION": "DATOS DE PRUEBA SINTÉTICOS - NO ES INFORMACIÓN DEPORTIVA EN VIVO",
                "Synthetic validation fixture": "Fixture sintético de validación",
                "No live sports data; test only.": "Sin datos deportivos en vivo; solo prueba.",
                "Team stats were not returned by active APIs.": "Las APIs activas no devolvieron estadísticas del equipo.",
                "Confirm form, injuries, and market movement before publishing.": "Confirmar forma, lesiones y movimiento del mercado antes de publicar.",
                "Synthetic fixture used only to validate report completeness and Page 2 calculations.": "Fixture sintético usado solo para validar la integridad del reporte y los cálculos de la página 2.",
                "Unavailable - no live market feed used.": "No disponible; no se usó una fuente de mercado en vivo.",
                "ABA test harness": "Banco de pruebas ABA",
                "TEST FIXTURE": "FIXTURE DE PRUEBA",
                "FALLBACK MODE": "MODO DE RESPALDO",
                "NO LIVE FEEDS USED": "NO SE USARON FUENTES EN VIVO",
            }
            for src, dst in phrase_map.items():
                raw = re.sub(re.escape(src), dst, raw, flags=re.I)
            raw = re.sub(r"Model projects\s+([^ ]+)\s+probability for\s+(.+?)\.?$", r"El modelo proyecta \1 de probabilidad para \2.", raw, flags=re.I)
            raw = re.sub(r"Market-implied probability checks at\s+(.+?)\.?$", r"La probabilidad implícita del mercado es \1.", raw, flags=re.I)
            raw = re.sub(r"Measured edge:\s*", "Ventaja medida: ", raw, flags=re.I)
            raw = re.sub(r"Expected value:\s*", "Valor esperado: ", raw, flags=re.I)
            raw = re.sub(r"\bCUOTA\b", "MOMIO", raw, flags=re.I)
            raw = re.sub(r"\bcuota\b", "momio", raw, flags=re.I)
            raw = re.sub(r"\bcuotas\b", "momios", raw, flags=re.I)
            raw = re.sub(r"\bPrice Watch / Research\b", "Seguimiento de momio / investigación", raw, flags=re.I)
            raw = re.sub(r"\bPrice Watch\b", "Seguimiento de momio", raw, flags=re.I)
            raw = re.sub(r"\bNegative at listed odds\b", "Negativo con el momio actual", raw, flags=re.I)
            for src, dst in sport_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
            for src, dst in country_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        for brand, token in provider_tokens.items():
            raw = raw.replace(token, brand)
        return raw

    def rect_w(rect: Rect) -> int:
        return rect[2] - rect[0]

    def rect_h(rect: Rect) -> int:
        return rect[3] - rect[1]

    def rect_intersects(a: Rect, b: Rect, padding: int = 0) -> bool:
        return not (a[2] + padding <= b[0] or b[2] + padding <= a[0] or a[3] + padding <= b[1] or b[3] + padding <= a[1])

    def rect_contains(outer: Rect, inner: Rect) -> bool:
        return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]

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

    def fit_text_single_line(d, text: str, rect: Rect, max_font: int, min_font: int, bold: bool = True):
        for size in range(max_font, max(4, min_font) - 1, -1):
            font = m._font(size, bold)
            if d.textbbox((0, 0), str(text), font=font)[2] <= rect_w(rect) and m._line_height(font) <= rect_h(rect):
                return font
        return m._font(max(4, min_font), bold)

    def fit_text_wrapped(d, text: str, rect: Rect, max_font: int, min_font: int, bold: bool = False, max_lines: int | None = None):
        floor = max(4, min_font)
        if max_lines == 1:
            return fit_text_single_line(d, str(text), rect, max_font, min_font, bold), [str(text)]
        for size in range(max_font, floor - 1, -1):
            font = m._font(size, bold)
            lines = safe_wrap(d, str(text), font, rect_w(rect), max_lines)
            if lines and len(lines) * m._line_height(font) <= rect_h(rect):
                return font, lines
        font = m._font(floor, bold)
        return font, safe_wrap(d, str(text), font, rect_w(rect), max_lines)

    def draw_text_in_rect(d, text: str, rect: Rect, max_font: int, min_font: int, bold: bool = False, fill: Any = None, align: str = "left", max_lines: int | None = None) -> list[Rect]:
        fill = m.TEXT if fill is None else fill
        font, lines = fit_text_wrapped(d, str(text), rect, max_font, min_font, bold, max_lines)
        line_h = m._line_height(font)
        y = rect[1]
        boxes: list[Rect] = []
        for line in lines:
            if y + line_h > rect[3]:
                break
            bbox = d.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            if align == "center":
                x = rect[0] + (rect_w(rect) - tw) // 2
            elif align == "right":
                x = rect[2] - tw
            else:
                x = rect[0]
            d.text((x, y), line, font=font, fill=fill)
            boxes.append((int(x), int(y), int(x + tw), int(y + line_h)))
            y += line_h
        return boxes

    def layout_text_boxes(d, text: str, rect: Rect, max_font: int, min_font: int, bold: bool = False, max_lines: int | None = None) -> list[Rect]:
        font, lines = fit_text_wrapped(d, str(text), rect, max_font, min_font, bold, max_lines)
        y = rect[1]
        boxes: list[Rect] = []
        for line in lines:
            if y + m._line_height(font) > rect[3]:
                break
            bbox = d.textbbox((0, 0), line, font=font)
            boxes.append((rect[0], y, rect[0] + bbox[2] - bbox[0], y + m._line_height(font)))
            y += m._line_height(font)
        return boxes

    def safe_fit(text: str, width: int, start: int, minimum: int = 16, bold: bool = True):
        d = m.ImageDraw.Draw(m.Image.new("RGB", (10, 10)))
        return fit_text_single_line(d, str(text), (0, 0, width, 100), start, minimum, bold)

    def safe_txt_auto(d, x: int, y: int, text: str, width: int, height: int, start: int, minimum: int, fill: Any, bold: bool = False, max_lines: int | None = None) -> int:
        boxes = draw_text_in_rect(d, str(text), (x, y, x + width, y + height), start, minimum, bold, fill, "left", max_lines)
        return boxes[-1][3] if boxes else y

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
        return safe_fit(str(text).upper(), width, preferred, 5, True)

    def raw_risk(row: Any) -> str:
        return m._clean(m._get(row, "risk", "risk_level", "risk_label", "profit_guard_status", default="REVIEW"), True)

    def demonstration_mode(row: Any) -> bool:
        data = dict(m._row(row))
        if data.get("demonstration_mode") is True:
            return True
        text = " ".join(
            str(data.get(key) or "").lower()
            for key in ("report_title", "report_data_scope", "report_truth_warning", "league")
        )
        return any(token in text for token in ("demonstration", "demo only", "validation fixture"))

    def normalize_public_risk_label(row: Any, language: str = "en") -> str:
        if demonstration_mode(row):
            return "DEMO"
        raw = raw_risk(row).upper().replace("_", " ")
        if "HIGH" in raw:
            label = "HIGH"
        elif "RESEARCH" in raw or "OFFICIAL" in raw:
            label = "RESEARCH"
        elif "WATCHLIST" in raw or "THIN EDGE" in raw:
            label = "MEDIUM"
        elif "SAFE ACCURACY" in raw or "VOLUME OK" in raw or raw in {"LOW", "SAFE"}:
            label = "LOW"
        elif "MEDIUM" in raw:
            label = "MEDIUM"
        else:
            label = "REVIEW"
        return risk_display_es.get(label, label) if language == "es" else risk_display_en.get(label, label)

    def normalize_liquidity_label(row: Any, language: str = "en") -> str:
        raw = raw_risk(row).upper()
        if "VOLUME" in raw:
            return "Liquidez: OK" if language == "es" else "Market liquidity: OK"
        return "Liquidez: revisar" if language == "es" else "Market liquidity: review"

    def normalize_data_quality_label(row: Any, language: str = "en") -> str:
        raw = raw_risk(row).upper()
        if "SAFE ACCURACY" in raw:
            return "Patrón de precisión: aprobado" if language == "es" else "Accuracy pattern: passed"
        if "RESEARCH" in raw:
            return "Datos oficiales: incompletos" if language == "es" else "Official data: incomplete"
        return "Calidad de datos: parcial" if language == "es" else "Data quality: partial"

    def risk_desk_bullets(row: Any, language: str = "en") -> list[str]:
        if demonstration_mode(row):
            if language == "es":
                return ["Solo demostración", "No es consejo de apuesta actual", "Reemplazar cada cuota antes de publicar"]
            return ["Demonstration only", "Not current betting advice", "Replace all prices first"]
        raw = raw_risk(row).upper().replace("_", " ")
        if language == "es":
            if "RESEARCH" in raw:
                return ["Estado: investigación", "Falta verificación oficial o contexto", "No publicar como prueba pública"]
            if "WATCHLIST" in raw:
                return ["Estado: seguimiento", "Esperar mejor momio o confirmación", "Revisar noticias antes de entrar"]
            if "THIN EDGE" in raw:
                return ["Ventaja delgada", "El movimiento del momio puede borrar el valor", "Revisar antes de entrar"]
            if "VOLUME" in raw:
                return ["Liquidez de mercado: OK", "Revisar momio antes de entrar", "Evitar si cambian noticias clave"]
            if "SAFE ACCURACY" in raw:
                return ["Estabilidad del modelo: OK", "Patrón de precisión: aprobado", "Revisar momio antes de entrar"]
            if "HIGH" in raw:
                return ["Riesgo alto", "Reducir exposición", "Confirmar noticias clave"]
            return ["Estado: revisar", "Datos incompletos", "Revisar antes de entrar"]
        if "RESEARCH" in raw:
            return ["Status: Research only", "Missing official verification or context", "Do not publish as public proof"]
        if "WATCHLIST" in raw:
            return ["Status: Watchlist", "Wait for better price or confirmation", "Recheck news before entry"]
        if "THIN EDGE" in raw:
            return ["Thin edge", "Line movement can erase value", "Recheck before entry"]
        if "VOLUME" in raw:
            return ["Market liquidity: OK", "Recheck odds before entry", "Avoid if key news changes"]
        if "SAFE ACCURACY" in raw:
            return ["Model stability: OK", "Accuracy pattern: passed", "Recheck odds before entry"]
        if "HIGH" in raw:
            return ["High risk", "Reduce exposure", "Confirm key news"]
        return ["Status: Review", "Data is incomplete", "Recheck before entry"]

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

    def enrich_report_row_context(row_like: Any, config: Any = None, language: str = "en") -> dict[str, Any]:
        row = dict(m._row(row_like))
        row.setdefault("team_context_unavailable_reason", "Team stats were not returned by active APIs." if language != "es" else "Las APIs activas no devolvieron estadísticas del equipo.")
        row.setdefault("player_context_unavailable_reason", "Player/injury data was not returned by active APIs." if language != "es" else "Las APIs activas no devolvieron datos de jugadores o lesiones.")
        row.setdefault("venue_context_unavailable_reason", "Venue was not provided by the available API." if language != "es" else "La API disponible no proporcionó sede.")
        return row

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
        provider_items = getattr(m, "team_items", None)
        if callable(provider_items):
            for item in provider_items(row, prefix):
                if item not in out:
                    out.append(item)
        return [patched_tr(item, lang) for item in out[:4]]

    def draw_metric_cell(d, rect: Rect, label: str, value: str, value_color: tuple[int, int, int], language: str) -> None:
        d.rectangle(rect, fill=m.BLACK, outline=(230, 224, 204), width=1)
        draw_text_in_rect(d, patched_tr(label, language).upper(), (rect[0] + 7, rect[1] + 9, rect[2] - 6, rect[1] + 31), 16, 6, True, (232, 230, 220), max_lines=1)
        draw_text_in_rect(d, str(value or "").upper(), (rect[0] + 7, rect[1] + 42, rect[2] - 6, rect[3] - 6), 20, 5, True, value_color, max_lines=2)

    def draw_headline_block(img, pick: Any, lang: str) -> None:
        row = dict(m._row(pick))
        away, home = m._teams(row)
        away_label, home_label = patched_team_label(away, lang), patched_team_label(home, lang)
        d = m.ImageDraw.Draw(img, "RGBA")
        d.rectangle(MAGAZINE_LAYOUT_RECTS["headline_area"], fill=m.PAPER)
        away_rect = MAGAZINE_LAYOUT_RECTS["away_headline"]
        home_rect = MAGAZINE_LAYOUT_RECTS["home_headline"]
        vs_rect = MAGAZINE_LAYOUT_RECTS["vs_badge"]
        draw_text_in_rect(d, away_label.upper(), away_rect, 84, 14, True, m.RED, max_lines=2)
        d.rounded_rectangle(vs_rect, radius=7, fill=m.CREAM, outline=m.BLACK, width=2)
        draw_text_in_rect(d, "VS", (vs_rect[0] + 8, vs_rect[1] + 13, vs_rect[2] - 8, vs_rect[3] - 8), 34, 16, True, m.BLACK, "center", 1)
        draw_text_in_rect(d, home_label.upper(), home_rect, 74, 14, True, m.BLUE, max_lines=2)
        sport = m._get(row, "sport", "league", default="Sport N/A")
        season = patched_tr(m._get(row, "season_label", "event_stage", "competition_round", default=f"{sport} REGULAR SEASON"), lang).upper()
        season_rect = MAGAZINE_LAYOUT_RECTS["season_bar"]
        d.rectangle(season_rect, fill=m.BLACK)
        draw_text_in_rect(d, season, (season_rect[0] + 18, season_rect[1] + 9, season_rect[2] - 14, season_rect[3] - 6), 27, 10, True, m.CREAM, max_lines=1)
        ctx: list[str] = []
        for k in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
            ctx += split_value(row.get(k))
        context = patched_tr((ctx or ["Context unavailable."])[0], lang)
        draw_text_in_rect(d, context, MAGAZINE_LAYOUT_RECTS["context_line"], 20, 10, False, m.TEXT, max_lines=2)

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
        for x, label, color, prefix in ((right_x + 24, away_label, m.RED, "away"), (divider + 24, home_label, m.BLUE, "home")):
            m._badge(img, d, label, x, 675, 50, 50, color, use_team_logo)
            draw_text_in_rect(d, label.upper(), (x + 66, 682, x + snap_w, 724), 24, 7, True, color, max_lines=1)
            items = team_items(row, prefix, lang)
            if not items:
                items = [
                    row.get("team_context_unavailable_reason") or m.TEAM_DATA_FALLBACK,
                    "Confirmar forma, lesiones y movimiento del mercado antes de publicar." if lang == "es" else "Confirm form, injuries, and market movement before publishing.",
                ]
            safe_bullets_auto(d, x, 751, items, snap_w - 10, 170, color, 18, 6, 4, lang)

    def repaint_risk_market(img, pick: Any, lang: str, sy: int = 456) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        risk = normalize_public_risk_label(pick, lang)
        market = patched_tr(m._clean(m._get(pick, "market_type", "market", "bet_type", default=m.NO_VERIFIED), True), lang)
        draw_metric_cell(d, MAGAZINE_LAYOUT_RECTS["metric_risk"], "RISK", risk, m.GREEN, lang)
        draw_metric_cell(d, MAGAZINE_LAYOUT_RECTS["metric_market"], "MARKET", market, m.CREAM, lang)

    def repaint_risk_desk(img, pick: Any, lang: str) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        x, y, w, h = 20, 1178, 320, 175
        m._section(d, x, y, w, h, "RISK DESK", m.RED, lang)
        safe_bullets_auto(d, x + 24, y + 70, risk_desk_bullets(pick, lang), w - 48, h - 88, m.RED, 15, 7, 3, lang)

    def repaint_final_bar(img, pick: Any, lang: str) -> None:
        row = dict(m._row(pick))
        d = m.ImageDraw.Draw(img, "RGBA")
        fy, fb = 1374, 1532
        d.rounded_rectangle((20, fy, m.PAGE_WIDTH - 20, fb), radius=14, fill=m.BLACK, outline=m.RED, width=3)
        d.rectangle((20, fy, 250, fb), fill=m.RED)
        draw_text_in_rect(d, patched_tr("FINAL", lang), (40, fy + 30, 232, fy + 66), 30, 16, True, m.CREAM, max_lines=1)
        draw_text_in_rect(d, patched_tr("RECOMMENDATION", lang), (40, fy + 76, 232, fy + 106), 22, 12, True, m.CREAM, max_lines=1)
        action = patched_tr(m._clean(m._get(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="PLAY STANDARD"), True), lang).upper()
        pick_text = patched_tr(m._clean(m._get(row, "prediction", "exact_bet", "pick", "selection", default=m.NOT_PROVIDED), True), lang).upper()
        expl = patched_tr(m._get(row, "final_explanation", "action_reason", "recommendation_reason", "decision_reasons", default="Use only if the line remains playable and key news does not change."), lang)
        draw_text_in_rect(d, action, MAGAZINE_LAYOUT_RECTS["final_action"], 52, 16, True, m.GREEN, max_lines=2)
        draw_text_in_rect(d, pick_text, MAGAZINE_LAYOUT_RECTS["final_pick"], 30, 8, True, m.CREAM, max_lines=2)
        draw_text_in_rect(d, expl, MAGAZINE_LAYOUT_RECTS["final_explanation"], 20, 8, False, m.CREAM, max_lines=4)

    def _boxes_for_validation(pick: Any, lang: str) -> dict[str, list[Rect]]:
        row = dict(m._row(pick))
        away, home = m._teams(row)
        d = m.ImageDraw.Draw(m.Image.new("RGB", (10, 10)))
        boxes: dict[str, list[Rect]] = {
            "away_headline": layout_text_boxes(d, patched_team_label(away, lang).upper(), MAGAZINE_LAYOUT_RECTS["away_headline"], 84, 14, True, 2),
            "home_headline": layout_text_boxes(d, patched_team_label(home, lang).upper(), MAGAZINE_LAYOUT_RECTS["home_headline"], 74, 14, True, 2),
            "season_bar": layout_text_boxes(d, patched_tr(m._get(row, "season_label", "event_stage", "competition_round", default=f"{m._get(row, 'sport', 'league', default='Sport')} REGULAR SEASON"), lang).upper(), (54, 339, 492, 372), 27, 10, True, 1),
            "risk_metric": layout_text_boxes(d, normalize_public_risk_label(row, lang), (837, 504, 972, 550), 20, 5, True, 2),
            "market_metric": layout_text_boxes(d, m._get(row, "market", "market_type", default="TOTALS"), (985, 504, 1054, 550), 18, 5, True, 2),
            "final_action": layout_text_boxes(d, m._get(row, "final_decision", "agent_decision", "recommendation", "consumer_action", default="PLAY STANDARD"), MAGAZINE_LAYOUT_RECTS["final_action"], 52, 16, True, 2),
            "final_pick": layout_text_boxes(d, m._get(row, "prediction", "exact_bet", "pick", "selection", default=m.NOT_PROVIDED), MAGAZINE_LAYOUT_RECTS["final_pick"], 30, 8, True, 2),
        }
        return boxes

    def validate_magazine_layout_no_overflow(pick: Any, language: str = "en") -> list[str]:
        lang = m._lang(pick, language)
        boxes = _boxes_for_validation(pick, lang)
        warnings: list[str] = []
        for name, items in boxes.items():
            outer = MAGAZINE_LAYOUT_RECTS.get(name, None)
            if name == "season_bar":
                outer = MAGAZINE_LAYOUT_RECTS["season_bar"]
            if outer is None:
                continue
            for box in items:
                if not rect_contains(outer, box):
                    warnings.append(f"{name}:outside")
                if rect_intersects(box, MAGAZINE_LAYOUT_RECTS["hero_image"], padding=12):
                    warnings.append(f"{name}:hero")
        for away_box in boxes.get("away_headline", []):
            for home_box in boxes.get("home_headline", []):
                if rect_intersects(away_box, home_box, padding=14):
                    warnings.append("headline:away_home_overlap")
            if rect_intersects(away_box, MAGAZINE_LAYOUT_RECTS["vs_badge"], padding=12):
                warnings.append("headline:away_vs_overlap")
        for home_box in boxes.get("home_headline", []):
            if rect_intersects(home_box, MAGAZINE_LAYOUT_RECTS["vs_badge"], padding=12):
                warnings.append("headline:home_vs_overlap")
        for home_box in boxes.get("home_headline", []):
            if rect_intersects(home_box, MAGAZINE_LAYOUT_RECTS["season_bar"], padding=12):
                warnings.append("headline:season_overlap")
        return sorted(set(warnings))

    def patched_render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None):
        lang = m._lang(pick, language)
        row = enrich_report_row_context(pick, language=lang)
        m._wrap = safe_wrap
        m._fit = safe_fit
        m._txt_auto = safe_txt_auto
        m._bullets_auto = safe_bullets_auto
        m._headline_font = safe_headline_font
        m._team_label = patched_team_label
        img = original_render(row, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        draw_headline_block(img, row, lang)
        repaint_team_snapshots(img, row, lang, use_team_logo)
        repaint_risk_market(img, row, lang)
        repaint_risk_desk(img, row, lang)
        repaint_final_bar(img, row, lang)
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
    m.normalize_public_risk_label = normalize_public_risk_label
    m.risk_desk_bullets = risk_desk_bullets
    m.normalize_liquidity_label = normalize_liquidity_label
    m.normalize_data_quality_label = normalize_data_quality_label
    m.enrich_report_row_context = enrich_report_row_context
    m.MAGAZINE_LAYOUT_RECTS = MAGAZINE_LAYOUT_RECTS
    m.rect_intersects = rect_intersects
    m._aba_magazine_metric_patch_v1 = True
    m._aba_magazine_metric_patch_v2 = True
    m._aba_magazine_metric_patch_v3 = True
    m._aba_magazine_metric_patch_v4 = True
    m._aba_magazine_layout_patch_v1 = True
