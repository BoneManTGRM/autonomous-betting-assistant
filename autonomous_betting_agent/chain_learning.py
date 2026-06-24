"""Leg-level chain bet learning.

This module grades completed chain structures and creates conservative learning
signals. It does not place bets and does not guarantee future results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

WIN = "win"
LOSS = "loss"
PUSH = "push"
VOID = "void"
UNKNOWN = "unknown"
NEUTRAL_STATUSES = {PUSH, VOID, "cancel", "canceled", "cancelled"}


@dataclass(frozen=True)
class ChainLegResult:
    leg_name: str
    market: str
    selection: str
    status: str = UNKNOWN
    was_main_read: bool = False
    was_add_on_leg: bool = False
    was_filler_leg: bool = False
    game_script_supported: bool = False
    failed_reason: str = ""
    learning_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ChainResultBreakdown:
    chain_id: str
    game: str
    final_status: str
    straight_pick_status: str
    chain_status: str
    failed_leg_count: int
    failed_legs: tuple[str, ...] = field(default_factory=tuple)
    main_read_correct: bool | None = None
    game_script_correct: bool | None = None
    target_payout_chase_detected: bool = False
    straight_bet_would_have_won: bool = False
    chain_was_better_than_straight: bool = False
    leg_results: tuple[ChainLegResult, ...] = field(default_factory=tuple)
    learning_summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["leg_results"] = [leg.as_dict() for leg in self.leg_results]
        return data


@dataclass(frozen=True)
class ChainLearningSignal:
    signal_type: str
    market_type: str
    script_type: str
    leg_type: str
    adjustment_direction: str
    adjustment_strength: float
    reason: str
    sample_size: int = 1
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _text(row: Mapping[str, Any] | None, *keys: str, default: str = "") -> str:
    if not row:
        return default
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _bool(row: Mapping[str, Any] | None, *keys: str) -> bool:
    value = _text(row, *keys).lower()
    return value in {"1", "true", "yes", "y", "main", "primary"}


def _status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"won", "win", "w"}:
        return WIN
    if text in {"lost", "loss", "lose", "l"}:
        return LOSS
    if text in {"push", "p"}:
        return PUSH
    if text in {"void", "cancel", "canceled", "cancelled", "no action"}:
        return VOID
    return UNKNOWN


def _market_type(row: Mapping[str, Any] | None) -> str:
    return _text(row, "market", "market_type", "bet_type", default="unknown")


def _selection(row: Mapping[str, Any] | None) -> str:
    return _text(row, "selection", "prediction", "pick", "exact_bet", default="unknown")


def _leg_name(row: Mapping[str, Any] | None) -> str:
    return _text(row, "leg_name", "pick_title", "title") or f"{_market_type(row)} {_selection(row)}".strip()


def _is_filler(row: Mapping[str, Any] | None) -> bool:
    text = f"{_leg_name(row)} {_market_type(row)} {_selection(row)} {_text(row, 'rejection_reason', 'final_explanation')}".lower()
    return _bool(row, "was_filler_leg", "filler_leg") or "filler" in text or "random" in text or "payout chase" in text


def _is_main_read(row: Mapping[str, Any] | None) -> bool:
    text = f"{_market_type(row)} {_selection(row)} {_text(row, 'role', 'leg_role')}".lower()
    return _bool(row, "was_main_read", "main_read") or "moneyline" in text or "1x2" in text or "straight" in text or "main" in text


def _script_supported(row: Mapping[str, Any] | None) -> bool:
    text = f"{_text(row, 'game_script_supported', 'correlation_label', 'context_effect', 'why_leg_belongs')}".lower()
    return "positive" in text or "supported" in text or "strengthened" in text or _bool(row, "game_script_supported")


def _match_graded_row(leg: Mapping[str, Any], graded_rows: Iterable[Mapping[str, Any]] | None) -> Mapping[str, Any] | None:
    if not graded_rows:
        return None
    leg_name = _leg_name(leg).lower()
    selection = _selection(leg).lower()
    market = _market_type(leg).lower()
    for row in graded_rows:
        row_text = f"{_leg_name(row)} {_selection(row)} {_market_type(row)}".lower()
        if leg_name and leg_name in row_text:
            return row
        if selection and selection in row_text and market and market in row_text:
            return row
    return None


def grade_chain_leg(leg: Mapping[str, Any], final_score: Any = None, graded_rows: Iterable[Mapping[str, Any]] | None = None) -> ChainLegResult:
    matched = _match_graded_row(leg, graded_rows)
    source = matched or leg
    status = _status(_text(source, "result_status", "status", "grade", "outcome", "final_status"))
    was_main = _is_main_read(leg)
    was_filler = _is_filler(leg)
    script_supported = _script_supported(leg)
    failed_reason = ""
    if status == LOSS:
        if was_filler:
            failed_reason = "Target-payout or random filler leg failed."
        elif not script_supported:
            failed_reason = "Add-on leg failed without strong game-script support."
        elif was_main:
            failed_reason = "Main read failed."
        else:
            failed_reason = "Add-on leg failed."
    elif status in NEUTRAL_STATUSES:
        failed_reason = "Neutral result; do not count as win/loss."
    elif status == UNKNOWN:
        failed_reason = "Unknown result; no strong learning signal."
    learning_note = ""
    if status == LOSS and was_main:
        learning_note = "Main read was wrong; reduce confidence in this script/read type."
    elif status == LOSS and was_filler:
        learning_note = "Penalize filler legs added mainly for payout."
    elif status == LOSS:
        learning_note = "Review this add-on market before using similar chains."
    elif status == WIN and script_supported:
        learning_note = "Leg matched script and won; keep as weak positive signal until sample grows."
    else:
        learning_note = "Neutral or insufficient signal."
    return ChainLegResult(
        leg_name=_leg_name(leg),
        market=_market_type(leg),
        selection=_selection(leg),
        status=status,
        was_main_read=was_main,
        was_add_on_leg=not was_main,
        was_filler_leg=was_filler,
        game_script_supported=script_supported,
        failed_reason=failed_reason,
        learning_note=learning_note,
    )


def _chain_legs(chain: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("legs", "accepted_legs", "leg_results"):
        value = chain.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [item for item in value if isinstance(item, Mapping)]
    return [chain]


def _chain_status_from_legs(legs: Sequence[ChainLegResult], explicit: str = "") -> str:
    explicit_status = _status(explicit)
    if explicit_status != UNKNOWN:
        return explicit_status
    active = [leg.status for leg in legs if leg.status not in NEUTRAL_STATUSES]
    if any(status == LOSS for status in active):
        return LOSS
    if active and all(status == WIN for status in active):
        return WIN
    return UNKNOWN


def identify_failed_chain_leg(chain_result: ChainResultBreakdown) -> ChainLegResult | None:
    failed = [leg for leg in chain_result.leg_results if leg.status == LOSS]
    if len(failed) == 1:
        return failed[0]
    return None


def evaluate_game_script_accuracy(chain: Mapping[str, Any] | ChainResultBreakdown, final_score: Any = None, event_stats: Mapping[str, Any] | None = None) -> bool | None:
    if isinstance(chain, ChainResultBreakdown):
        if chain.chain_status == WIN:
            return True
        if chain.main_read_correct is False:
            return False
        if any(leg.game_script_supported and leg.status == LOSS for leg in chain.leg_results):
            return False
        if any(leg.game_script_supported and leg.status == WIN for leg in chain.leg_results):
            return True
        return None
    text = _text(chain, "game_script_correct", "script_result", "script_status").lower()
    if text in {"true", "yes", "correct", "hit"}:
        return True
    if text in {"false", "no", "wrong", "miss"}:
        return False
    return None


def evaluate_target_payout_decision(chain_result: ChainResultBreakdown) -> bool:
    if chain_result.target_payout_chase_detected:
        return True
    return any(leg.was_filler_leg and leg.status == LOSS for leg in chain_result.leg_results)


def grade_chain_result(chain: Mapping[str, Any], final_score: Any = None, graded_rows: Iterable[Mapping[str, Any]] | None = None) -> ChainResultBreakdown:
    legs = tuple(grade_chain_leg(leg, final_score=final_score, graded_rows=graded_rows) for leg in _chain_legs(chain))
    explicit_chain_status = _text(chain, "chain_status", "final_status", "result_status", "status")
    chain_status = _chain_status_from_legs(legs, explicit_chain_status)
    straight_status = _status(_text(chain, "straight_pick_status", "straight_status"))
    failed_legs = tuple(leg.leg_name for leg in legs if leg.status == LOSS)
    main_legs = [leg for leg in legs if leg.was_main_read]
    main_read_correct = None
    if main_legs:
        if any(leg.status == LOSS for leg in main_legs):
            main_read_correct = False
        elif any(leg.status == WIN for leg in main_legs):
            main_read_correct = True
    straight_would_have_won = straight_status == WIN or bool(main_read_correct and chain_status == LOSS)
    target_chase = _text(chain, "target_payout_fit", "target_fit_label").lower() in {"forced payout chase", "good target fit", "excellent target fit"} and any(leg.was_filler_leg for leg in legs)
    temp = ChainResultBreakdown(
        chain_id=_text(chain, "chain_id", "id", default="unknown_chain"),
        game=_text(chain, "game", "event", "event_name", "matchup", default="Unknown"),
        final_status=chain_status,
        straight_pick_status=straight_status,
        chain_status=chain_status,
        failed_leg_count=len(failed_legs),
        failed_legs=failed_legs,
        main_read_correct=main_read_correct,
        game_script_correct=None,
        target_payout_chase_detected=target_chase,
        straight_bet_would_have_won=straight_would_have_won,
        chain_was_better_than_straight=chain_status == WIN and straight_status != WIN,
        leg_results=legs,
        learning_summary="",
    )
    script_correct = evaluate_game_script_accuracy(temp, final_score=final_score)
    summary = _learning_summary(temp, script_correct)
    return ChainResultBreakdown(**{**temp.__dict__, "game_script_correct": script_correct, "learning_summary": summary})


def _learning_summary(result: ChainResultBreakdown, script_correct: bool | None = None) -> str:
    if result.chain_status == WIN and result.failed_leg_count == 0:
        return "Chain won and all active legs matched sufficiently."
    if result.main_read_correct and result.failed_leg_count == 1:
        failed = identify_failed_chain_leg(result)
        if failed and failed.was_add_on_leg:
            return "Main read correct, add-on leg failed."
    if result.straight_bet_would_have_won and result.chain_status == LOSS:
        return "Straight bet would have won; chain reduced ROI."
    if result.target_payout_chase_detected:
        return "Target payout chase detected; filler leg may have hurt the ticket."
    if script_correct is False:
        return "Chain lost because the game script was wrong."
    if result.failed_leg_count:
        return "Chain lost because one or more legs failed."
    return "Insufficient result data for strong learning."


def build_chain_learning_signal(chain_result: ChainResultBreakdown) -> ChainLearningSignal:
    failed = identify_failed_chain_leg(chain_result)
    script_type = "unknown"
    if chain_result.game_script_correct is True:
        script_type = "script_correct"
    elif chain_result.game_script_correct is False:
        script_type = "script_wrong"
    if failed:
        direction = "decrease"
        strength = 0.55
        reason = failed.failed_reason or "Failed chain leg."
        if "corner" in failed.market.lower() or "corner" in failed.selection.lower():
            reason = "Reduce underdog corner add-ons unless pressure data supports it."
            strength = 0.65
        return ChainLearningSignal(
            signal_type="failed_leg_pattern",
            market_type=failed.market,
            script_type=script_type,
            leg_type="main_read" if failed.was_main_read else "add_on",
            adjustment_direction=direction,
            adjustment_strength=strength,
            reason=reason,
            confidence=0.50 if failed.status != UNKNOWN else 0.1,
        )
    if chain_result.straight_bet_would_have_won and chain_result.chain_status == LOSS:
        return ChainLearningSignal(
            signal_type="straight_bet_better",
            market_type="chain",
            script_type=script_type,
            leg_type="chain",
            adjustment_direction="watch_only",
            adjustment_strength=0.8,
            reason="Straight bet would have won while chain lost.",
            confidence=0.55,
        )
    if chain_result.target_payout_chase_detected:
        return ChainLearningSignal(
            signal_type="target_payout_chase",
            market_type="chain",
            script_type=script_type,
            leg_type="filler",
            adjustment_direction="decrease",
            adjustment_strength=0.7,
            reason="Target payout chase or filler leg detected.",
            confidence=0.55,
        )
    if chain_result.chain_status == WIN and chain_result.failed_leg_count == 0:
        return ChainLearningSignal(
            signal_type="successful_chain_pattern",
            market_type="chain",
            script_type=script_type,
            leg_type="all",
            adjustment_direction="increase",
            adjustment_strength=0.25,
            reason="Chain won cleanly; keep only as weak positive signal until sample grows.",
            confidence=0.35,
        )
    return ChainLearningSignal(
        signal_type="insufficient_data",
        market_type="unknown",
        script_type=script_type,
        leg_type="unknown",
        adjustment_direction="neutral",
        adjustment_strength=0.0,
        reason="Unknown, push/void, or incomplete result; no strong learning.",
        confidence=0.0,
    )


def summarize_chain_learning(chain_results: Iterable[ChainResultBreakdown]) -> dict[str, Any]:
    results = list(chain_results)
    failed: dict[str, int] = {}
    wins = 0
    losses = 0
    straight_better = 0
    target_chase = 0
    script_known = 0
    script_correct = 0
    for result in results:
        if result.chain_status == WIN:
            wins += 1
        elif result.chain_status == LOSS:
            losses += 1
        if result.straight_bet_would_have_won and result.chain_status == LOSS:
            straight_better += 1
        if result.target_payout_chase_detected:
            target_chase += 1
        if result.game_script_correct is not None:
            script_known += 1
            script_correct += int(result.game_script_correct)
        for leg in result.leg_results:
            if leg.status == LOSS:
                failed[leg.market] = failed.get(leg.market, 0) + 1
    return {
        "graded_chains": len(results),
        "wins": wins,
        "losses": losses,
        "straight_bet_better_cases": straight_better,
        "target_payout_chase_cases": target_chase,
        "game_script_accuracy": None if not script_known else round(script_correct / script_known, 4),
        "most_common_failed_markets": sorted(failed.items(), key=lambda item: item[1], reverse=True),
        "signals": [build_chain_learning_signal(result).as_dict() for result in results],
    }
