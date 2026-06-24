"""Subscriber-ready bet catalog and betting magazine helpers.

The helpers rank already-supplied analysis and odds rows. They do not fetch odds,
place bets, guarantee winners, or claim a guaranteed 65% actual win rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

CORE_PROBABILITY_THRESHOLD = 0.65
DOUBLE_MONEY_DECIMAL = 2.0
MOBILE_PICK_LIMIT = 3
FINAL_DECISIONS = {
    "BET", "SMALL BET", "CHAIN ONLY", "WAIT FOR BETTER ODDS", "WATCH ONLY",
    "NO BET", "GOOD READ, BAD PRICE", "BAD VALUE", "AGGRESSIVE ONLY",
}
CATALOG_SECTIONS = (
    "Best 65%+ Singles", "Best Good-Odds Bets", "Closest Double-Money Bets",
    "Conservative Baseball Chains", "Balanced Baseball Chains", "Aggressive Baseball Chains",
    "Player Prop Catalog", "Home Run Watchlist", "Good Read / Bad Price", "No-Bet List",
)
_CHAIN_MARKERS = {"chain", "parlay", "same game parlay", "sgp"}
_PROP_MARKERS = {"player", "prop", "hits", "total bases", "rbi", "runs", "strikeouts", "outs"}
_HR_MARKERS = {"home run", "hr", "homer"}


def _text(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _num(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _prob(row: Mapping[str, Any], *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def american_to_decimal(american_odds: float) -> float | None:
    if american_odds == 0:
        return None
    return 1 + american_odds / 100 if american_odds > 0 else 1 + 100 / abs(american_odds)


def decimal_to_american(decimal_odds: float | None) -> int | None:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return int(round((decimal_odds - 1) * 100)) if decimal_odds >= 2 else int(round(-100 / (decimal_odds - 1)))


def normalize_decimal_odds(row: Mapping[str, Any]) -> float | None:
    decimal = _num(row, "decimal_odds", "decimal_price", "current_decimal_odds", "odds_at_pick")
    if decimal and decimal > 1:
        return decimal
    american = _num(row, "american_odds", "current_american_odds", "odds")
    return american_to_decimal(american) if american is not None else None


def implied_probability_from_decimal(decimal_odds: float | None) -> float | None:
    return None if decimal_odds is None or decimal_odds <= 1 else 1 / decimal_odds


def fmt_prob(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def fmt_dec(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def fmt_american(decimal_odds: float | None) -> str:
    american = decimal_to_american(decimal_odds)
    if american is None:
        return "N/A"
    return f"+{american}" if american > 0 else str(american)


def risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    return "low" if score <= 3 else "medium" if score <= 6 else "high" if score <= 8 else "very high"


def _market_text(row: Mapping[str, Any]) -> str:
    return " ".join(_text(row, key).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))


def is_chain(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    return any(marker in market for marker in _CHAIN_MARKERS) or bool(row.get("legs"))


def is_home_run_prop(row: Mapping[str, Any]) -> bool:
    return any(marker in _market_text(row) for marker in _HR_MARKERS)


def is_player_prop(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    return is_home_run_prop(row) or any(marker in market for marker in _PROP_MARKERS)


def _model_probability(row: Mapping[str, Any]) -> float | None:
    return _prob(row, "model_probability", "learned_model_probability", "probability", "projected_probability")


def _chain_probability(row: Mapping[str, Any]) -> float | None:
    supplied = _prob(row, "combined_adjusted_probability", "adjusted_combined_probability", "chain_probability")
    if supplied is not None:
        return supplied
    legs = row.get("legs")
    if not isinstance(legs, Sequence) or isinstance(legs, (str, bytes)) or not legs:
        return None
    combined = 1.0
    for leg in legs:
        if not isinstance(leg, Mapping):
            return None
        probability = _model_probability(leg)
        if probability is None:
            return None
        combined *= probability
    penalty = _num(row, "correlation_penalty")
    if penalty is None:
        penalty = 0.03 * max(len(legs) - 1, 0)
    return max(0.0, combined * (1.0 - penalty))


def _edge(model_probability: float | None, implied_probability: float | None, supplied: float | None) -> float | None:
    if supplied is not None:
        return supplied / 100 if abs(supplied) > 1 else supplied
    if model_probability is None or implied_probability is None:
        return None
    return model_probability - implied_probability


def _ev(model_probability: float | None, decimal_odds: float | None, supplied: float | None) -> float | None:
    if supplied is not None:
        return supplied
    if model_probability is None or decimal_odds is None:
        return None
    return model_probability * decimal_odds - 1


def _analysis_pass(row: Mapping[str, Any]) -> bool:
    gate = _text(row, "sports_analysis_gate", "analysis_gate").lower()
    if gate in {"pass", "passed", "true", "yes", "supported"}:
        return True
    if gate in {"fail", "failed", "false", "no", "unsupported"}:
        return False
    return bool(_text(row, "why_pick", "why_we_are_picking", "analysis_summary", "reason", "explanation") or _num(row, "analysis_confidence", "pattern_points") is not None)


def _risk_score(row: Mapping[str, Any], model_probability: float | None, ev: float | None) -> float | None:
    supplied = _num(row, "risk_score", "blended_risk_score")
    if supplied is not None:
        return max(1.0, min(10.0, supplied))
    if model_probability is None:
        return None
    score = 10 - model_probability * 10
    if ev and ev > 0:
        score -= min(ev * 4, 1.5)
    if is_chain(row):
        legs = row.get("legs")
        score += len(legs) * 0.65 if isinstance(legs, Sequence) and not isinstance(legs, (str, bytes)) else 1.5
    if is_player_prop(row):
        score += 0.8
    if is_home_run_prop(row):
        score += 1.7
    return round(max(1.0, min(10.0, score)), 1)


def _stake(row: Mapping[str, Any], score: float | None) -> str:
    supplied = _text(row, "recommended_stake", "stake_suggestion", "stake", "recommended_units", "unit_size")
    if supplied:
        return supplied
    if score is None:
        return "Review manually"
    return "1.0 unit max" if score <= 3 else "0.5 unit max" if score <= 6 else "0.25 unit max / small bet only" if score <= 8 else "Watch only unless aggressive"


def _decision(row: Mapping[str, Any], analysis_ok: bool, odds_ok: bool, probability: float | None, ev: float | None, score: float | None) -> str:
    supplied = _text(row, "final_decision", "recommendation", "decision").upper()
    if supplied in FINAL_DECISIONS:
        return supplied
    if not analysis_ok:
        return "WATCH ONLY"
    if not odds_ok:
        return "GOOD READ, BAD PRICE" if probability and probability >= CORE_PROBABILITY_THRESHOLD else "BAD VALUE"
    if is_chain(row):
        return "AGGRESSIVE ONLY" if score and score > 8 else "SMALL BET"
    if is_home_run_prop(row):
        return "SMALL BET" if ev and ev > 0 and probability and probability >= CORE_PROBABILITY_THRESHOLD else "AGGRESSIVE ONLY"
    if probability is None or probability < CORE_PROBABILITY_THRESHOLD:
        return "WATCH ONLY"
    if score and score > 8:
        return "AGGRESSIVE ONLY"
    return "SMALL BET" if score and score > 6 else "BET"


def _compact(text: str, max_words: int = 10) -> str:
    words = str(text).replace("\n", " ").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(",.;") + "..."


def _split_supplied_bullets(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_compact(part.strip(" -•\t"), 10) for part in normalized.split("\n") if part.strip(" -•\t")]


def _add_bullet(bullets: list[str], text: str, max_words: int = 10) -> None:
    text = _compact(text, max_words)
    if text and text not in bullets:
        bullets.append(text)


def _why_pick(row: Mapping[str, Any], probability: float | None, implied: float | None, edge: float | None, score: float | None) -> str:
    supplied = _text(row, "why_pick", "why_we_are_picking", "analysis_summary", "reason", "explanation")
    if supplied:
        return supplied
    game = _text(row, "game", "event", "event_name", "matchup", default="the game")
    parts = [f"The available model fields support {game} at {fmt_prob(probability)} projected probability."]
    if implied is not None and edge is not None:
        parts.append(f"The market implies {fmt_prob(implied)}, creating a {edge:.1%} model-market edge.")
    if score is not None:
        parts.append(f"The blended risk score is {score:.1f}/10, which is {risk_level(score)} risk.")
    return " ".join(parts)


def _why_pick_bullets(row: Mapping[str, Any], probability: float | None, implied: float | None, edge: float | None, ev: float | None, score: float | None) -> tuple[str, ...]:
    bullets: list[str] = []
    supplied = _text(row, "why_bullets", "why_we_picked_it", "evidence_bullets", "professional_evidence", "pro_edge_reasons")
    if supplied:
        bullets.extend(_split_supplied_bullets(supplied))
    if probability is not None:
        _add_bullet(bullets, f"Model projects {fmt_prob(probability)} win probability")
    if implied is not None and edge is not None:
        _add_bullet(bullets, f"Market implies {fmt_prob(implied)}; edge {edge:.1%}")
    if ev is not None:
        _add_bullet(bullets, f"Expected value {ev:.3f} vs market")
    for keys, label in (
        (("injury_edge", "injury_report", "player_injuries"), "Injury edge"),
        (("starting_lineups", "lineup_status", "lineup_confirmation"), "Lineup status"),
        (("market_movement", "line_movement", "sharp_money_signal"), "Market signal"),
        (("public_betting", "public_betting_percentage"), "Public market"),
        (("best_price_edge", "sportsbook_discrepancy", "line_shopping_edge"), "Best price"),
        (("weather_impact", "wind_direction", "wind_speed"), "Weather impact"),
        (("travel_fatigue", "rest_advantage", "back_to_back"), "Fatigue edge"),
        (("team_form", "player_form", "recent_trend"), "Form edge"),
        (("news_signal", "news_sentiment", "beat_writer_update"), "News signal"),
        (("matchup_edge", "offensive_efficiency", "defensive_efficiency"), "Matchup edge"),
    ):
        value = _text(row, *keys)
        if value:
            _add_bullet(bullets, f"{label}: {value}")
    sport = _text(row, "sport", "sport_league", "league").lower()
    if any(word in sport for word in ("mlb", "baseball")):
        for keys, label in (
            (("starting_pitcher", "pitcher_name"), "Starter"),
            (("pitcher_handedness", "pitcher_vs_batter_handedness", "left_right_split"), "L/R split"),
            (("team_ops_vs_pitcher_side", "ops_vs_hand"), "OPS split"),
            (("bullpen_usage_last_3_days", "bullpen_fatigue"), "Bullpen fatigue"),
            (("park_factor", "stadium_factor"), "Park factor"),
            (("umpire_tendency", "umpire_zone"), "Umpire trend"),
            (("pitch_mix_edge", "pitch_mix_mismatch"), "Pitch mix edge"),
        ):
            value = _text(row, *keys)
            if value:
                _add_bullet(bullets, f"{label}: {value}")
    elif any(word in sport for word in ("soccer", "football", "fifa", "liga", "premier")):
        for keys, label in (
            (("starting_xi_strength", "starting_xi"), "Starting XI"),
            (("formation_matchup",), "Formation edge"),
            (("xg", "expected_goals"), "xG edge"),
            (("xga", "expected_goals_allowed"), "xGA edge"),
            (("set_piece_edge",), "Set-piece edge"),
            (("referee_tendency", "referee_cards"), "Referee trend"),
        ):
            value = _text(row, *keys)
            if value:
                _add_bullet(bullets, f"{label}: {value}")
    elif "basketball" in sport or "nba" in sport:
        for keys, label in (
            (("usage_rate_change", "usage_edge"), "Usage shift"),
            (("pace", "pace_edge"), "Pace edge"),
            (("lineup_net_rating",), "Lineup rating"),
            (("bench_depth",), "Bench depth"),
            (("rebounding_edge",), "Rebounding edge"),
        ):
            value = _text(row, *keys)
            if value:
                _add_bullet(bullets, f"{label}: {value}")
    elif "tennis" in sport:
        for keys, label in (
            (("surface_advantage",), "Surface edge"),
            (("serve_hold_percentage", "serve_hold_pct"), "Serve hold"),
            (("return_points_won", "return_win_percentage"), "Return edge"),
            (("break_point_conversion",), "Break conversion"),
            (("head_to_head_style", "h2h_style"), "Style edge"),
        ):
            value = _text(row, *keys)
            if value:
                _add_bullet(bullets, f"{label}: {value}")
    if score is not None:
        _add_bullet(bullets, f"Risk graded {risk_level(score)}")
    if not bullets:
        bullets.append("Insufficient pro evidence supplied")
    return tuple(bullets[:8])


def _why_lose(row: Mapping[str, Any]) -> str:
    supplied = _text(row, "why_lose", "why_it_could_lose", "risk_reason", "hidden_risk")
    if supplied:
        return supplied
    if is_home_run_prop(row):
        return "Home run props are high-variance markets and can lose even when the matchup profile is favorable."
    if is_player_prop(row):
        return "Player props can lose from lineup changes, limited plate appearances, pitcher approach, or game script."
    if is_chain(row):
        return "A chain bet can lose if any leg fails, and combined probability drops as legs are added."
    return "The bet can lose from late lineup changes, pitcher variance, bullpen failure, market movement, or normal sports variance."


def _score_from_row(row: Mapping[str, Any], *keys: str, default: float | None = None) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return default
    if value <= 1:
        value *= 100
    return round(max(0.0, min(100.0, value)), 1)


def _evidence_scores(row: Mapping[str, Any], probability: float | None, edge: float | None, ev: float | None, score: float | None) -> dict[str, float | None]:
    model_default = round((probability or 0) * 100, 1) if probability is not None else None
    edge_default = round(max(0.0, min(100.0, (edge or 0) * 1000)), 1) if edge is not None else None
    risk_penalty = round((score or 0) * 10, 1) if score is not None else None
    final_conf = _score_from_row(row, "final_confidence_score", "confidence_score", "confidence", default=model_default)
    return {
        "Model Edge": _score_from_row(row, "model_edge_score", default=edge_default),
        "Market Movement": _score_from_row(row, "market_movement_score", "line_movement_score"),
        "Injury Advantage": _score_from_row(row, "injury_advantage_score", "injury_score"),
        "Matchup Advantage": _score_from_row(row, "matchup_advantage_score", "matchup_score"),
        "Weather Impact": _score_from_row(row, "weather_impact_score", "weather_score"),
        "Fatigue": _score_from_row(row, "fatigue_score", "travel_fatigue_score"),
        "Form": _score_from_row(row, "form_score", "team_form_score", "player_form_score"),
        "News Confirmation": _score_from_row(row, "news_confirmation_score", "news_score"),
        "Line Shopping": _score_from_row(row, "line_shopping_score", "best_price_score"),
        "Risk Penalty": _score_from_row(row, "risk_penalty_score", default=risk_penalty),
        "Final Confidence": final_conf,
    }


def _checklist(row: Mapping[str, Any], decision: str, ev: float | None, edge: float | None) -> tuple[str, ...]:
    checks = []
    checks.append("EV+" if (ev is not None and ev > 0) or (edge is not None and edge > 0) else "EV warning")
    checks.append("Line playable" if decision not in {"GOOD READ, BAD PRICE", "BAD VALUE"} else "Price warning")
    checks.append("Injuries checked" if _text(row, "injury_report", "player_injuries", "injury_edge") else "Injury pending")
    checks.append("Lineups checked" if _text(row, "starting_lineups", "lineup_status", "lineup_confirmation") else "Lineup pending")
    checks.append("Weather checked" if _text(row, "weather_impact", "wind_speed", "weather_score") else "Weather monitor")
    checks.append("Risk acceptable" if decision in {"BET", "SMALL BET", "CHAIN ONLY"} else "Risk warning")
    return tuple(checks)


def _chain_analysis(row: Mapping[str, Any]) -> tuple[str, ...]:
    if not is_chain(row):
        return ()
    notes = []
    for keys, label in (
        (("main_read", "primary_leg"), "Main Read"),
        (("add_on_legs", "secondary_legs"), "Add-On"),
        (("filler_leg_risk",), "Filler Risk"),
        (("correlation_risk", "correlation_label"), "Correlation"),
        (("straight_bet_comparison", "better_straight_or_chain"), "Straight Compare"),
        (("chain_confidence", "combined_adjusted_probability"), "Chain Confidence"),
    ):
        value = _text(row, *keys)
        if value:
            notes.append(_compact(f"{label}: {value}", 10))
    if not notes:
        notes.append("Review every leg; reject filler payout chases")
    return tuple(notes[:6])


def _pro_notes(row: Mapping[str, Any], min_odds: float | None, score: float | None) -> tuple[str, ...]:
    notes: list[str] = []
    supplied = _text(row, "pro_notes", "professional_notes")
    if supplied:
        notes.extend(_split_supplied_bullets(supplied))
    if min_odds is not None:
        _add_bullet(notes, f"Playable to {fmt_dec(min_odds)} decimal", 7)
    invalidation = _text(row, "invalidation_condition", "avoid_if", "no_bet_if")
    if invalidation:
        _add_bullet(notes, f"Avoid if {invalidation}")
    elif _text(row, "starting_pitcher", "pitcher_name"):
        _add_bullet(notes, "Avoid if starter scratched", 6)
    if _text(row, "injury_report", "player_injuries"):
        _add_bullet(notes, "Recheck injuries before lock", 6)
    if _text(row, "weather_impact", "wind_speed"):
        _add_bullet(notes, "Recheck weather 60 min pregame", 6)
    if is_chain(row):
        _add_bullet(notes, "Reject weak filler legs", 5)
    else:
        _add_bullet(notes, "Better as straight if price holds", 7)
    if score is not None and score > 6:
        _add_bullet(notes, "Small stake due to risk", 6)
    return tuple(notes[:6])


@dataclass(frozen=True)
class CatalogPick:
    pick_title: str
    game: str
    sport_league: str
    start_time: str
    bet_type: str
    exact_bet: str
    sportsbook_casino: str
    current_odds: str
    closest_double_money_odds: str
    implied_probability: float | None
    model_probability: float | None
    passes_65_filter: bool
    edge: float | None
    expected_value: float | None
    risk_score: float | None
    risk_level: str
    recommended_stake: str
    why_pick: str
    why_pick_bullets: tuple[str, ...]
    why_lose: str
    final_decision: str
    minimum_playable_odds: str
    evidence_scores: dict[str, float | None]
    pro_checklist: tuple[str, ...]
    pro_notes: tuple[str, ...]
    chain_analysis: tuple[str, ...]
    chain_combined_probability: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_catalog_pick(row: Mapping[str, Any]) -> CatalogPick:
    decimal = normalize_decimal_odds(row)
    implied = _prob(row, "implied_probability", "market_implied_probability") or implied_probability_from_decimal(decimal)
    probability = _chain_probability(row) if is_chain(row) else _model_probability(row)
    edge = _edge(probability, implied, _num(row, "edge", "model_market_edge"))
    ev = _ev(probability, decimal, _num(row, "expected_value", "ev"))
    score = _risk_score(row, probability, ev)
    odds_ok = (ev is not None and ev > 0) or (edge is not None and edge > 0)
    decision = _decision(row, _analysis_pass(row), odds_ok, probability, ev, score)
    exact_bet = _text(row, "exact_bet", "pick", "prediction", "selection", default="Bet not specified")
    min_odds = None if not probability else 1 / probability
    return CatalogPick(
        pick_title=_text(row, "pick_title", "title") or f"{exact_bet} — {decision}",
        game=_text(row, "game", "event", "event_name", "matchup", default="Game not specified"),
        sport_league=_text(row, "sport_league", "league", "sport", default="MLB Baseball"),
        start_time=_text(row, "start_time", "commence_time", "event_time", default="Not specified"),
        bet_type=_text(row, "bet_type", "market", "market_type", default="Market not specified"),
        exact_bet=exact_bet,
        sportsbook_casino=_text(row, "sportsbook_casino", "bookmaker", "best_bookmaker", "sportsbook", default="Best available"),
        current_odds=f"{fmt_american(decimal)} / {fmt_dec(decimal)} decimal",
        closest_double_money_odds="N/A" if decimal is None else f"{fmt_american(decimal)} / {fmt_dec(decimal)} decimal; gap {abs(decimal - DOUBLE_MONEY_DECIMAL):.2f} from 2.00",
        implied_probability=implied,
        model_probability=probability,
        passes_65_filter=bool(probability is not None and probability >= CORE_PROBABILITY_THRESHOLD),
        edge=edge,
        expected_value=ev,
        risk_score=score,
        risk_level=risk_level(score),
        recommended_stake=_stake(row, score),
        why_pick=_why_pick(row, probability, implied, edge, score),
        why_pick_bullets=_why_pick_bullets(row, probability, implied, edge, ev, score),
        why_lose=_why_lose(row),
        final_decision=decision,
        minimum_playable_odds=fmt_dec(min_odds),
        evidence_scores=_evidence_scores(row, probability, edge, ev, score),
        pro_checklist=_checklist(row, decision, ev, edge),
        pro_notes=_pro_notes(row, min_odds, score),
        chain_analysis=_chain_analysis(row),
        chain_combined_probability=_chain_probability(row) if is_chain(row) else None,
    )


def _sort_key(pick: CatalogPick) -> tuple[int, float, float, float]:
    rank = 0 if pick.final_decision == "BET" else 1 if pick.final_decision == "SMALL BET" else 2
    return (rank, -(pick.expected_value if pick.expected_value is not None else -99), -(pick.model_probability or 0), pick.risk_score or 10)


def build_bet_catalog(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[CatalogPick]]:
    row_list = list(rows)
    sections = {section: [] for section in CATALOG_SECTIONS}
    for row in row_list:
        pick = build_catalog_pick(row)
        playable = pick.final_decision in {"BET", "SMALL BET", "CHAIN ONLY"}
        if pick.passes_65_filter and playable and not is_chain(row) and not is_player_prop(row):
            sections["Best 65%+ Singles"].append(pick)
        if playable and pick.expected_value is not None and pick.expected_value > 0:
            sections["Best Good-Odds Bets"].append(pick)
        decimal = normalize_decimal_odds(row)
        if playable and decimal is not None and abs(decimal - DOUBLE_MONEY_DECIMAL) <= 0.25:
            sections["Closest Double-Money Bets"].append(pick)
        if is_chain(row):
            score = pick.risk_score if pick.risk_score is not None else 10
            sections["Conservative Baseball Chains" if score <= 4 else "Balanced Baseball Chains" if score <= 7 else "Aggressive Baseball Chains"].append(pick)
        if is_player_prop(row) and not is_home_run_prop(row):
            sections["Player Prop Catalog"].append(pick)
        if is_home_run_prop(row):
            sections["Home Run Watchlist"].append(pick)
        if pick.final_decision in {"GOOD READ, BAD PRICE", "WAIT FOR BETTER ODDS"}:
            sections["Good Read / Bad Price"].append(pick)
        if pick.final_decision in {"NO BET", "WATCH ONLY", "BAD VALUE"}:
            sections["No-Bet List"].append(pick)
    for picks in sections.values():
        picks.sort(key=_sort_key)
    return sections


def _score_line(label: str, value: float | None) -> str:
    return f"{label}: {'N/A' if value is None else f'{value:.0f}/100'}"


def render_pick_card(pick: CatalogPick) -> str:
    edge = "N/A" if pick.edge is None else f"{pick.edge:.1%}"
    ev = "N/A" if pick.expected_value is None else f"{pick.expected_value:.3f}"
    risk = "N/A" if pick.risk_score is None else f"{pick.risk_score:.1f}/10"
    confidence = pick.evidence_scores.get("Final Confidence")
    lines = [
        f"### {pick.pick_title}",
        f"**{pick.game}** | {pick.sport_league} | {pick.start_time}",
        f"**Pick:** {pick.exact_bet}",
        f"**Book:** {pick.sportsbook_casino} | **Odds:** {pick.current_odds}",
        f"**Confidence:** {'N/A' if confidence is None else f'{confidence:.0f}%'} | **Edge:** {edge} | **EV:** {ev}",
        f"**Units:** {pick.recommended_stake} | **Risk:** {pick.risk_level} ({risk})",
        "",
        "**Why We Picked It**",
    ]
    lines.extend(f"- {bullet}" for bullet in pick.why_pick_bullets)
    score_bits = [
        _score_line("Model", pick.evidence_scores.get("Model Edge")),
        _score_line("Market", pick.evidence_scores.get("Market Movement")),
        _score_line("Injury", pick.evidence_scores.get("Injury Advantage")),
        _score_line("Matchup", pick.evidence_scores.get("Matchup Advantage")),
        _score_line("Weather", pick.evidence_scores.get("Weather Impact")),
        _score_line("Fatigue", pick.evidence_scores.get("Fatigue")),
        _score_line("Form", pick.evidence_scores.get("Form")),
        _score_line("News", pick.evidence_scores.get("News Confirmation")),
        _score_line("Line Shop", pick.evidence_scores.get("Line Shopping")),
        _score_line("Risk Penalty", pick.evidence_scores.get("Risk Penalty")),
    ]
    lines += [
        "",
        "**Evidence Scores:** " + " • ".join(score_bits),
        "**Checklist:** " + " • ".join(pick.pro_checklist),
    ]
    if pick.chain_combined_probability is not None:
        lines.append(f"- Chain Combined Adjusted Probability: {fmt_prob(pick.chain_combined_probability)}")
    if pick.chain_analysis:
        lines += ["", "**Chain/Parlay Notes**"]
        lines.extend(f"- {note}" for note in pick.chain_analysis)
    lines += ["", "**Pro Notes**"]
    lines.extend(f"- {note}" for note in pick.pro_notes)
    lines += [
        "",
        f"**Could Lose If:** {_compact(pick.why_lose, 18)}",
        f"**Final Recommendation:** {pick.final_decision}",
    ]
    return "\n".join(lines)


def render_betting_magazine(rows: Iterable[Mapping[str, Any]], title: str = "ABA Signal Pro Betting Magazine", subscriber_name: str = "") -> str:
    catalog = build_bet_catalog(rows)
    lines = [f"# {title}", ""]
    if subscriber_name:
        lines += [f"**Subscriber:** {subscriber_name}", ""]
    lines += [
        "**Analytics notice:** Projected-probability and odds-value analysis only. No guaranteed wins, profit, or 65% actual win rate.",
        "**Security:** API keys stay server-side. Reports are analytics only and do not execute bets.",
        "**Mobile format:** Top 3 cards per section are rendered for one-page/image readability; export CSV keeps the full catalog.",
        "",
    ]
    for section in CATALOG_SECTIONS:
        lines += [f"## {section}", ""]
        picks = catalog[section]
        if not picks:
            lines.append("NO CHAIN RECOMMENDED TODAY" if "Chain" in section else "No qualifying picks in this section.")
            lines.append("")
            continue
        for pick in picks[:MOBILE_PICK_LIMIT]:
            lines.append(render_pick_card(pick))
            lines.append("")
        if len(picks) > MOBILE_PICK_LIMIT:
            lines.append(f"_{len(picks) - MOBILE_PICK_LIMIT} additional picks available in CSV export._")
            lines.append("")
    return "\n".join(lines).strip() + "\n"
