import json

from autonomous_betting_agent import api_health_service as health


def test_normalize_api_health_provider_aliases_and_unknowns():
    assert health.normalize_api_health_provider("odds_api") == "the_odds_api"
    assert health.normalize_api_health_provider("Sports Data IO") == "sportsdataio"
    assert health.normalize_api_health_provider("weather") == "weatherapi"
    assert health.normalize_api_health_provider("px") == "perplexity"
    assert health.normalize_api_health_provider("not-real") == "unknown"


def test_classify_api_health_event_api_ok():
    result = health.classify_api_health_event({
        "provider": "the_odds_api",
        "status_code": 200,
        "success_count": 1,
        "error_count": 0,
        "records_count": 20,
        "data_age_minutes": 5,
    })

    assert result["status"] == "API OK"
    assert result["data_complete"] is True


def test_classify_api_health_event_down_when_all_checks_fail():
    result = health.classify_api_health_event({
        "provider": "the_odds_api",
        "status_code": 500,
        "success_count": 0,
        "error_count": 2,
    })

    assert result["status"] == "API DOWN"
    assert result["data_complete"] is False
    assert result["reasons"]


def test_classify_api_health_event_stale_when_data_age_exceeds_limit():
    result = health.classify_api_health_event({
        "provider": "the_odds_api",
        "status_code": 200,
        "success_count": 1,
        "data_age_minutes": 60,
    })

    assert result["status"] == "API STALE"
    assert result["data_complete"] is False


def test_classify_api_health_event_fallback_active():
    result = health.classify_api_health_event({
        "provider": "sportsdataio",
        "status_code": 200,
        "success_count": 1,
        "fallback_active": True,
    })

    assert result["status"] == "FALLBACK ACTIVE"
    assert result["data_complete"] is False


def test_classify_api_health_event_degraded_when_missing_context_or_slow():
    missing_context = health.classify_api_health_event({
        "provider": "perplexity",
        "status_code": 200,
        "success_count": 1,
        "context_available": False,
    })
    slow = health.classify_api_health_event({
        "provider": "newsapi",
        "status_code": 200,
        "success_count": 1,
        "latency_ms": 9000,
    })

    assert missing_context["status"] == "API DEGRADED"
    assert slow["status"] == "API DEGRADED"


def test_summarize_api_health_events_rolls_up_provider_statuses():
    summary = health.summarize_api_health_events([
        {"provider": "the_odds_api", "status_code": 200, "success_count": 1, "data_age_minutes": 5},
        {"provider": "sportsdataio", "status_code": 500, "success_count": 0, "error_count": 1},
        {"provider": "weatherapi", "status_code": 200, "success_count": 1, "fallback_active": True},
    ])

    assert summary["check_count"] == 3
    assert summary["provider_count"] == 3
    assert summary["down_provider_count"] == 1
    assert summary["fallback_provider_count"] == 1
    assert summary["data_complete"] is False


def test_build_api_health_report_marks_down_and_not_data_complete():
    report = health.build_api_health_report("client-a", [
        {"provider": "sportsdataio", "status_code": 500, "success_count": 0, "error_count": 1},
    ])

    assert report["status"] == "API DOWN"
    assert report["overall_passed"] is False
    assert report["data_complete"] is False
    assert report["down_provider_count"] == 1
    assert report["report_hash"].startswith("api_health_hash_")


def test_build_api_health_report_allows_degraded_but_not_complete():
    report = health.build_api_health_report("client-a", [
        {"provider": "newsapi", "status_code": 200, "success_count": 1, "latency_ms": 9000},
    ])

    assert report["status"] == "API DEGRADED"
    assert report["overall_passed"] is True
    assert report["data_complete"] is False
    assert report["degraded_provider_count"] == 1


def test_api_health_report_hash_stable_when_generated_at_changes():
    report = health.build_api_health_report("client-a", [{"provider": "weatherapi", "status_code": 200, "success_count": 1}])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_status = dict(report, status="API DOWN")

    assert health.build_api_health_report_hash(report) == health.build_api_health_report_hash(changed_time)
    assert health.build_api_health_report_hash(report) != health.build_api_health_report_hash(changed_status)


def test_validate_api_health_report_blocks_overstated_pass_and_data_complete():
    report = health.build_api_health_report("client-a", [{"provider": "the_odds_api", "status_code": 500, "success_count": 0, "error_count": 1}])
    overstated = dict(report, overall_passed=True, data_complete=True)
    overstated["report_hash"] = health.build_api_health_report_hash(overstated)

    result = health.validate_api_health_report(overstated)

    assert result["passed"] is False
    joined = "\n".join(result["errors"])
    assert "overall_passed" in joined or "data_complete" in joined


def test_export_api_health_report_json_is_sanitized():
    report = health.build_api_health_report("client-a", [{"provider": "not-real", "status_code": 0, "error_count": 1}])
    payload = json.loads(health.export_api_health_report_json(report, public_safe=True))

    assert "events" not in payload
    assert "errors" not in payload
    assert "provider_results" in payload
    assert payload["error_count"] >= 1


def test_api_health_service_has_no_write_or_network_paths():
    source = open("autonomous_betting_agent/api_health_service.py", encoding="utf-8").read()
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
