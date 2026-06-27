from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def clean_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = clean_spaces(item)
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def split_items(value: Any) -> list[str]:
    if is_blank(value):
        return []
    return [
        part.strip(" -•")
        for part in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines()
        if part.strip(" -•")
    ]


def explicit_items(row: Mapping[str, Any], keys: Iterable[str]) -> list[str]:
    out: list[str] = []
    for key in keys:
        out.extend(split_items(row.get(key)))
    return dedupe(out)


def short_location(location: str) -> str:
    replacements = {
        "Pennsylvania": "PA",
        "United States of America": "USA",
        "United States": "USA",
    }
    parts = [part.strip() for part in clean_spaces(location).strip(" .").split(",") if part.strip()]
    return ", ".join(replacements.get(part, part) for part in parts)


def compact_weather(text: str) -> list[str]:
    value = clean_spaces(text)
    if not value.lower().startswith(("weather:", "weatherapi:")):
        return []
    body = value.split(":", 1)[1].strip()
    location = ""
    match_location = re.search(r"\bLocation:\s*(.+)$", body, flags=re.I)
    if match_location:
        location = match_location.group(1).strip(" .")
        body = body[: match_location.start()].strip(" .")
    temp_match = re.search(r"-?\d+(?:\.\d+)?\s*°\s*[CF]\b", body, flags=re.I)
    wind_match = re.search(r"wind\s*-?\d+(?:\.\d+)?\s*kph", body, flags=re.I)
    condition_match = re.search(r"^\s*([A-Za-z][A-Za-z\s'-]+?)(?:,|\s+-?\d|\.)", body)
    temp = temp_match.group(0).replace(" ", "") if temp_match else ""
    condition = condition_match.group(1).strip(" ., '").lower() if condition_match else ""
    wind = wind_match.group(0).lower() if wind_match else ""
    parts = [part for part in (temp, condition, wind) if part]
    if not parts:
        return [value]
    out = ["Weather: " + ", ".join(parts) + "."]
    if location:
        out.append("Location: " + short_location(location) + ".")
    return out


def compact_matchup_item(text: str) -> list[str]:
    value = clean_spaces(text)
    low = value.lower()
    if not value:
        return []
    weather = compact_weather(value)
    if weather:
        return weather
    if low.startswith("location:"):
        return ["Location: " + short_location(value.split(":", 1)[1]) + "."]
    if low.startswith("api-fb lookup checked") or low.startswith("api-football checked") or low.startswith("api-fb team lookup checked"):
        return ["API-FB lookup checked; no fixture match."]
    if low.startswith("api-fb lookup only"):
        return ["API-FB lookup checked; no fixture match."]
    return [value.replace("Pennsylvania, United States of America", "PA, USA")]
