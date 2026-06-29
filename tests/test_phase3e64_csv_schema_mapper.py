from __future__ import annotations

from copy import deepcopy

import pandas as pd

from autonomous_betting_agent.csv_schema_mapper import (
    SCHEMA_MISSING_REQUIRED_FIELDS,
    SCHEMA_PARTIAL,
    SCHEMA_READY,
    detect_column_mappings,
    map_and_repair_frame,
    normalize_decimal_odds,
    normalize_market,
    normalize_probability,
    normalize_result,
    schema_mapper_report_section,
    schema_mapper_summary,
)


def test_common_aliases_map_to_canonical_schema():
    frame = pd.DataFrame([
        {
            "matchup": "Team A vs Team B",
            "pick": "Team A",
            "bet_type": "moneyline",
            "casino": "Caliente",
            "odds": "+150",
            "confidence": "72%",
            "resultado": "ganada",
        }
    ])
    repaired = map_and_repair_frame(frame)
    row = repaired.iloc[0].to_dict()
    assert row["event"] == "Team A vs Team B"
    assert row["prediction"] == "Team A"
    assert row["market_type"] == "h2h"
    assert row["bookmaker"] == "Caliente"
    assert row["decimal_odds"] == 2.5
    assert row["model_probability"] == 0.72
    assert row["result"] == "win"
    assert row["schema_mapper_status"] == SCHEMA_READY
    assert bool(row["schema_mapper_ready_for_advisory_pipeline"]) is True


def test_missing_required_fields_detected_safely():
    frame = pd.DataFrame([{"matchup": "Team A vs Team B", "odds": "2.10"}])
    repaired = map_and_repair_frame(frame)
    missing = repaired.iloc[0]["schema_mapper_missing_required_fields"]
    assert repaired.iloc[0]["schema_mapper_status"] == SCHEMA_MISSING_REQUIRED_FIELDS
    assert "prediction" in missing
    assert "market_type" in missing
    assert "bookmaker" in missing
    assert "model_probability" in missing
    assert bool(repaired.iloc[0]["schema_mapper_ready_for_advisory_pipeline"]) is False


def test_probability_and_decimal_odds_normalize_safely():
    assert normalize_probability("72%") == 0.72
    assert normalize_probability("72") == 0.72
    assert normalize_probability("0.72") == 0.72
    assert normalize_probability("bad") is None
    assert normalize_decimal_odds("2.10") == 2.1
    assert normalize_decimal_odds("+150") == 2.5
    assert normalize_decimal_odds("-120") == 1.833333
    assert normalize_decimal_odds("bad") is None


def test_result_and_market_aliases_normalize():
    assert normalize_result("W") == "win"
    assert normalize_result("perdida") == "loss"
    assert normalize_result("void") == "cancel"
    assert normalize_market("moneyline") == "h2h"
    assert normalize_market("over/under") == "totals"


def test_duplicate_rows_are_detected_without_blocking_export():
    frame = pd.DataFrame([
        {
            "event": "Same Game",
            "prediction": "Team A",
            "market_type": "h2h",
            "bookmaker": "Caliente",
            "decimal_odds": 2.0,
            "model_probability": 0.6,
            "event_start_utc": "2099-01-01T00:00:00Z",
        },
        {
            "event": "Same Game",
            "prediction": "Team A",
            "market_type": "h2h",
            "bookmaker": "Caliente",
            "decimal_odds": 2.0,
            "model_probability": 0.6,
            "event_start_utc": "2099-01-01T00:00:00Z",
        },
    ])
    repaired = map_and_repair_frame(frame)
    assert repaired.iloc[0]["schema_mapper_status"] == SCHEMA_PARTIAL
    assert int(repaired.iloc[0]["schema_mapper_duplicate_count"]) == 2
    assert bool(repaired.iloc[0]["schema_mapper_ready_for_advisory_pipeline"]) is True


def test_original_input_not_mutated_and_summary_report_export_fields_exist():
    frame = pd.DataFrame([
        {
            "matchup": "Team A vs Team B",
            "selection": "Team A",
            "market": "ml",
            "book": "Codere",
            "price": "2.20",
            "probability": "61%",
            "extra_note": "keep me",
        }
    ])
    before = deepcopy(frame.to_dict("records"))
    mappings = detect_column_mappings(frame.columns)
    repaired = map_and_repair_frame(frame)
    summary = schema_mapper_summary(frame)
    report = schema_mapper_report_section(frame)
    assert frame.to_dict("records") == before
    assert mappings["event"] == "matchup"
    assert "schema_mapper_status" in repaired.columns
    assert "schema_mapper_applied_mappings" in repaired.columns
    assert "extra_note" in repaired.columns
    assert int(summary.iloc[0]["ready_rows"]) == 1
    assert "CSV Schema Mapper" in report
    assert "Original upload is not modified in place" in report
