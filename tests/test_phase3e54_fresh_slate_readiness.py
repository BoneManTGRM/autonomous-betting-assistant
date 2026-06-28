from __future__ import annotations

from copy import deepcopy

import pandas as pd

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
from autonomous_betting_agent.advisory_odds_value_display import fresh_slate_readiness_check, proof_safety_comparison
from autonomous_betting_agent.ui_i18n import localize_dataframe

NOW = "2026-06-28T22:34:00Z"


def row(
    index: int,
    *,
    event_start_utc: str = "2026-06-29T22:00:00Z",
    odds_last_update: str | None = "2026-06-28T22:00:00Z",
    bookmaker: str = "Caliente",
    decimal_price: float | None = 2.05,
    model_probability: float | None = 0.56,
    market_type: str | None = "h2h",
    prediction: str | None = "Team A",
    completeness: str = "COMPLETE_MARKET",
    lr_model_loaded: bool | None = True,
) -> dict[str, object]:
    out: dict[str, object] = {
        "event": f"Future Game {index}",
        "sport": "basketball",
        "league": "test league",
        "event_start_utc": event_start_utc,
        "bookmaker": bookmaker,
        "advisory_market_completeness_status": completeness,
        "advisory_playable_status": "WATCHLIST_VALUE",
        "advisory_playable_reason": "fixture",
        "lock_ready": False,
        "official_lock_ready": False,
        "publish_ready": False,
        "proof_hash": f"hash-{index}",
        "proof_id": f"proof-{index}",
        "locked_at_utc": "2026-06-28T18:00:00Z",
        "result_status": "pending",
    }
    if odds_last_update is not None:
        out["odds_last_update"] = odds_last_update
    if decimal_price is not None:
        out["decimal_price"] = decimal_price
    if model_probability is not None:
        out["model_probability"] = model_probability
    if market_type is not None:
        out["market_type"] = market_type
    if prediction is not None:
        out["prediction"] = prediction
    if lr_model_loaded is not None:
        out["lr_model_loaded"] = lr_model_loaded
    return out


def historical_148_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(148):
        completeness = "COMPLETE_MARKET" if index < 55 else "INCOMPLETE_MARKET"
        item = row(
            index,
            event_start_utc="2026-06-22T12:00:00Z",
            bookmaker="consensus_average",
            completeness=completeness,
            lr_model_loaded=False,
        )
        item["advisory_playable_status"] = "BLOCKED_STALE_LINE"
        item["advisory_playable_reason"] = "event_start_time_is_not_future"
        rows.append(item)
    return rows


def test_complete_future_slate_gets_ready() -> None:
    result = fresh_slate_readiness_check([row(1), row(2)], now=NOW)
    assert result["readiness_status"] == "READY_FOR_ADVISORY_VALUE"
    assert result["readiness_score"] >= 95
    assert result["future_event_count"] == 2
    assert result["real_sportsbook_count"] == 2
    assert result["complete_market_count"] == 2


def test_historical_file_gets_historical_only() -> None:
    result = fresh_slate_readiness_check([row(1, event_start_utc="2026-06-22T12:00:00Z")], now=NOW)
    assert result["readiness_status"] == "HISTORICAL_ONLY"
    assert result["future_event_count"] == 0
    assert result["historical_or_started_event_count"] == 1


def test_missing_decimal_odds_gets_missing_critical_fields() -> None:
    result = fresh_slate_readiness_check([row(1, decimal_price=None)], now=NOW)
    assert result["readiness_status"] == "MISSING_CRITICAL_FIELDS"
    assert "decimal_odds_field_present" in result["critical_missing_fields"]


def test_consensus_only_file_gets_needs_real_sportsbook_prices() -> None:
    result = fresh_slate_readiness_check([row(1, bookmaker="consensus_average")], now=NOW)
    assert result["readiness_status"] == "NEEDS_REAL_SPORTSBOOK_PRICES"
    assert result["real_sportsbook_count"] == 0
    assert result["consensus_only_count"] == 1


def test_incomplete_market_gets_needs_complete_markets() -> None:
    result = fresh_slate_readiness_check([row(1, completeness="INCOMPLETE_MARKET")], now=NOW)
    assert result["readiness_status"] == "NEEDS_COMPLETE_MARKETS"
    assert result["complete_market_count"] == 0
    assert result["incomplete_market_count"] == 1


def test_shadow_required_gets_needs_shadow_training_when_not_ready() -> None:
    result = fresh_slate_readiness_check([row(1, lr_model_loaded=False)], now=NOW, require_shadow_ready=True)
    assert result["readiness_status"] == "NEEDS_SHADOW_TRAINING"
    assert result["shadow_readiness_status"] == "NO_MODEL_LOADED"


def test_shadow_not_required_does_not_force_training_status() -> None:
    result = fresh_slate_readiness_check([row(1, lr_model_loaded=False)], now=NOW, require_shadow_ready=False)
    assert result["readiness_status"] == "READY_FOR_ADVISORY_VALUE"
    assert result["shadow_readiness_status"] == "NO_MODEL_LOADED"
    assert any("Shadow model" in warning for warning in result["warnings"])


def test_timestamp_fields_are_separated() -> None:
    result = fresh_slate_readiness_check([row(1, odds_last_update=None)], now=NOW)
    assert result["readiness_status"] == "MISSING_CRITICAL_FIELDS"
    assert result["event_start_fields_detected"] == ["event_start_utc"]
    assert result["odds_freshness_fields_detected"] == []
    assert "Event-start fields are used only" in result["timestamp_rule_confirmation"]


def test_historical_148_row_style_file_is_not_ready() -> None:
    result = fresh_slate_readiness_check(historical_148_rows(), now=NOW)
    assert result["readiness_status"] == "HISTORICAL_ONLY"
    assert result["readiness_status"] != "READY_FOR_ADVISORY_VALUE"
    assert result["future_event_count"] == 0
    assert result["historical_or_started_event_count"] == 148


def test_readiness_checker_does_not_mutate_proof_or_official_fields_or_row_count() -> None:
    rows = [row(1), row(2, bookmaker="Playdoit")]
    before = deepcopy(rows)
    result = fresh_slate_readiness_check(rows, now=NOW)
    assert rows == before
    assert result["proof_safety_check_result"]["passed"] is True
    assert proof_safety_comparison(before, rows)["passed"] is True
    assert len(rows) == len(before)


def test_spanish_advisory_labels_still_resolve() -> None:
    frame = pd.DataFrame([{"advisory_playable_status": "WATCHLIST_VALUE", "advisory_market_completeness_status": "COMPLETE_MARKET"}])
    localized = localize_dataframe(frame, "es")
    assert any("asesor" in column.lower() for column in localized.columns)
    assert localized.iloc[0, 0] in {"WATCHLIST VALOR", "WATCHLIST_VALUE"}
