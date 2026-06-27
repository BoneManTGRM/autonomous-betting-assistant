from __future__ import annotations

from typing import Any

from autonomous_betting_agent.multi_leg_report import format_items

_FLAG = "_ABA_MAGAZINE_COMBO_SECTION_PATCHED_V1"


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _lang(row: dict[str, Any]) -> str:
    text = str(row.get("report_language") or row.get("language") or row.get("lang") or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _split_items(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na", "--"}:
        return []
    for sep in ("|", ";", "\n", "•"):
        text = text.replace(sep, "\n")
    return [part.strip(" -•") for part in text.splitlines() if part.strip(" -•")]


def combo_section_items(row_value: Any) -> list[str]:
    row = _row(row_value)
    explicit: list[str] = []
    for key in ("parlay_magazine_items", "combo_magazine_items", "parlay_recommendation", "combo_recommendation", "parlay_note", "combo_note"):
        explicit.extend(_split_items(row.get(key)))
    if explicit:
        return explicit[:3]
    return format_items([row], _lang(row), 3)


def install(module: Any) -> Any:
    if getattr(module, _FLAG, False):
        return module
    module.chain_items = combo_section_items
    module._chain_items = combo_section_items
    setattr(module, _FLAG, True)
    return module
