"""Daily chain betting report helpers.

This module builds subscriber-facing daily chain summaries and optional
single-game deep dives from already-supplied rows. It does not fetch live data,
place bets, expose API keys, or guarantee outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping, Sequence


def _text(row: Mapping[str, Any] | None, *keys: str, default: str = "") -> str:
    if not row:
        return default
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _num(row: Mapping[str, Any] | None, *keys: str, default: float | None = None) -> float | None:
    if not row:
        return default
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _prob(row: Mapping[str, Any] | None, *keys: str, default: float | None = None) -> float | None:
    value = _num(row, *keys, default=default)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.0%}"


def _fmt_edge(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.1%}"


def _compact(text: str, max_words: int = 11) -> str:
    words = str(text).replace("\n", " ").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(",.;") + "..."


def _split_bullets(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_compact(part.strip(" -•\t"), 11) for part in normalized.split("\n") if part.strip(" -•\t")]


def _add_unique(items: list[str], text: str, max_words: int = 11) -> None:
    text = _compact(text, max_words)
    if text and text not in items:
        items.append(text)


def _game(row: Mapping[str, Any]) -> str:
    return _text(row, "game", "event", "event_name", "matchup", default="Unknown Game")


def _exact_bet(row: Mapping[str, Any]) -> str:
    return _text(row, "exact_bet", "pick", "selection", "prediction", "bet", default="Bet not specified")


def _is_chain_row(row: Mapping[str, Any]) -> bool:
    text = " ".join(_text(row, key).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))
    return bool(row.get("legs")) or any(marker in text for marker in ("chain", "parlay", "same game parlay", "sgp"))


def _is_filler(row: Mapping[str, Any]) -> bool:
    text = " ".join(_text(row, key).lower() for key in ("leg_name", "exact_bet", "pick", "selection", "market", "reason", "why_pick", "filler_leg_risk"))
    value = _text(row, "was_filler_leg", "filler_leg").lower()
    return value in {"true", "yes", "1", "high"} or "filler" in text or "payout chase" in text or "random" in text


def _risk_label(score: float | None) -> str:
    if score is None:
        return "Unknown"
    if score <= 3:
        return "Low"
    if score <= 6:
        return "Medium"
    if score <= 8:
        return "High"
    return "Very High"


def _profile_value(profile: Any, key: str, default: str = "") -> str:
    if profile is None:
        return default
    if isinstance(profile, Mapping):
        return str(profile.get(key) or default)
    return str(getattr(profile, key, default) or default)


def sanitize_report_filename(title: str, extension: str = "md") -> str:
    """Return a safe lowercase download filename from an editable report title."""
    clean = re.sub(r"[^A-Za-z0-9]+", "_", (title or "report").strip().lower()).strip("_")
    if not clean:
        clean = "report"
    ext = (extension or "md").strip().lstrip(".") or "md"
    return f"{clean}.{ext}"


@dataclass(frozen=True)
class DailyChainCandidate:
    game: str
    sport_league: str
    start_time: str
    sportsbook: str
    main_read: str
    chain: str
    add_on_legs: tuple[str, ...] = field(default_factory=tuple)
    optional_legs: tuple[str, ...] = field(default_factory=tuple)
    rejected_legs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float | None = None
    edge: float | None = None
    risk_score: float | None = None
    risk_level: str = "Unknown"
    recommended_units: str = "0.25-0.50"
    filler_leg_risk: str = "Unknown"
    correlation: str = "Unknown"
    straight_bet_alternative: str = "None supplied"
    better_as_straight: bool = False
    deep_dive_available: bool = False
    daily_chain_score: float = 0.0
    why_bullets: tuple[str, ...] = field(default_factory=tuple)
    risk_bullets: tuple[str, ...] = field(default_factory=tuple)
    learning_warnings: tuple[str, ...] = field(default_factory=tuple)
    source_rows: tuple[Mapping[str, Any], ...] = field(default_factory=tuple, repr=False)
    approved: bool = True

    def as_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("source_rows", None)
        return data


@dataclass(frozen=True)
class DailyChainReport:
    generated_at: str
    subscriber: str
    risk_profile: str
    candidates: tuple[DailyChainCandidate, ...]
    approved_chains: tuple[DailyChainCandidate, ...]
    rejected_chains: tuple[DailyChainCandidate, ...]
    best_chain: DailyChainCandidate | None = None
    best_single_game: DailyChainCandidate | None = None
    learning_warnings: tuple[str, ...] = field(default_factory=tuple)
    key_alerts: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "subscriber": self.subscriber,
            "risk_profile": self.risk_profile,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "approved_chains": [candidate.as_dict() for candidate in self.approved_chains],
            "rejected_chains": [candidate.as_dict() for candidate in self.rejected_chains],
            "best_chain": None if self.best_chain is None else self.best_chain.as_dict(),
            "best_single_game": None if self.best_single_game is None else self.best_single_game.as_dict(),
            "learning_warnings": list(self.learning_warnings),
            "key_alerts": list(self.key_alerts),
        }


@dataclass(frozen=True)
class SingleGameChainMagazine:
    game: str
    sport_league: str
    start_time: str
    sportsbook: str
    risk_profile: str
    best_candidate: DailyChainCandidate | None
    rows: tuple[Mapping[str, Any], ...] = field(default_factory=tuple, repr=False)
    professional_evidence: tuple[str, ...] = field(default_factory=tuple)
    learning_warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "sport_league": self.sport_league,
            "start_time": self.start_time,
            "sportsbook": self.sportsbook,
            "risk_profile": self.risk_profile,
            "best_candidate": None if self.best_candidate is None else self.best_candidate.as_dict(),
            "professional_evidence": list(self.professional_evidence),
            "learning_warnings": list(self.learning_warnings),
        }


def _candidate_from_chain_row(row: Mapping[str, Any], learning_warnings: tuple[str, ...]) -> DailyChainCandidate:
    legs_value = row.get("legs")
    legs: list[str] = []
    if isinstance(legs_value, Sequence) and not isinstance(legs_value, (str, bytes)):
        for leg in legs_value:
            if isinstance(leg, Mapping):
                legs.append(_exact_bet(leg))
            elif str(leg).strip():
                legs.append(str(leg).strip())
    if not legs:
        supplied = _text(row, "chain", "chain_bet", "exact_bet", "pick", "selection")
        legs = [part.strip() for part in re.split(r"\s*\+\s*|,", supplied) if part.strip()]
    main_read = _text(row, "main_read", "primary_leg", default=legs[0] if legs else _exact_bet(row))
    add_ons = tuple(leg for leg in legs if leg != main_read)[:3]
    return _build_candidate(row, (row,), main_read=main_read, add_ons=add_ons, learning_warnings=learning_warnings)


def _candidate_from_game_rows(game_rows: Sequence[Mapping[str, Any]], learning_warnings: tuple[str, ...]) -> DailyChainCandidate:
    sorted_rows = sorted(game_rows, key=lambda row: (_prob(row, "model_probability", "projected_probability", default=0) or 0, _num(row, "edge", "expected_value", "ev", default=0) or 0), reverse=True)
    main = sorted_rows[0]
    add_ons = tuple(_exact_bet(row) for row in sorted_rows[1:4])
    return _build_candidate(main, tuple(sorted_rows), main_read=_text(main, "main_read", "primary_leg", default=_exact_bet(main)), add_ons=add_ons, learning_warnings=learning_warnings)


def _build_candidate(row: Mapping[str, Any], source_rows: Sequence[Mapping[str, Any]], main_read: str, add_ons: Sequence[str], learning_warnings: tuple[str, ...]) -> DailyChainCandidate:
    confidence = _prob(row, "combined_adjusted_probability", "chain_probability", "model_probability", "confidence", "confidence_score")
    edge = _num(row, "edge", "expected_value", "ev", default=0.0)
    if edge is not None and abs(edge) > 1:
        edge /= 100.0
    risk_score = _num(row, "risk_score", "blended_risk_score", default=None)
    if risk_score is None and confidence is not None:
        risk_score = round(max(1.0, min(10.0, 10 - confidence * 10 + len(add_ons) * 0.6)), 1)
    filler_risk = _text(row, "filler_leg_risk", default="High" if any(_is_filler(item) for item in source_rows) else "Low")
    correlation = _text(row, "correlation_label", "correlation", default="Positive" if add_ons else "Unknown")
    straight_alt = _text(row, "straight_bet_alternative", "straight_bet_comparison", default=main_read)
    better_text = _text(row, "better_straight_or_chain", "straight_bet_comparison").lower()
    better_as_straight = "straight" in better_text and "chain" not in better_text[:20]
    if filler_risk.lower() == "high":
        better_as_straight = True
    score = _score_daily_chain(row, confidence, edge, risk_score, filler_risk, correlation, source_rows)
    approved = score >= 35 and filler_risk.lower() not in {"very high", "reject"}
    chain = _text(row, "chain", "chain_bet") or " + ".join([main_read, *add_ons])
    why = _why_bullets(row, source_rows, confidence, edge, correlation)
    risks = _risk_bullets(row, filler_risk, risk_score, better_as_straight)
    return DailyChainCandidate(
        game=_game(row),
        sport_league=_text(row, "sport_league", "league", "sport", default="Unknown League"),
        start_time=_text(row, "start_time", "commence_time", "event_time", default="Not specified"),
        sportsbook=_text(row, "sportsbook", "sportsbook_casino", "best_bookmaker", "bookmaker", default="Best available"),
        main_read=main_read,
        chain=chain,
        add_on_legs=tuple(add_ons),
        optional_legs=tuple(_split_bullets(_text(row, "optional_legs")))[:3],
        rejected_legs=tuple(_split_bullets(_text(row, "rejected_legs")))[:3],
        confidence=confidence,
        edge=edge,
        risk_score=risk_score,
        risk_level=_risk_label(risk_score),
        recommended_units=_text(row, "recommended_units", "recommended_stake", "stake", default="0.25-0.50"),
        filler_leg_risk=filler_risk,
        correlation=correlation,
        straight_bet_alternative=straight_alt,
        better_as_straight=better_as_straight,
        deep_dive_available=len(source_rows) >= 2 or bool(add_ons),
        daily_chain_score=round(score, 2),
        why_bullets=why,
        risk_bullets=risks,
        learning_warnings=learning_warnings,
        source_rows=tuple(source_rows),
        approved=approved,
    )


def _score_daily_chain(row: Mapping[str, Any], confidence: float | None, edge: float | None, risk_score: float | None, filler_risk: str, correlation: str, rows: Sequence[Mapping[str, Any]]) -> float:
    main_read_score = (_num(row, "main_read_score", default=None) or ((confidence or 0.45) * 35))
    add_on_quality = _num(row, "add_on_quality_score", default=min(18.0, max(0.0, (len(rows) - 1) * 7.0))) or 0.0
    corr_supplied = _num(row, "correlation_score", default=None)
    if corr_supplied is None:
        corr_supplied = 16.0 if correlation.lower() in {"positive", "strong", "high"} else 6.0 if correlation.lower() in {"weak", "negative"} else 10.0
    market_value = _num(row, "market_value_score", default=max(0.0, min(15.0, (edge or 0.0) * 180))) or 0.0
    injury = 8.0 if any(_text(item, "injury_report", "injury_edge", "player_injuries") for item in rows) else 3.0
    lineup = 8.0 if any(_text(item, "lineup_status", "starting_lineups", "lineup_confirmation") for item in rows) else 3.0
    weather = 6.0 if any(_text(item, "weather_impact", "wind_speed", "wind_direction") for item in rows) else 3.0
    filler_penalty = 18.0 if filler_risk.lower() == "high" else 8.0 if filler_risk.lower() == "medium" else 0.0
    risk_penalty = risk_score or 5.0
    return main_read_score + add_on_quality + corr_supplied + market_value + injury + lineup + weather - filler_penalty - risk_penalty


def _why_bullets(row: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], confidence: float | None, edge: float | None, correlation: str) -> tuple[str, ...]:
    bullets: list[str] = []
    supplied = _text(row, "why_bullets", "why_we_picked_it", "pro_edge_reasons", "professional_evidence", "why_pick")
    if supplied:
        bullets.extend(_split_bullets(supplied))
    if confidence is not None:
        _add_unique(bullets, f"Chain confidence {_fmt_pct(confidence)}")
    if edge is not None:
        _add_unique(bullets, f"Market edge {_fmt_edge(edge)}")
    _add_unique(bullets, f"Correlation graded {correlation}")
    for keys, label in (
        (("injury_report", "injury_edge", "player_injuries"), "Injury"),
        (("lineup_status", "starting_lineups", "lineup_confirmation"), "Lineup"),
        (("weather_impact", "wind_speed", "wind_direction"), "Weather"),
        (("market_movement", "line_movement", "sharp_money_signal"), "Market"),
        (("bullpen_fatigue", "bullpen_usage_last_3_days"), "Bullpen"),
        (("pitcher_handedness", "left_right_split", "pitcher_vs_batter_handedness"), "L/R split"),
        (("news_signal", "news_sentiment", "beat_writer_update"), "News"),
        (("travel_fatigue", "rest_advantage", "back_to_back"), "Fatigue"),
    ):
        value = next((_text(item, *keys) for item in rows if _text(item, *keys)), "")
        if value:
            _add_unique(bullets, f"{label}: {value}")
    return tuple(bullets[:5])


def _risk_bullets(row: Mapping[str, Any], filler_risk: str, risk_score: float | None, better_as_straight: bool) -> tuple[str, ...]:
    risks: list[str] = []
    supplied = _text(row, "risk_bullets", "risk_reason", "why_lose", "hidden_risk")
    if supplied:
        risks.extend(_split_bullets(supplied))
    if filler_risk.lower() in {"medium", "high", "very high"}:
        _add_unique(risks, f"Filler leg risk {filler_risk}")
    if better_as_straight:
        _add_unique(risks, "Straight bet may be safer")
    if risk_score is not None and risk_score > 6:
        _add_unique(risks, "Use smaller stake due to risk")
    invalidation = _text(row, "avoid_if", "no_bet_if", "invalidation_condition")
    if invalidation:
        _add_unique(risks, f"Avoid if {invalidation}")
    else:
        _add_unique(risks, "Avoid if lineup or injury news changes")
    return tuple(risks[:4])


def _learning_warnings(learning_memory: Any) -> tuple[str, ...]:
    if not learning_memory:
        return ("No chain learning memory yet. Grade completed chains to improve future reports.",)
    warnings: list[str] = []
    if isinstance(learning_memory, Mapping):
        if learning_memory.get("bad_filler_leg_patterns") or learning_memory.get("target_payout_chase_patterns"):
            warnings.append("Similar filler or target-payout legs failed before.")
        if learning_memory.get("straight_bet_better_patterns"):
            warnings.append("Straight bet has beaten similar chains before.")
        if learning_memory.get("leg_failure_patterns"):
            warnings.append("Review historical failed-leg patterns before chaining.")
    return tuple(warnings or ["Chain learning memory loaded; no major warnings found."])


def _key_alerts(candidates: Sequence[DailyChainCandidate]) -> tuple[str, ...]:
    alerts: list[str] = []
    for candidate in candidates:
        if candidate.filler_leg_risk.lower() in {"medium", "high", "very high"}:
            _add_unique(alerts, f"{candidate.game}: filler risk {candidate.filler_leg_risk}", 12)
        if any("injury" in risk.lower() for risk in candidate.risk_bullets):
            _add_unique(alerts, f"{candidate.game}: injury/news must be rechecked", 12)
    return tuple(alerts[:5])


def build_daily_chain_report(rows: Iterable[Mapping[str, Any]], client_profile: Any = None, max_cards: int = 5, learning_memory: Any = None) -> DailyChainReport:
    row_list = [row for row in rows if isinstance(row, Mapping)]
    warnings = _learning_warnings(learning_memory)
    candidates: list[DailyChainCandidate] = []
    used_games: set[str] = set()
    for row in row_list:
        if _is_chain_row(row):
            candidate = _candidate_from_chain_row(row, warnings)
            candidates.append(candidate)
            used_games.add(candidate.game)
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in row_list:
        grouped.setdefault(_game(row), []).append(row)
    for game, game_rows in grouped.items():
        if game in used_games or len(game_rows) < 2:
            continue
        candidates.append(_candidate_from_game_rows(game_rows, warnings))
    candidates.sort(key=lambda candidate: candidate.daily_chain_score, reverse=True)
    limited = tuple(candidates[:max(1, int(max_cards or 5))])
    approved = tuple(candidate for candidate in limited if candidate.approved)
    rejected = tuple(candidate for candidate in limited if not candidate.approved)
    best = approved[0] if approved else None
    return DailyChainReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        subscriber=_profile_value(client_profile, "name", "Default Client"),
        risk_profile=_profile_value(client_profile, "risk_profile", "balanced"),
        candidates=limited,
        approved_chains=approved,
        rejected_chains=rejected,
        best_chain=best,
        best_single_game=best,
        learning_warnings=warnings,
        key_alerts=_key_alerts(limited),
    )


def _render_candidate_card(candidate: DailyChainCandidate, index: int = 1) -> str:
    lines = [
        f"### {index}. {candidate.game}",
        "**MAIN READ:**",
        candidate.main_read,
        "",
        "**CHAIN:**",
        candidate.chain,
        "",
        f"Confidence: {_fmt_pct(candidate.confidence)}",
        f"Edge: {_fmt_edge(candidate.edge)}",
        f"Risk: {candidate.risk_level}",
        f"Filler Risk: {candidate.filler_leg_risk}",
        f"Correlation: {candidate.correlation}",
        f"Units: {candidate.recommended_units}",
        f"Deep Dive Available: {'Yes' if candidate.deep_dive_available else 'No'}",
        f"Better As Straight: {'Yes' if candidate.better_as_straight else 'No'}",
        "",
        "**Why It Works:**",
    ]
    lines.extend(f"- {bullet}" for bullet in candidate.why_bullets)
    lines += ["", "**Risk:**"]
    lines.extend(f"- {risk}" for risk in candidate.risk_bullets)
    lines += ["", f"**Magazine Summary:** Best one-game chain candidate today. {'Straight bet is safer.' if candidate.better_as_straight else 'Chain acceptable at small stake if data confirms.'}"]
    return "\n".join(lines)


def render_daily_chain_summary_card(report: DailyChainReport, title: str = "ABA Signal Pro — Daily Chain Summary") -> str:
    best = report.best_chain
    lines = [f"# {title}", ""]
    if best is None:
        lines += ["NO CHAIN RECOMMENDED TODAY", "Straight bet or watch-only report available."]
        return "\n".join(lines).strip() + "\n"
    lines += [
        "Daily Summary:",
        f"• Best Chain: {best.chain}",
        f"• Best Game: {best.game}",
        f"• Chain Confidence: {_fmt_pct(best.confidence)}",
        f"• Risk: {best.risk_level}",
        f"• Filler Risk: {best.filler_leg_risk}",
        f"• Straight Alternative: {best.straight_bet_alternative}",
        "• Report Mode: One-game deep dive recommended" if best.deep_dive_available else "• Report Mode: Summary only",
    ]
    return "\n".join(lines).strip() + "\n"


def render_daily_chain_report(report: DailyChainReport, title: str = "ABA Signal Pro — Daily Chain Report") -> str:
    lines = [
        f"# {title}",
        "",
        f"Date: {report.generated_at[:10]}",
        f"Subscriber: {report.subscriber}",
        f"Risk Profile: {report.risk_profile}",
        f"Generated: {report.generated_at}",
        "",
        "## Daily Summary",
        "",
    ]
    if report.best_chain is None:
        lines += ["NO CHAIN RECOMMENDED TODAY", "Straight bet or watch-only report available.", ""]
    else:
        best = report.best_chain
        lines += [
            f"• Best Chain: {best.chain}",
            f"• Best Game: {best.game}",
            f"• Chain Confidence: {_fmt_pct(best.confidence)}",
            f"• Risk: {best.risk_level}",
            f"• Filler Risk: {best.filler_leg_risk}",
            f"• Straight Alternative: {best.straight_bet_alternative}",
            f"• Approved Chains: {len(report.approved_chains)}",
            f"• Rejected Chains: {len(report.rejected_chains)}",
            "• Report Mode: One-game deep dive recommended" if best.deep_dive_available else "• Report Mode: Summary only",
            "",
        ]
    if report.key_alerts:
        lines += ["## Key Alerts", ""] + [f"• {alert}" for alert in report.key_alerts] + [""]
    lines += ["## Learning Warnings", ""] + [f"• {warning}" for warning in report.learning_warnings] + [""]
    lines += ["## Compact Chain Cards", ""]
    if not report.candidates:
        lines += ["NO CHAIN RECOMMENDED TODAY", ""]
    for index, candidate in enumerate(report.candidates, start=1):
        lines.append(_render_candidate_card(candidate, index))
        lines.append("")
    lines += [
        "## Safety Notice",
        "",
        "Analytics and decision support only. No bet execution, no guaranteed wins, and no guaranteed profit.",
    ]
    return "\n".join(lines).strip() + "\n"


def _professional_evidence(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    evidence: list[str] = []
    for keys, label in (
        (("injury_report", "injury_edge", "player_injuries"), "Injuries"),
        (("lineup_status", "starting_lineups", "lineup_confirmation"), "Starting lineup"),
        (("pitcher_handedness", "left_right_split", "pitcher_vs_batter_handedness"), "Pitcher/batter handedness"),
        (("bullpen_fatigue", "bullpen_usage_last_3_days"), "Bullpen fatigue"),
        (("weather_impact", "wind_speed", "wind_direction"), "Weather/wind"),
        (("market_movement", "line_movement", "sharp_money_signal"), "Market movement"),
        (("sportsbook_discrepancy", "line_shopping_edge", "best_price_edge"), "Sportsbook price gap"),
        (("news_signal", "news_sentiment", "beat_writer_update"), "News confirmation"),
        (("travel_fatigue", "rest_advantage", "back_to_back"), "Travel/fatigue"),
        (("motivation", "table_motivation", "playoff_pressure"), "Motivation"),
        (("referee_tendency", "umpire_tendency", "umpire_zone"), "Ref/umpire tendency"),
    ):
        value = next((_text(row, *keys) for row in rows if _text(row, *keys)), "")
        if value:
            _add_unique(evidence, f"{label}: {value}", 14)
    return tuple(evidence[:12])


def build_single_game_chain_magazine(game_rows: Iterable[Mapping[str, Any]], client_profile: Any = None, learning_memory: Any = None) -> SingleGameChainMagazine:
    rows = tuple(row for row in game_rows if isinstance(row, Mapping))
    if not rows:
        return SingleGameChainMagazine("Unknown Game", "Unknown League", "Not specified", "Best available", _profile_value(client_profile, "risk_profile", "balanced"), None)
    report = build_daily_chain_report(rows, client_profile=client_profile, max_cards=1, learning_memory=learning_memory)
    best = report.best_chain or (report.candidates[0] if report.candidates else None)
    first = rows[0]
    return SingleGameChainMagazine(
        game=_game(first),
        sport_league=_text(first, "sport_league", "league", "sport", default="Unknown League"),
        start_time=_text(first, "start_time", "commence_time", "event_time", default="Not specified"),
        sportsbook=_text(first, "sportsbook", "sportsbook_casino", "best_bookmaker", "bookmaker", default="Best available"),
        risk_profile=_profile_value(client_profile, "risk_profile", "balanced"),
        best_candidate=best,
        rows=rows,
        professional_evidence=_professional_evidence(rows),
        learning_warnings=report.learning_warnings,
    )


def render_single_game_chain_magazine(game_report: SingleGameChainMagazine, title: str = "ABA Signal Pro — Single Game Chain Report") -> str:
    candidate = game_report.best_candidate
    lines = [
        f"# {title}",
        "",
        f"Game: {game_report.game}",
        f"League: {game_report.sport_league}",
        f"Start Time: {game_report.start_time}",
        f"Sportsbook: {game_report.sportsbook}",
        f"Risk Profile: {game_report.risk_profile}",
        "",
        "## Executive Summary",
        "",
    ]
    if candidate is None:
        lines += [
            "• Best Play: Watch only",
            "• Best Chain: NO ONE-GAME CHAIN RECOMMENDED TODAY",
            "• Best Straight Alternative: Straight bet or watch-only report available",
            "• Confidence: N/A",
            "• Risk: Unknown",
            "• Playable Line: N/A",
            "• Pass/No Pass: NO CHAIN RECOMMENDED",
            "",
            "Final Recommendation: NO CHAIN RECOMMENDED",
        ]
        return "\n".join(lines).strip() + "\n"
    lines += [
        f"• Best Play: {candidate.main_read}",
        f"• Best Chain: {candidate.chain}",
        f"• Best Straight Alternative: {candidate.straight_bet_alternative}",
        f"• Confidence: {_fmt_pct(candidate.confidence)}",
        f"• Risk: {candidate.risk_level}",
        "• Playable Line: Use uploaded playable threshold or recheck market",
        f"• Pass/No Pass: {'PASS' if candidate.approved else 'WATCH ONLY'}",
        "",
        "## Main Read",
        "",
        f"{candidate.main_read} is the core read. The chain should only be considered if this main read remains playable.",
        "",
        "## Chain Build",
        "",
        f"- Leg 1 — Main Read: {candidate.main_read}",
    ]
    for index, leg in enumerate(candidate.add_on_legs, start=2):
        lines.append(f"- Leg {index} — Add-On: {leg}")
    if candidate.optional_legs:
        lines += ["- Optional Legs: " + ", ".join(candidate.optional_legs)]
    if candidate.rejected_legs:
        lines += ["- Rejected Legs: " + ", ".join(candidate.rejected_legs)]
    lines += ["", "## Why These Legs Belong", ""]
    lines.extend(f"• {bullet}" for bullet in candidate.why_bullets)
    lines += ["", "## Professional Evidence", ""]
    if game_report.professional_evidence:
        lines.extend(f"• {item}" for item in game_report.professional_evidence)
    else:
        lines.append("• Professional evidence pending from uploaded data.")
    lines += ["", "## Straight vs Chain Decision", ""]
    if candidate.better_as_straight:
        lines.append("Straight bet is safer. Chain should be small-stake or watch-only unless add-ons confirm.")
    else:
        lines.append("Chain is acceptable at small stake because the add-ons support the same game script.")
    lines += ["", "## Risk Desk", ""]
    lines.extend(f"• {risk}" for risk in candidate.risk_bullets)
    lines += ["", "## Learning Warnings", ""]
    lines.extend(f"• {warning}" for warning in game_report.learning_warnings)
    lines += ["", f"Final Recommendation: {'SMALL BET' if candidate.approved else 'WATCH ONLY'}"]
    return "\n".join(lines).strip() + "\n"


def daily_chain_report_to_rows(report: DailyChainReport) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [{
        "row_type": "metadata",
        "generated_at": report.generated_at,
        "subscriber": report.subscriber,
        "risk_profile": report.risk_profile,
        "approved_chains": len(report.approved_chains),
        "rejected_chains": len(report.rejected_chains),
    }]
    for index, candidate in enumerate(report.candidates, start=1):
        row = candidate.as_dict()
        row["row_type"] = "chain_candidate"
        row["rank"] = index
        row["why_bullets"] = " | ".join(candidate.why_bullets)
        row["risk_bullets"] = " | ".join(candidate.risk_bullets)
        row["learning_warnings"] = " | ".join(candidate.learning_warnings)
        rows.append(row)
    return rows
