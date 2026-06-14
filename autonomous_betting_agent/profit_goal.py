from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

WIN_LABELS = {"won", "win", "w", "correct", "hit", "true", "yes", "1"}
LOSS_LABELS = {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0"}
PUSH_LABELS = {"push", "void", "draw", "tie", "refund", "cancelled", "canceled"}

EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
START_COLUMNS = ("start", "start_time", "event_start", "date", "commence_time")
PICK_COLUMNS = ("prediction", "pick", "predicted_side", "selection", "team", "player_name")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
GAME_ID_COLUMNS = ("sdio_game_id", "sportsdataio_game_id", "game_id", "event_id", "sdio_result_game_id")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
PRICE_COLUMNS = ("best_price", "price", "odds", "decimal_odds", "sportsbook_odds", "entry_price", "entry_odds")
CLOSING_PRICE_COLUMNS = ("closing_price", "closing_odds", "close_price", "close_odds")
CLV_COLUMNS = ("closing_line_value", "clv", "closing_line_delta")


@dataclass(frozen=True)
class ProfitGoalPolicy:
    target_win_rate: float = 0.70
    win_rate_tolerance: float = 0.01
    min_average_odds: float = 1.43
    min_roi: float = 0.0
    min_average_clv: float = 0.0
    min_finished: int = 200
    require_positive_clv: bool = True
    require_no_duplicates: bool = True


@dataclass(frozen=True)
class ProfitGoalReport:
    status: str
    finished_rows: int
    raw_rows: int
    duplicate_rows: int
    deduped_finished_rows: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    average_odds: float | None
    unit_profit_loss: float
    roi: float | None
    average_clv: float | None
    clv_rows: int
    goal_checks: dict[str, bool | None]
    required_actions: list[str]
    notes: list[str]


def _clean_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return None


def _clean_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def parse_result(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in WIN_LABELS:
        return "win"
    if text in LOSS_LABELS:
        return "loss"
    if text in PUSH_LABELS:
        return "push"
    return None


def parse_price(value: Any) -> float | None:
    price = parse_float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def _record_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    game_id = _clean_id(_first(row, GAME_ID_COLUMNS))
    market = str(_first(row, MARKET_COLUMNS) or "").strip().lower()
    pick = str(_first(row, PICK_COLUMNS) or "").strip().lower()
    if game_id:
        return "game_id", game_id, market, pick
    event = str(_first(row, EVENT_COLUMNS) or "").strip().lower()
    start = str(_first(row, START_COLUMNS) or "").strip().lower()
    return "event_start", f"{event}|{start}", market, pick


def unit_profit_loss(result: str, price: float | None) -> float:
    if result == "push":
        return 0.0
    if result == "loss":
        return -1.0
    if result == "win" and price is not None:
        return price - 1.0
    if result == "win":
        return 0.0
    return 0.0


def closing_line_value(row: Mapping[str, Any], entry_price: float | None) -> float | None:
    direct = parse_float(_first(row, CLV_COLUMNS))
    if direct is not None:
        if abs(direct) > 1.0:
            direct /= 100.0
        return direct
    close_price = parse_price(_first(row, CLOSING_PRICE_COLUMNS))
    if entry_price is None or close_price is None or entry_price <= 0:
        return None
    return (entry_price - close_price) / entry_price


def review_profit_goal_rows(rows: list[Mapping[str, Any]], policy: ProfitGoalPolicy = ProfitGoalPolicy()) -> ProfitGoalReport:
    seen: set[tuple[str, str, str, str]] = set()
    duplicate_rows = 0
    finished: list[tuple[Mapping[str, Any], str, float | None, float | None]] = []

    for row in rows:
        result = parse_result(_first(row, RESULT_COLUMNS))
        if result is None:
            continue
        key = _record_key(row)
        if key in seen:
            duplicate_rows += 1
            continue
        seen.add(key)
        price = parse_price(_first(row, PRICE_COLUMNS))
        clv = closing_line_value(row, price)
        finished.append((row, result, price, clv))

    wins = sum(1 for _, result, _, _ in finished if result == "win")
    losses = sum(1 for _, result, _, _ in finished if result == "loss")
    pushes = sum(1 for _, result, _, _ in finished if result == "push")
    decisions = wins + losses
    prices = [price for _, _, price, _ in finished if price is not None]
    clvs = [clv for _, _, _, clv in finished if clv is not None]
    unit_pl = sum(unit_profit_loss(result, price) for _, result, price, _ in finished)

    win_rate = wins / decisions if decisions else None
    avg_odds = sum(prices) / len(prices) if prices else None
    roi = unit_pl / decisions if decisions else None
    avg_clv = sum(clvs) / len(clvs) if clvs else None

    checks: dict[str, bool | None] = {
        "enough_finished_picks": decisions >= policy.min_finished,
        "win_rate_in_target_band": None if win_rate is None else policy.target_win_rate - policy.win_rate_tolerance <= win_rate <= policy.target_win_rate + policy.win_rate_tolerance,
        "win_rate_at_or_above_floor": None if win_rate is None else win_rate >= policy.target_win_rate - policy.win_rate_tolerance,
        "average_odds_above_minimum": None if avg_odds is None else avg_odds >= policy.min_average_odds,
        "positive_roi": None if roi is None else roi > policy.min_roi,
        "positive_average_clv": None if avg_clv is None else avg_clv > policy.min_average_clv,
        "no_duplicate_padding": duplicate_rows == 0,
    }

    required_actions: list[str] = []
    if not checks["enough_finished_picks"]:
        required_actions.append(f"Track at least {policy.min_finished} finished non-push picks before trusting the goal.")
    if checks["win_rate_at_or_above_floor"] is False:
        required_actions.append("Win rate is below the 70 percent target band; tighten filters or downweight weak buckets.")
    if checks["average_odds_above_minimum"] is False:
        required_actions.append("Average odds are below 1.43; high win rate may not be profitable.")
    if checks["positive_roi"] is False:
        required_actions.append("ROI is not positive; do not treat the group as profitable.")
    if policy.require_positive_clv and checks["positive_average_clv"] is not True:
        required_actions.append("Add or improve closing-odds data until average CLV is positive.")
    if policy.require_no_duplicates and duplicate_rows > 0:
        required_actions.append("Remove duplicate game/market/pick rows before reporting performance.")

    hard_checks = [
        checks["enough_finished_picks"],
        checks["win_rate_at_or_above_floor"],
        checks["average_odds_above_minimum"],
        checks["positive_roi"],
        checks["no_duplicate_padding"] if policy.require_no_duplicates else True,
    ]
    if policy.require_positive_clv:
        hard_checks.append(checks["positive_average_clv"])

    if all(item is True for item in hard_checks):
        status = "GOAL_MET"
    elif decisions == 0:
        status = "NO_FINISHED_DATA"
    else:
        status = "NOT_MET_YET"

    notes = [
        "Profit goal uses deduped finished rows only.",
        "Duplicate protection prefers game_id + market + pick when game IDs are available, then falls back to event/start + market + pick.",
        "Win rate alone is not enough; odds, ROI, CLV and duplicates are checked separately.",
        "Positive CLV requires a closing odds column or a direct CLV column.",
    ]

    return ProfitGoalReport(
        status=status,
        finished_rows=decisions,
        raw_rows=len(rows),
        duplicate_rows=duplicate_rows,
        deduped_finished_rows=len(finished),
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=None if win_rate is None else round(win_rate, 4),
        average_odds=None if avg_odds is None else round(avg_odds, 4),
        unit_profit_loss=round(unit_pl, 4),
        roi=None if roi is None else round(roi, 4),
        average_clv=None if avg_clv is None else round(avg_clv, 4),
        clv_rows=len(clvs),
        goal_checks=checks,
        required_actions=required_actions,
        notes=notes,
    )


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def review_profit_goal_csv(path: str | Path, policy: ProfitGoalPolicy = ProfitGoalPolicy()) -> ProfitGoalReport:
    return review_profit_goal_rows(read_csv_rows(path), policy=policy)


def write_report(report: ProfitGoalReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
