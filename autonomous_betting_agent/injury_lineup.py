from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

OUT_LABELS = {"out", "inactive", "injured reserve", "ir", "doubtful", "suspended", "scratched", "ruled out"}
QUESTIONABLE_LABELS = {"questionable", "probable", "day-to-day", "limited", "game time decision", "gtd"}
CONFIRMED_LABELS = {"confirmed", "official", "active", "starting", "available"}
UNCONFIRMED_LABELS = {"projected", "expected", "unknown", "unconfirmed", "pending"}
STAR_HINTS = {"star", "starter", "starting", "key", "captain", "qb", "goalkeeper", "pitcher", "ace", "top"}


@dataclass(frozen=True)
class InjuryLineupRisk:
    injury_risk_score: float
    lineup_confirmed: str
    key_player_out: str
    injury_warning: str
    lineup_do_not_bet_reason: str


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    lowered = {str(key).lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(" ", "_").replace("-", "_"))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _contains_any(text: str, labels: set[str]) -> bool:
    normalized = " ".join(text.lower().split())
    return any(label in normalized for label in labels)


def _is_key_player(row: Mapping[str, Any]) -> bool:
    text = " ".join([
        _first(row, ("player_role", "role", "position", "depth_chart_role")),
        _first(row, ("is_starter", "starter", "starting")),
        _first(row, ("importance", "player_importance", "usage_tier")),
    ]).lower()
    return any(hint in text for hint in STAR_HINTS)


def score_injury_lineup(row: Mapping[str, Any]) -> InjuryLineupRisk:
    status_text = " ".join([
        _first(row, ("injury_status", "status", "player_status")),
        _first(row, ("injury_notes", "injury_note", "notes", "news")),
    ])
    lineup_text = " ".join([
        _first(row, ("lineup_status", "lineup_confirmed", "starter_status")),
        _first(row, ("depth_chart_status", "expected_lineup")),
    ])
    key_player = _is_key_player(row)
    score = 100.0
    warning: list[str] = []
    do_not_bet: list[str] = []

    if _contains_any(status_text, OUT_LABELS):
        score -= 45 if key_player else 25
        warning.append("player out/scratched")
        if key_player:
            do_not_bet.append("key_player_out")
    elif _contains_any(status_text, QUESTIONABLE_LABELS):
        score -= 22 if key_player else 10
        warning.append("player questionable/limited")
        if key_player:
            do_not_bet.append("key_player_not_confirmed")

    if _contains_any(lineup_text, CONFIRMED_LABELS):
        confirmed = "true"
    elif _contains_any(lineup_text, UNCONFIRMED_LABELS) or not lineup_text.strip():
        confirmed = "false"
        score -= 12
        warning.append("lineup not confirmed")
    else:
        confirmed = "unknown"
        score -= 8
        warning.append("lineup status unclear")

    score = round(max(0.0, min(100.0, score)), 2)
    return InjuryLineupRisk(
        injury_risk_score=score,
        lineup_confirmed=confirmed,
        key_player_out="true" if "key_player_out" in do_not_bet else "false",
        injury_warning="; ".join(warning) or "no major injury/lineup warning",
        lineup_do_not_bet_reason="; ".join(do_not_bet),
    )


def enrich_rows_with_injury_lineup(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        risk = score_injury_lineup(row)
        enriched = dict(row)
        enriched.update({
            "injury_risk_score": str(risk.injury_risk_score),
            "lineup_confirmed": risk.lineup_confirmed,
            "key_player_out": risk.key_player_out,
            "injury_warning": risk.injury_warning,
            "lineup_do_not_bet_reason": risk.lineup_do_not_bet_reason,
        })
        output.append(enriched)
    return output
