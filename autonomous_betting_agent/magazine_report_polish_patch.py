from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlencode

_PATCH_VERSION = "magazine_report_display_polish_v3_live_odds_match"

SOURCE_LABELS = {
    "Odds API": "Odds",
    "The Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _live_odds_marker(row: Any) -> bool:
    data = _row(row)
    status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    return status in {"live", "live_api", "live_match", "odds_api_live_match"} or source in {"live", "live_api", "the odds api", "odds api"}


def _fallback_row(row: Any) -> bool:
    if _live_odds_marker(row):
        return False
    data = _row(row)
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    status = _clean(data.get("odds_status")).lower()
    mode = _clean(data.get("risk") or data.get("risk_level") or data.get("risk_label")).lower()
    return any(token in source or token in status or token in mode for token in ("uploaded", "fallback", "cached", "missing"))


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item)
        if text and not text.endswith("."):
            text += "."
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _source_label(name: str) -> str:
    return SOURCE_LABELS.get(str(name).strip(), str(name).strip())


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).replace("%", "").replace(",", "").strip()
        if not text or text.lower() in {"nan", "none", "null", "n/a", "na"}:
            return None
        return float(text)
    except Exception:
        return None


def _norm(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"\b(fc|cf|sc|club|team|national|women|men)\b", " ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {part for part in _norm(value).split() if len(part) > 2}


def _team_pair(data: dict[str, Any], live: Any) -> tuple[str, str]:
    try:
        away, home = live._split_teams(data)
        if away and home:
            return str(away), str(home)
    except Exception:
        pass
    away = data.get("away_team") or data.get("team_a") or data.get("team1") or ""
    home = data.get("home_team") or data.get("team_b") or data.get("team2") or ""
    if away and home:
        return str(away), str(home)
    event = _clean(data.get("event") or data.get("event_name") or data.get("matchup") or data.get("game"))
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return "", ""


def _install_renderer_source_labels(module: Any) -> None:
    if getattr(module, "_ABA_SOURCE_LABEL_POLISH_VERSION", "") == _PATCH_VERSION:
        return
    original_api_provenance = getattr(module, "api_provenance", None)
    if not callable(original_api_provenance):
        return

    def polished_api_provenance(row: Any) -> dict[str, list[str]]:
        prov = original_api_provenance(row)
        if _fallback_row(row):
            checked = _dedupe([
                *prov.get("active_sources", []),
                *prov.get("available_no_data_sources", []),
                *prov.get("inactive_sources", []),
            ])
            return {"active_sources": [], "available_no_data_sources": checked, "inactive_sources": []}
        return prov

    def polished_api_provenance_lines(row: Any) -> list[str]:
        prov = polished_api_provenance(row)
        active = [_source_label(name) for name in prov.get("active_sources", [])]
        checked = [_source_label(name) for name in prov.get("available_no_data_sources", [])]
        inactive = [_source_label(name) for name in prov.get("inactive_sources", [])]
        if _fallback_row(row):
            if checked:
                return ["Sources checked: " + " · ".join(checked[:6]) + "; no verified live match."]
            return ["Sources checked: no verified live match."]
        lines: list[str] = []
        if active:
            lines.append("Live sources: " + " · ".join(active))
        if not lines and checked:
            lines.append("Sources checked: " + " · ".join(checked))
        if not lines and inactive:
            lines.append("Sources configured: " + " · ".join(inactive))
        return lines

    def polished_active_note(row: Any) -> str:
        lines = polished_api_provenance_lines(row)
        return lines[0] + ("" if lines[0].endswith(".") else ".") if lines else "Sources checked: none."

    module.api_provenance = polished_api_provenance
    module.api_provenance_lines = polished_api_provenance_lines
    module._active_note = polished_active_note
    module._ABA_SOURCE_LABEL_POLISH_VERSION = _PATCH_VERSION


def install_live_odds_api_match() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    original = getattr(live, "_apply_odds_truth", None)
    if not callable(original) or getattr(original, "_ABA_ODDS_API_MATCH_PATCH", False):
        return

    def apply_odds_truth_with_safe_status(row: dict[str, Any], refresh_time: str) -> None:
        try:
            data = _row(row)
            status = _clean(data.get("odds_status") or data.get("odds_api_status")).lower()
            source = _clean(data.get("odds_source") or data.get("data_source")).lower()
            if status in {"live", "live_api"} or source in {"the odds api", "odds api"}:
                row.setdefault("odds_api_status", "LIVE_MATCH")
                row.setdefault("odds_api_live", "true")
                row.setdefault("the_odds_api_live", "true")
        except Exception:
            pass
        original(row, refresh_time)

    apply_odds_truth_with_safe_status._ABA_ODDS_API_MATCH_PATCH = True
    live._apply_odds_truth = apply_odds_truth_with_safe_status


def _restore_sale_ready_version_suffix(renderer: Any) -> None:
    current = str(getattr(renderer, "MAGAZINE_STYLE_VERSION", ""))
    if current.endswith("_sale_ready_risk_chain_v4"):
        return
    base = re.sub(r"(?:_direct_two_page)?_sale_ready_[a-z_]+_v\d+(?:_[a-z_]+)*$", "", current)
    if not base:
        base = current or "magazine"
    renderer.MAGAZINE_STYLE_VERSION = f"{base}_sale_ready_risk_chain_v4"


def install_sale_ready_polish() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as renderer
        _install_renderer_source_labels(renderer)
        _restore_sale_ready_version_suffix(renderer)
    except Exception:
        pass
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
        sale._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION
    except Exception:
        pass


def install() -> None:
    install_live_odds_api_match()
    install_sale_ready_polish()


install()
