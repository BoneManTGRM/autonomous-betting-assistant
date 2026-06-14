from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds")
PROBABILITY_COLUMNS = ("calibrated_probability", "model_probability", "probability", "prop_blended_probability", "prop_model_probability")
EDGE_COLUMNS = ("edge", "expected_value", "ev", "prop_implied_edge")
SPORT_COLUMNS = ("sport",)
LEAGUE_COLUMNS = ("league", "competition")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
TEAM_COLUMNS = ("team", "selection", "prediction", "home_team", "away_team", "player_name")
STATUS_COLUMNS = ("ensemble_status", "profile_trust_level", "prop_status", "status")
SCORE_COLUMNS = ("ensemble_score", "profile_accuracy_score", "confidence_score", "data_quality")


@dataclass(frozen=True)
class BankrollPolicy:
    bankroll_units: float = 100.0
    max_stake_per_pick_units: float = 2.0
    min_stake_units: float = 0.10
    kelly_fraction: float = 0.25
    max_daily_exposure_units: float = 8.0
    max_sport_exposure_units: float = 4.0
    max_league_exposure_units: float = 3.0
    max_market_exposure_units: float = 3.0
    max_team_exposure_units: float = 2.0
    require_ensemble_accept: bool = True
    reject_low_trust_profiles: bool = False
    min_ensemble_score: float = 60.0
    min_probability: float = 0.53
    min_edge: float = 0.01


@dataclass(frozen=True)
class BankrollReport:
    raw_rows: int
    bet_rows: int
    watch_rows: int
    rejected_rows: int
    total_stake_units: float
    average_stake_units: float | None
    max_stake_units: float | None
    exposure_by_sport: dict[str, float]
    exposure_by_league: dict[str, float]
    exposure_by_market: dict[str, float]
    exposure_by_team: dict[str, float]
    output_csv: str | None
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return ""


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_price(value: Any) -> float | None:
    price = _float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def parse_probability(value: Any) -> float | None:
    probability = _float(value)
    if probability is None:
        return None
    if probability > 1.0:
        probability /= 100.0
    if probability < 0 or probability > 1:
        return None
    return probability


def _edge(row: Mapping[str, Any]) -> float | None:
    value = _float(_first(row, EDGE_COLUMNS))
    if value is None:
        return None
    return value / 100.0 if abs(value) > 1.0 else value


def _score(row: Mapping[str, Any]) -> float:
    scores = [_float(_first(row, (column,))) for column in SCORE_COLUMNS]
    scores = [score for score in scores if score is not None]
    if not scores:
        return 0.0
    return max(scores)


def _norm(value: Any, fallback: str = "unknown") -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return text or fallback


def _kelly_units(probability: float | None, price: float | None, policy: BankrollPolicy) -> float:
    if probability is None or price is None or price <= 1.0:
        return 0.0
    b = price - 1.0
    edge_fraction = ((b * probability) - (1.0 - probability)) / b
    if edge_fraction <= 0:
        return 0.0
    stake = policy.bankroll_units * edge_fraction * policy.kelly_fraction
    return max(0.0, min(policy.max_stake_per_pick_units, stake))


def _risk_tier(row: Mapping[str, Any], stake: float) -> str:
    trust = str(row.get("profile_trust_level", "")).strip().upper()
    score = _score(row)
    if stake <= 0:
        return "NO_BET"
    if trust == "HIGH" and score >= 75:
        return "LOW"
    if trust in {"HIGH", "MEDIUM"} and score >= 60:
        return "MEDIUM"
    return "HIGH"


def _base_rejection_reasons(row: Mapping[str, Any], policy: BankrollPolicy) -> list[str]:
    reasons: list[str] = []
    ensemble_status = str(row.get("ensemble_status", "")).strip().upper()
    trust = str(row.get("profile_trust_level", "")).strip().upper()
    probability = parse_probability(_first(row, PROBABILITY_COLUMNS))
    edge = _edge(row)
    price = parse_price(_first(row, PRICE_COLUMNS))
    if policy.require_ensemble_accept and ensemble_status and ensemble_status != "ACCEPT":
        reasons.append(f"ensemble_status_{ensemble_status.lower()}")
    if policy.reject_low_trust_profiles and trust == "LOW":
        reasons.append("low_trust_profile")
    if probability is None:
        reasons.append("missing_probability")
    elif probability < policy.min_probability:
        reasons.append("probability_below_minimum")
    if edge is None:
        reasons.append("missing_edge")
    elif edge < policy.min_edge:
        reasons.append("edge_below_minimum")
    if price is None:
        reasons.append("missing_price")
    return reasons


