from __future__ import annotations

from copy import deepcopy

import pandas as pd

from autonomous_betting_agent.advisory_odds_value_display import (
    PLAYABLE_PLUS_EV,
    advisory_csv_frame,
    advisory_report_text,
    advisory_rows,
    fresh_slate_readiness_check,
    line_shopping_summary,
    proof_safety_comparison,
    sportsbook_source_summary,
)
from autonomous_betting_agent.advisory_sportsbook_sources import (
    CONSENSUS_ONLY,
    REAL_SPORTSBOOK,
    UNKNOWN_SOURCE,
    add_sportsbook_source_fields,
    normalize_sportsbook_source,
)

NOW = "2026-06-28T22:34:00Z"


def base_row(index: int, *, bookmaker: object = "Caliente", decimal_price: float = 2.1) -> dict[str, object]:
    return {
        "event": "Team A vs Team B",
        "sport": "basketball",
        "league": "test league",
        "market_type": "h2h",
        "prediction": "Team A",
        "bookmaker": bookmaker,
        "decimal_price": decimal_price,
        "model_probability": 0.56,
        "event_start_utc": "2026-06-29T22:00:00Z",
        "odds_last_update": "2026-06-28T22:20:00Z",
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_playable_status": "WATCHLIST_VALUE",
        "advisory_playable_reason": "fixture",
        "lock_ready": False,
        "official_lock_ready": False,
        "publish_ready": False,
        "proof_hash": f"hash-{index}",
        "proof_id": f"proof-{index}",
        "locked_at_utc": "2026-06-28T18:00:00Z",
    }


def positive_ev_precomputed(bookmaker: object) -> dict[str, object]:
    row = base_row(1, bookmaker=bookmaker, decimal_price=2.4)
    row.update({
        "advisory_playable_status": PLAYABLE_PLUS_EV,
        "advisory_raw_EV": 0.25,
        "advisory_best_price_EV": 0.25,
        "advisory_no_vig_edge": 0.05,
        "advisory_current_decimal_odds": 2.4,
        "advisory_best_available_decimal_odds": 2.4,
        "advisory_best_available_sportsbook": str(bookmaker or ""),
        "advisory_odds_value_tier": "PLAYABLE",
    })
    return row


def test_mexican_sportsbooks_classified_real_and_labels_preserved() -> None:
    for label in ["Caliente", "Playdoit", "Codere"]:
        normalized = normalize_sportsbook_source(label)
        assert normalized["source_type"] == REAL_SPORTSBOOK
        assert normalized["original_label"] == label
    assert normalize_sportsbook_source("Caliente MX")["normalized_sportsbook"] == "caliente"
    assert normalize_sportsbook_source("Playdoit")["normalized_sportsbook"] == "playdoit"
    assert normalize_sportsbook_source("codere")["normalized_sportsbook"] == "codere"


def test_consensus_and_unknown_sources_classified_correctly() -> None:
    for label in ["consensus_average", "market_average", "average"]:
        normalized = normalize_sportsbook_source(label)
        assert normalized["source_type"] == CONSENSUS_ONLY
        assert normalized["is_consensus_source"] is True
    for label in ["", None, "unknown"]:
        normalized = normalize_sportsbook_source(label)
        assert normalized["source_type"] == UNKNOWN_SOURCE


def test_consensus_only_rows_do_not_count_as_real_sportsbook_coverage() -> None:
    rows = add_sportsbook_source_fields([base_row(1, bookmaker="consensus_average")])
    assert rows[0]["advisory_sportsbook_source_type"] == CONSENSUS_ONLY
    assert rows[0]["advisory_is_real_sportsbook"] is False
    readiness = fresh_slate_readiness_check(rows, now=NOW)
    assert readiness["real_sportsbook_count"] == 0
    assert readiness["consensus_only_count"] == 1
    assert readiness["readiness_status"] == "NEEDS_REAL_SPORTSBOOK_PRICES"


def test_one_real_sportsbook_gets_one_book_status() -> None:
    rows = add_sportsbook_source_fields([base_row(1, bookmaker="Caliente")])
    assert rows[0]["advisory_line_shopping_source_status"] == "LINE_SHOPPING_UNAVAILABLE_ONE_BOOK"


def test_two_real_sportsbooks_get_line_shopping_available() -> None:
    rows = add_sportsbook_source_fields([base_row(1, bookmaker="Caliente", decimal_price=2.05), base_row(2, bookmaker="Playdoit", decimal_price=2.15)])
    assert {row["advisory_line_shopping_source_status"] for row in rows} == {"LINE_SHOPPING_AVAILABLE"}


def test_best_price_uses_real_sportsbooks_not_consensus() -> None:
    rows = advisory_rows([
        base_row(1, bookmaker="Caliente", decimal_price=2.05),
        base_row(2, bookmaker="Playdoit", decimal_price=2.15),
        base_row(3, bookmaker="consensus_average", decimal_price=9.99),
    ])
    for row in rows:
        assert row["advisory_best_available_sportsbook"] == "Playdoit"
        assert row["advisory_best_available_decimal_odds"] == 2.15
    summary = line_shopping_summary(rows)
    assert "consensus_average" not in set(summary["advisory_best_available_sportsbook"].dropna().astype(str))


def test_consensus_and_unknown_positive_ev_rows_are_not_playable() -> None:
    consensus = advisory_rows([positive_ev_precomputed("consensus_average")])[0]
    unknown = advisory_rows([positive_ev_precomputed(None)])[0]
    assert consensus["advisory_playable_status"] != PLAYABLE_PLUS_EV
    assert consensus["advisory_playable_reason"] == "source_is_consensus_not_real_sportsbook"
    assert unknown["advisory_playable_status"] != PLAYABLE_PLUS_EV
    assert unknown["advisory_playable_reason"] == "source_is_unknown_or_missing"


def test_advisory_csv_and_report_include_source_fields_and_summary() -> None:
    rows = advisory_rows([base_row(1, bookmaker="Caliente"), base_row(2, bookmaker="consensus_average")])
    csv = advisory_csv_frame(rows)
    assert "advisory_sportsbook_source_type" in csv.columns
    assert "advisory_line_shopping_source_status" in csv.columns
    report = advisory_report_text(rows)
    assert "Sportsbook Source Summary" in report
    assert "REAL_SPORTSBOOK" in report
    assert "CONSENSUS_ONLY" in report


def test_sportsbook_source_summary_does_not_mutate_proof_or_official_fields() -> None:
    rows = [base_row(1, bookmaker="Caliente"), base_row(2, bookmaker="Playdoit")]
    before = deepcopy(rows)
    summary = sportsbook_source_summary(rows)
    assert not summary.empty
    assert rows == before
    assert proof_safety_comparison(before, rows)["passed"] is True
