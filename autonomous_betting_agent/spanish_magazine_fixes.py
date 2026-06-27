from __future__ import annotations

import re
from typing import Any

COUNTRY_ES_EXTRA = {
    "belgium": "Bélgica",
    "morocco": "Marruecos",
    "switzerland": "Suiza",
    "scotland": "Escocia",
    "uzbekistan": "Uzbekistán",
    "panama": "Panamá",
    "haiti": "Haití",
    "croatia": "Croacia",
    "austria": "Austria",
    "curacao": "Curazao",
    "curaçao": "Curazao",
    "new zealand": "Nueva Zelanda",
    "norway": "Noruega",
    "ivory coast": "Costa de Marfil",
    "cote d'ivoire": "Costa de Marfil",
    "côte d'ivoire": "Costa de Marfil",
    "netherlands": "Países Bajos",
    "tunisia": "Túnez",
    "iran": "Irán",
    "iraq": "Irak",
    "egypt": "Egipto",
    "algeria": "Argelia",
    "jordan": "Jordania",
    "canada": "Canadá",
    "brazil": "Brasil",
    "portugal": "Portugal",
    "south korea": "Corea del Sur",
    "czech republic": "República Checa",
    "czechia": "Chequia",
    "united states": "Estados Unidos",
    "usa": "Estados Unidos",
    "denmark": "Dinamarca",
    "sweden": "Suecia",
    "poland": "Polonia",
    "romania": "Rumanía",
    "saudi arabia": "Arabia Saudita",
    "united arab emirates": "Emiratos Árabes Unidos",
    "south africa": "Sudáfrica",
    "wales": "Gales",
    "ireland": "Irlanda",
    "northern ireland": "Irlanda del Norte",
}

WEATHER_ES = (
    ("Weather:", "Clima:"),
    ("Location:", "Ubicación:"),
    ("weather checked", "clima revisado"),
    ("wind", "viento"),
    ("Partly cloudy", "parcialmente nublado"),
    ("partly cloudy", "parcialmente nublado"),
    ("Sunny", "soleado"),
    ("sunny", "soleado"),
    ("Clear", "despejado"),
    ("clear", "despejado"),
    ("Overcast", "nublado"),
    ("overcast", "nublado"),
    ("Mist", "neblina"),
    ("mist", "neblina"),
    ("Patchy rain nearby", "lluvia cercana"),
    ("patchy rain nearby", "lluvia cercana"),
    ("Light rain", "lluvia ligera"),
    ("light rain", "lluvia ligera"),
    ("Moderate or heavy rain with thunder", "lluvia y tormenta"),
    ("moderate or heavy rain with thunder", "lluvia y tormenta"),
)


def _compact_weather_message(mas: Any, text: str) -> list[str]:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    lower = value.lower()
    if lower.startswith("weather:"):
        value = "WeatherAPI:" + value.split(":", 1)[1]
        lower = value.lower()
    if lower.startswith("weatherapi:"):
        body = value.split(":", 1)[1].strip()
        location = ""
        location_match = re.search(r"\bLocation:\s*(.+)$", body, flags=re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip(" .")
            body = body[: location_match.start()].strip(" .")

        bits = [part.strip(" .") for part in body.split(";") if part.strip(" .")]
        if len(bits) <= 1:
            expanded = re.sub(r"\.\s*", ", ", body)
            bits = [part.strip(" .") for part in expanded.split(",") if part.strip(" .")]

        deduped: list[str] = []
        seen: set[str] = set()
        for bit in bits:
            clean = re.sub(r"\s+", " ", bit).strip(" .")
            key = clean.lower()
            if clean and key not in seen:
                deduped.append(clean)
                seen.add(key)

        temperature = next((bit for bit in deduped if re.search(r"-?\d+(?:\.\d+)?\s*°\s*[CF]\b", bit, re.IGNORECASE)), "")
        wind = next((bit for bit in deduped if re.search(r"\bwind\s*-?\d+(?:\.\d+)?\s*kph\b", bit, re.IGNORECASE)), "")
        condition = next((bit for bit in deduped if bit not in {temperature, wind} and "location:" not in bit.lower()), "")

        ordered = []
        if temperature:
            ordered.append(temperature.replace(" ", ""))
        if condition:
            ordered.append(condition[:1].lower() + condition[1:])
        if wind:
            ordered.append(wind.lower())
        if not ordered:
            ordered = deduped[:3]

        out = ["Weather: " + ", ".join(ordered[:3]) + "."]
        if location:
            out.append("Location: " + mas._shorten_location(location) + ".")
        return out
    if lower.startswith("weatherapi checked"):
        location = value.replace("WeatherAPI checked", "", 1).split(";", 1)[0].strip()
        return [f"Weather checked: {mas._shorten_location(location)}; no live payload."] if location else ["Weather checked; no live payload."]
    if lower.startswith("weatherapi configured"):
        return ["Weather checked; no venue/location in row."]
    return [value]


def install() -> None:
    from . import magazine_api_sources as mas
    from . import magazine_book_export as m

    if getattr(m, "_aba_spanish_magazine_fixes_v1", False):
        return

    try:
        m.COUNTRY_ES.update(COUNTRY_ES_EXTRA)
    except Exception:
        pass
    try:
        from . import report_product_layer as rpl
        rpl.COUNTRY_ES.update(COUNTRY_ES_EXTRA)
    except Exception:
        pass

    mas._compact_weather_message = lambda text: _compact_weather_message(mas, text)

    original_tr = m._tr

    def patched_tr(value: Any, lang: str) -> str:
        text = original_tr(value, lang)
        if lang != "es" or not isinstance(text, str):
            return text
        for old, new in WEATHER_ES:
            text = text.replace(old, new)
        return text

    def compact_note(value: Any, lang: str) -> str:
        text = patched_tr(value, lang)
        if lang == "es":
            text = text.replace("sin coincidencia de partido", "sin partido")
            text = text.replace("sin artículos recientes relacionados", "sin noticias recientes")
            text = text.replace("búsqueda revisada", "revisado")
            text = re.sub(r"\bUbicación:\s*", "Ubic.: ", text)
        return str(text)

    current_render = m.render_full_pick_magazine_page

    def draw_readable_matchup_notes(img: Any, pick: Any, lang: str) -> None:
        if lang != "es":
            return
        draw = m.ImageDraw.Draw(img, "RGBA")
        x, y, width, height = 354, 1178, 344, 175
        m._section(draw, x, y, width, height, "MATCHUP NOTES", m.BLUE, lang)
        items = [compact_note(item, lang) for item in m._matchup_items(pick)[:3]]
        font = m._font(11, False)
        line_h = m._line_height(font)
        cursor = y + 70
        bottom = y + height - 10
        for item in items:
            lines = m._wrap_text_to_box(draw, item, font, width - 58, 2)
            if cursor + len(lines) * line_h > bottom:
                break
            draw.ellipse((x + 24, cursor + 7, x + 36, cursor + 19), fill=m.BLUE)
            for line in lines:
                draw.text((x + 48, cursor), m._ellipsize_to_width(draw, line, font, width - 62), font=font, fill=m.TEXT)
                cursor += line_h
            cursor += 5

    def patched_render(pick: Any, *args: Any, **kwargs: Any):
        img = current_render(pick, *args, **kwargs)
        language = kwargs.get("language")
        if language is None and len(args) >= 11:
            language = args[10]
        draw_readable_matchup_notes(img, pick, m._lang(pick, language))
        return img

    m._tr = patched_tr
    m.render_full_pick_magazine_page = patched_render
    m._aba_spanish_magazine_fixes_v1 = True
