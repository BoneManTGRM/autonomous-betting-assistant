from __future__ import annotations

from typing import Any, Iterable, Sequence

SPORT_LEAGUE_ES = {
    "Boxing": "Boxeo",
    "MMA": "MMA",
    "MLB": "MLB",
    "NCAAB": "NCAAB",
    "NCAAF": "NCAAF",
    "NBA": "NBA",
    "NFL": "NFL",
    "NHL": "NHL",
    "FIFA World Cup": "Copa Mundial FIFA",
    "League of Ireland": "Liga de Irlanda",
    "Brazil Série B": "Brasil Serie B",
    "Brazil Serie B": "Brasil Serie B",
    "Soccer": "Fútbol",
    "Football": "Fútbol americano",
    "Basketball": "Baloncesto",
    "Baseball": "Béisbol",
    "Tennis": "Tenis",
    "English Premier League": "Premier League inglesa",
    "Premier League": "Premier League",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Liga MX": "Liga MX",
}


def sport_league_display_text(value: Any, language: str = "en") -> str:
    text = str(value or "").strip()
    if language == "es":
        return SPORT_LEAGUE_ES.get(text, text)
    return text


def selected_raw_sport_values(display_values: Iterable[str], options: Sequence[str], language: str = "en") -> list[str]:
    """Map displayed Spanish labels back to raw sport/league values."""
    wanted = {str(value or "").strip() for value in display_values}
    selected: list[str] = []
    for option in options:
        display = sport_league_display_text(option, language)
        if option in wanted or display in wanted:
            selected.append(option)
    return selected


def render_sport_league_filter(st, *, label: str, options: Sequence[str], default: Iterable[str] | None = None, language: str = "en", key: str = "report_profile_sports") -> list[str]:
    raw_options = [str(option) for option in options if str(option or "").strip()]
    default_set = {str(value) for value in (default or []) if str(value) in raw_options}
    if language != "es":
        return list(st.multiselect(label, raw_options, default=[option for option in raw_options if option in default_set], key=key))

    st.caption("Elige opciones")
    select_all = st.checkbox("Seleccionar todos", value=bool(raw_options) and len(default_set) == len(raw_options), key=f"{key}_select_all")
    if select_all:
        return raw_options

    selected: list[str] = []
    with st.container():
        for option in raw_options:
            option_key = "".join(ch if ch.isalnum() else "_" for ch in option.lower()).strip("_") or "option"
            checked = st.checkbox(sport_league_display_text(option, "es"), value=option in default_set, key=f"{key}_{option_key}")
            if checked:
                selected.append(option)
    return selected