def apply_bankroll_exposure(rows: list[Mapping[str, Any]], policy: BankrollPolicy = BankrollPolicy()) -> list[dict[str, Any]]:
    ordered = sorted(list(rows), key=lambda row: (_score(row), parse_probability(_first(row, PROBABILITY_COLUMNS)) or 0.0), reverse=True)
    sport_exposure: dict[str, float] = {}
    league_exposure: dict[str, float] = {}
    market_exposure: dict[str, float] = {}
    team_exposure: dict[str, float] = {}
    daily_exposure = 0.0
    output: list[dict[str, Any]] = []

    for row in ordered:
        out = dict(row)
        reasons = _base_rejection_reasons(row, policy)
        probability = parse_probability(_first(row, PROBABILITY_COLUMNS))
        price = parse_price(_first(row, PRICE_COLUMNS))
        raw_stake = _kelly_units(probability, price, policy)
        if raw_stake < policy.min_stake_units:
            reasons.append("stake_below_minimum")
            raw_stake = 0.0

        sport = _norm(_first(row, SPORT_COLUMNS), "sport_unknown")
        league = _norm(_first(row, LEAGUE_COLUMNS), "league_unknown")
        market = _norm(_first(row, MARKET_COLUMNS), "market_unknown")
        team = _norm(_first(row, TEAM_COLUMNS), "team_unknown")
        warning: list[str] = []
        stake = raw_stake
        caps = [
            ("daily_exposure_cap", policy.max_daily_exposure_units - daily_exposure),
            ("sport_exposure_cap", policy.max_sport_exposure_units - sport_exposure.get(sport, 0.0)),
            ("league_exposure_cap", policy.max_league_exposure_units - league_exposure.get(league, 0.0)),
            ("market_exposure_cap", policy.max_market_exposure_units - market_exposure.get(market, 0.0)),
            ("team_exposure_cap", policy.max_team_exposure_units - team_exposure.get(team, 0.0)),
        ]
        for name, remaining in caps:
            if remaining <= 0:
                warning.append(name)
                stake = 0.0
            elif stake > remaining:
                warning.append(f"trimmed_by_{name}")
                stake = min(stake, remaining)

        if reasons:
            action = "REJECT"
            stake = 0.0
        elif stake >= policy.min_stake_units:
            action = "BET"
            daily_exposure += stake
            sport_exposure[sport] = sport_exposure.get(sport, 0.0) + stake
            league_exposure[league] = league_exposure.get(league, 0.0) + stake
            market_exposure[market] = market_exposure.get(market, 0.0) + stake
            team_exposure[team] = team_exposure.get(team, 0.0) + stake
        elif warning:
            action = "WATCH"
        else:
            action = "WATCH"
            reasons.append("no_positive_stake")

        out["recommended_stake_units"] = str(round(stake, 4))
        out["raw_kelly_stake_units"] = str(round(raw_stake, 4))
        out["risk_tier"] = _risk_tier(out, stake)
        out["exposure_warning"] = "; ".join(warning)
        out["bankroll_action"] = action
        out["do_not_bet_reason"] = "; ".join(reasons)
        output.append(out)
    return output


def summarize_bankroll(rows: list[Mapping[str, Any]], *, output_csv: str | None = None) -> BankrollReport:
    stakes = [_float(row.get("recommended_stake_units")) for row in rows if row.get("bankroll_action") == "BET"]
    stakes = [stake for stake in stakes if stake is not None]
    exposure_by_sport: dict[str, float] = {}
    exposure_by_league: dict[str, float] = {}
    exposure_by_market: dict[str, float] = {}
    exposure_by_team: dict[str, float] = {}
    for row in rows:
        if row.get("bankroll_action") != "BET":
            continue
        stake = _float(row.get("recommended_stake_units")) or 0.0
        for mapping, columns, fallback in [
            (exposure_by_sport, SPORT_COLUMNS, "sport_unknown"),
            (exposure_by_league, LEAGUE_COLUMNS, "league_unknown"),
            (exposure_by_market, MARKET_COLUMNS, "market_unknown"),
            (exposure_by_team, TEAM_COLUMNS, "team_unknown"),
        ]:
            key = _norm(_first(row, columns), fallback)
            mapping[key] = round(mapping.get(key, 0.0) + stake, 4)
    return BankrollReport(
        raw_rows=len(rows),
        bet_rows=sum(1 for row in rows if row.get("bankroll_action") == "BET"),
        watch_rows=sum(1 for row in rows if row.get("bankroll_action") == "WATCH"),
        rejected_rows=sum(1 for row in rows if row.get("bankroll_action") == "REJECT"),
        total_stake_units=round(sum(stakes), 4),
        average_stake_units=None if not stakes else round(sum(stakes) / len(stakes), 4),
        max_stake_units=None if not stakes else round(max(stakes), 4),
        exposure_by_sport=exposure_by_sport,
        exposure_by_league=exposure_by_league,
        exposure_by_market=exposure_by_market,
        exposure_by_team=exposure_by_team,
        output_csv=output_csv,
        notes=[
            "Stake sizing uses fractional Kelly capped by pick, sport, league, market, team and daily exposure limits.",
            "Rows are processed from strongest score to weakest so the best picks receive exposure first.",
        ],
    )


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_report(report: BankrollReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
