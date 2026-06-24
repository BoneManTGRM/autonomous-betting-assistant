"""Merge optional API-Football, Perplexity, and NewsAPI context.

External context is a support layer only. It can weaken or flag picks, but it
must not create a BET by itself or override bad EV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .api_football_client import fetch_api_football_fixture_statistics
from .api_config import has_api_football, has_newsapi, has_perplexity
from .news_context import fetch_recent_match_news
from .perplexity_research import research_match_context

MAJOR_FLAG_TERMS = ("injury", "suspension", "out", "doubtful", "lineup", "contradiction")


@dataclass(frozen=True)
class ExternalContext:
    sources_used: tuple[str, ...] = field(default_factory=tuple)
    research_summary: str = ""
    news_summary: str = ""
    soccer_stats_summary: str = ""
    injury_flags: tuple[str, ...] = field(default_factory=tuple)
    lineup_flags: tuple[str, ...] = field(default_factory=tuple)
    travel_flags: tuple[str, ...] = field(default_factory=tuple)
    weather_flags: tuple[str, ...] = field(default_factory=tuple)
    motivation_flags: tuple[str, ...] = field(default_factory=tuple)
    public_sentiment_flags: tuple[str, ...] = field(default_factory=tuple)
    confidence_adjustment: float = 0.0
    risk_adjustment: float = 0.0
    no_bet_flags: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    context_effect: str = "neutral"

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _flatten(*values: Any) -> tuple[str, ...]:
    output: list[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            output.append(value)
        elif isinstance(value, (list, tuple, set)):
            output.extend(str(item) for item in value if item)
    return tuple(dict.fromkeys(output))


def _stats_summary(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    parts = []
    for row in rows[:2]:
        team = row.get("team") or "team"
        possession = row.get("possession_edge")
        shots = row.get("shots_edge")
        corners = row.get("corner_edge")
        cards = row.get("card_edge")
        parts.append(f"{team}: possession={possession}, shots={shots}, corners={corners}, cards={cards}")
    return "; ".join(parts)


def collect_external_context(row: Mapping[str, Any], enable_api_football: bool = True, enable_perplexity: bool = True, enable_newsapi: bool = True) -> ExternalContext:
    fixture_id = row.get("fixture_id")
    game = _text(row, "game", "event", "event_name", "matchup")
    league = _text(row, "league", "sport_league", "sport")
    teams = [team for team in (_text(row, "home_team"), _text(row, "away_team")) if team]

    api_context: dict[str, Any] = {"rows": [], "warnings": []}
    research_context: dict[str, Any] = {}
    news_context: dict[str, Any] = {}

    if enable_api_football and has_api_football() and fixture_id:
        api_context = fetch_api_football_fixture_statistics(fixture_id)
    elif enable_api_football and not has_api_football():
        api_context = {"rows": [], "warnings": ["API-Football missing key or fixture_id; local context only."]}

    if enable_perplexity and has_perplexity() and game:
        research_context = research_match_context(game, league=league, teams=teams)
    elif enable_perplexity and not has_perplexity():
        research_context = {"warnings": ["Perplexity missing key; research context skipped."]}

    if enable_newsapi and has_newsapi() and game:
        news_context = fetch_recent_match_news(game, teams=teams)
    elif enable_newsapi and not has_newsapi():
        news_context = {"warnings": ["NewsAPI missing key; recent news skipped."]}

    return merge_context_signals(api_context, research_context, news_context)


def merge_context_signals(api_football_context: Mapping[str, Any] | None, perplexity_context: Mapping[str, Any] | None, news_context: Mapping[str, Any] | None) -> ExternalContext:
    api = api_football_context or {}
    research = perplexity_context or {}
    news = news_context or {}
    sources = []
    if api.get("rows"):
        sources.append("api-football")
    if research.get("research_summary"):
        sources.append("perplexity")
    if news.get("news_summary"):
        sources.append("newsapi")

    injury = _flatten(research.get("injury_flags"), news.get("injury_news"), news.get("suspension_news"))
    lineup = _flatten(research.get("lineup_flags"), news.get("lineup_news"))
    travel = _flatten(research.get("travel_flags"), news.get("travel_news"))
    weather = _flatten(research.get("weather_flags"), news.get("weather_news"))
    motivation = _flatten(research.get("motivation_flags"), news.get("motivation_news"))
    public = _flatten(research.get("public_sentiment_flags"))
    warnings = _flatten(api.get("warnings"), research.get("warnings"), news.get("warnings"))
    no_bet = tuple(flag for flag in injury + lineup if any(term in flag.lower() for term in MAJOR_FLAG_TERMS))
    confidence = float(research.get("confidence_adjustment") or 0.0) + float(news.get("confidence_adjustment") or 0.0)
    risk = min(2.0, len(no_bet) * 0.6 + len(weather) * 0.2 + len(travel) * 0.2)
    if no_bet:
        effect = "weakened"
    elif sources and confidence > 0:
        effect = "strengthened"
    else:
        effect = "neutral"
    return ExternalContext(
        sources_used=tuple(sources),
        research_summary=str(research.get("research_summary") or ""),
        news_summary=str(news.get("news_summary") or ""),
        soccer_stats_summary=_stats_summary(api.get("rows", [])),
        injury_flags=injury,
        lineup_flags=lineup,
        travel_flags=travel,
        weather_flags=weather,
        motivation_flags=motivation,
        public_sentiment_flags=public,
        confidence_adjustment=round(max(-0.12, min(0.05, confidence)), 3),
        risk_adjustment=round(risk, 2),
        no_bet_flags=no_bet,
        warnings=warnings,
        context_effect=effect,
    )


def context_confidence_adjustment(context: ExternalContext | Mapping[str, Any] | None) -> float:
    if context is None:
        return 0.0
    return float(context.confidence_adjustment if isinstance(context, ExternalContext) else context.get("confidence_adjustment", 0.0) or 0.0)


def context_risk_adjustment(context: ExternalContext | Mapping[str, Any] | None) -> float:
    if context is None:
        return 0.0
    return float(context.risk_adjustment if isinstance(context, ExternalContext) else context.get("risk_adjustment", 0.0) or 0.0)


def context_no_bet_flags(context: ExternalContext | Mapping[str, Any] | None) -> tuple[str, ...]:
    if context is None:
        return tuple()
    value = context.no_bet_flags if isinstance(context, ExternalContext) else context.get("no_bet_flags", tuple())
    return tuple(value or tuple())


def apply_context_to_pick(row: Mapping[str, Any], context: ExternalContext | Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    ctx = context if isinstance(context, ExternalContext) else ExternalContext(**{k: v for k, v in context.items() if k in ExternalContext.__dataclass_fields__})
    current_probability = data.get("model_probability") or data.get("probability")
    try:
        if current_probability is not None:
            probability = float(current_probability)
            if probability > 1:
                probability /= 100
            data["model_probability"] = max(0.0, min(1.0, probability + ctx.confidence_adjustment))
    except (TypeError, ValueError):
        pass
    try:
        risk = float(data.get("risk_score") or data.get("blended_risk_score") or 0)
        if risk:
            data["risk_score"] = max(1.0, min(10.0, risk + ctx.risk_adjustment))
    except (TypeError, ValueError):
        pass
    data["external_context"] = ctx.as_dict()
    data["context_effect"] = ctx.context_effect
    if ctx.no_bet_flags:
        data["context_warning"] = "; ".join(ctx.no_bet_flags[:3])
        if str(data.get("final_decision", "")).upper() in {"BET", "SMALL BET", ""}:
            data["final_decision"] = "WATCH ONLY"
    return data


def format_external_context_for_card(context: ExternalContext | Mapping[str, Any] | None) -> str:
    if not context:
        return ""
    ctx = context if isinstance(context, ExternalContext) else ExternalContext(**{k: v for k, v in context.items() if k in ExternalContext.__dataclass_fields__})
    lines = ["External Context:"]
    lines.append(f"- Sources used: {', '.join(ctx.sources_used) if ctx.sources_used else 'local CSV only'}")
    if ctx.soccer_stats_summary:
        lines.append(f"- Soccer stats support: {ctx.soccer_stats_summary}")
    if ctx.research_summary:
        lines.append(f"- Research notes: {ctx.research_summary}")
    if ctx.news_summary:
        lines.append(f"- Recent news: {ctx.news_summary}")
    if ctx.injury_flags or ctx.lineup_flags:
        lines.append(f"- Injury / lineup flags: {'; '.join((ctx.injury_flags + ctx.lineup_flags)[:3])}")
    lines.append(f"- Risk adjustment: {ctx.risk_adjustment:+.2f}")
    lines.append(f"- Confidence adjustment: {ctx.confidence_adjustment:+.3f}")
    if ctx.no_bet_flags:
        lines.append(f"- Context warning: {'; '.join(ctx.no_bet_flags[:3])}")
    lines.append(f"- Context effect: {ctx.context_effect}")
    return "\n".join(lines)


def format_external_context_for_magazine(context: ExternalContext | Mapping[str, Any] | None) -> str:
    return format_external_context_for_card(context)
