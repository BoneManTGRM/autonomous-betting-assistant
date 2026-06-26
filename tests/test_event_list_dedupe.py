from copy import deepcopy

from autonomous_betting_agent.event_list_dedupe import (
    canonical_text,
    collapse_to_event_rows,
    event_duplicate_summary,
    event_group_key,
    row_market_key,
)


def test_event_group_key_groups_same_event_variants_but_keeps_market_keys_distinct():
    moneyline = {
        "event": "Mexico at Czech Republic",
        "event_start_utc": "2026-06-27T20:00:00Z",
        "prediction": "Mexico",
        "market_type": "moneyline",
    }
    total = {
        **moneyline,
        "prediction": "Over 2.5",
        "market_type": "totals",
        "line_point": 2.5,
    }

    assert event_group_key(moneyline) == event_group_key(total)
    assert row_market_key(moneyline) != row_market_key(total)


def test_event_group_key_normalizes_common_matchup_separators_and_accents():
    base = {"event": "México at Czech Republic", "event_date": "2026-06-27"}
    variants = [
        {"event": "Mexico vs Czech Republic", "event_date": "2026-06-27"},
        {"event": "Mexico v Czech Republic", "event_date": "2026-06-27"},
        {"event": "Mexico @ Czech Republic", "event_date": "2026-06-27"},
    ]

    assert canonical_text("México") == "mexico"
    assert all(event_group_key(base) == event_group_key(row) for row in variants)


def test_event_group_key_keeps_same_matchup_on_different_dates_separate():
    first = {"event": "Mexico at Czech Republic", "event_date": "2026-06-27"}
    second = {"event": "Mexico at Czech Republic", "event_date": "2026-06-28"}

    assert event_group_key(first) != event_group_key(second)


def test_event_group_key_uses_sport_league_context_when_start_time_missing():
    soccer = {"event": "Tigers at Lions", "sport": "Soccer", "league": "Friendly"}
    baseball = {"event": "Tigers at Lions", "sport": "Baseball", "league": "MLB"}
    soccer_variant = {"event": "Tigers vs Lions", "sport": "Soccer", "league": "Friendly"}

    assert event_group_key(soccer) == event_group_key(soccer_variant)
    assert event_group_key(soccer) != event_group_key(baseball)


def test_collapse_to_event_rows_keeps_one_display_row_per_event():
    rows = [
        {
            "event": "Mexico at Czech Republic",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Mexico",
            "market_type": "moneyline",
        },
        {
            "event": "Mexico at Czech Republic",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Over 2.5",
            "market_type": "totals",
        },
        {
            "event": "Germany at Ecuador",
            "event_start_utc": "2026-06-27T21:00:00Z",
            "prediction": "Germany",
            "market_type": "moneyline",
        },
    ]

    collapsed = collapse_to_event_rows(rows)

    assert [row["event"] for row in collapsed] == ["Mexico at Czech Republic", "Germany at Ecuador"]
    assert collapsed[0]["event_duplicate_count"] == 2
    assert collapsed[0]["event_market_count"] == 2


def test_collapse_to_event_rows_prefers_official_or_proof_backed_row():
    rows = [
        {
            "event": "Australia vs Paraguay",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Over 2.5",
            "market_type": "totals",
        },
        {
            "event": "Australia vs Paraguay",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Australia",
            "market_type": "moneyline",
            "proof_id": "proof-123",
        },
    ]

    collapsed = collapse_to_event_rows(rows)

    assert len(collapsed) == 1
    assert collapsed[0]["prediction"] == "Australia"
    assert collapsed[0]["proof_id"] == "proof-123"


def test_collapse_to_event_rows_prefers_spanish_official_action_label():
    rows = [
        {
            "event": "Austria vs Algeria",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Over 2.5",
            "market_type": "totals",
        },
        {
            "event": "Austria vs Algeria",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Austria",
            "market_type": "moneyline",
            "public_action": "Jugada oficial +EV",
        },
    ]

    collapsed = collapse_to_event_rows(rows)

    assert len(collapsed) == 1
    assert collapsed[0]["prediction"] == "Austria"
    assert collapsed[0]["public_action"] == "Jugada oficial +EV"


def test_collapse_to_event_rows_prefers_positive_edge_then_complete_price_probability():
    rows = [
        {
            "event": "Netherlands vs Tunisia",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Netherlands",
            "market_type": "moneyline",
            "decimal_price": 2.1,
            "model_probability": 0.51,
        },
        {
            "event": "Netherlands vs Tunisia",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Over 2.5",
            "market_type": "totals",
            "expected_value_per_unit": 0.04,
        },
    ]

    collapsed = collapse_to_event_rows(rows)

    assert collapsed[0]["prediction"] == "Over 2.5"


def test_collapse_to_event_rows_does_not_mutate_original_rows():
    rows = [
        {"event": "Mexico at Czech Republic", "event_date": "2026-06-27", "market_type": "moneyline"},
        {"event": "Mexico at Czech Republic", "event_date": "2026-06-27", "market_type": "totals"},
    ]
    original = deepcopy(rows)

    collapsed = collapse_to_event_rows(rows)

    assert rows == original
    assert "event_duplicate_count" in collapsed[0]
    assert "event_duplicate_count" not in rows[0]


def test_event_duplicate_summary_counts_extra_event_rows():
    rows = [
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "moneyline"},
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "totals"},
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "spread"},
        {"event": "Netherlands vs Tunisia", "event_start_utc": "2026-06-27T21:00:00Z", "market_type": "moneyline"},
    ]

    summary = event_duplicate_summary(rows)

    assert summary == {
        "total_rows": 4,
        "unique_events": 2,
        "duplicate_events": 1,
        "duplicate_event_rows": 2,
    }
