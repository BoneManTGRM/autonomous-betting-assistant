import json

from autonomous_betting_agent import event_match_resolver as resolver


def _locked(event="A vs B", time="2026-06-29T20:00:00Z"):
    return {
        "proof_id": "p1",
        "sport": "tennis",
        "league": "wta",
        "event": event,
        "event_start_utc": time,
        "market_type": "moneyline",
        "selection": "A",
    }


def _provider(event="A vs B", time="2026-06-29T20:05:00Z"):
    return {
        "event_id": "e1",
        "sport": "tennis",
        "league": "wta",
        "event": event,
        "commence_time": time,
        "market_type": "moneyline",
        "selection": "A",
    }


def test_parse_csv_text_reads_locked_rows():
    rows = resolver.parse_csv_text("proof_id,event\np1,A vs B\n")
    assert rows == [{"proof_id": "p1", "event": "A vs B"}]


def test_parse_json_records_accepts_list_and_wrapped_events():
    direct = resolver.parse_json_records('[{"event":"A vs B"}]')
    wrapped = resolver.parse_json_records('{"events":[{"event":"A vs B"}]}')
    assert direct == [{"event": "A vs B"}]
    assert wrapped == [{"event": "A vs B"}]


def test_name_similarity_handles_related_text():
    assert resolver.name_similarity("A vs B", "A v B") > 0.7
    assert resolver.name_similarity("New York Liberty", "NY Liberty") > 0.5


def test_time_score_rewards_close_starts():
    assert resolver.time_score("2026-06-29T20:00:00Z", "2026-06-29T20:05:00Z") == 1.0
    assert resolver.time_score("2026-06-29T20:00:00Z", "2026-07-01T20:00:00Z") == 0.0


def test_score_candidate_combines_event_fields():
    scored = resolver.score_candidate(_locked(), _provider())
    assert scored["score"] > 0.9
    assert scored["name_score"] > 0.8
    assert scored["time_score"] == 1.0


def test_resolve_locked_row_matched_when_confident():
    row = resolver.resolve_locked_row(_locked(), [_provider()])
    assert row["status"] == "MATCHED"
    assert row["manual_review_required"] is False
    assert row["best_provider_event_id"]


def test_resolve_locked_row_low_confidence_when_partial_match():
    provider = _provider(event="A vs C")
    row = resolver.resolve_locked_row(_locked(), [provider], match_threshold=0.95, review_threshold=0.50)
    assert row["status"] in {"LOW CONFIDENCE", "MANUAL REVIEW"}
    assert row["manual_review_required"] is True


def test_resolve_locked_row_no_match_when_empty():
    row = resolver.resolve_locked_row(_locked(), [])
    assert row["status"] == "NO MATCH"
    assert row["manual_review_required"] is True


def test_resolve_locked_row_duplicate_match_when_two_close_candidates():
    row = resolver.resolve_locked_row(_locked(), [_provider(), {**_provider(), "event_id": "e2"}], duplicate_margin=0.03)
    assert row["status"] == "DUPLICATE MATCH"
    assert row["manual_review_required"] is True


def test_build_event_match_report_counts_statuses():
    report = resolver.build_event_match_report("test_01", [_locked()], [_provider()])
    assert report["schema_version"] == "event_match_resolver_v1"
    assert report["status"] == "MATCHED"
    assert report["matched_count"] == 1
    assert report["manual_review_count"] == 0
    assert report["preview_only"] is True
    assert report["proof_rows_changed"] == 0


def test_build_event_match_report_from_text_and_export():
    locked_csv = "proof_id,sport,league,event,event_start_utc,market_type,selection\np1,tennis,wta,A vs B,2026-06-29T20:00:00Z,moneyline,A\n"
    provider_json = json.dumps([_provider()])
    report = resolver.build_event_match_report_from_text("test_01", locked_csv, provider_json)
    payload = json.loads(resolver.export_event_match_report_json(report))
    assert payload["matched_count"] == 1


def test_event_match_resolver_uses_no_external_clients():
    source = open("autonomous_betting_agent/event_match_resolver.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
