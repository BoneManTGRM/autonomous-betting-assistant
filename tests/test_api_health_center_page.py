import ast
from pathlib import Path

PAGE = Path("pages/api_health_center.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_api_health_center_page_imports_read_only_services():
    for token in (
        "build_api_health_report",
        "export_api_health_report_json",
        "validate_api_health_report",
    ):
        assert token in SOURCE


def test_api_health_center_page_exposes_controls():
    for token in (
        "api_health_workspace_id",
        "api_health_provider",
        "api_health_status_code",
        "api_health_success_count",
        "api_health_error_count",
        "api_health_records_count",
        "api_health_latency_ms",
        "api_health_data_age_minutes",
        "api_health_fallback_active",
        "api_health_context_available",
        "api_health_odds_available",
        "api_health_add_event",
        "api_health_clear_events",
        "api_health_run_health_check",
    ):
        assert token in SOURCE


def test_api_health_center_page_displays_required_report_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "data_complete",
        "check_count",
        "provider_count",
        "down_provider_count",
        "stale_provider_count",
        "fallback_provider_count",
        "degraded_provider_count",
        "provider_results",
        "warning_count",
        "error_count",
    ):
        assert token in SOURCE


def test_api_health_center_page_has_clear_status_language():
    for token in (
        "API OK",
        "API DEGRADED",
        "API STALE",
        "API DOWN",
        "FALLBACK ACTIVE",
        "REPORT NOT DATA-COMPLETE",
        "DATA COMPLETE",
        "DATA INCOMPLETE",
    ):
        assert token in SOURCE


def test_api_health_center_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_api_health_report_json(report, public_safe=True).encode" in SOURCE
    assert "api_health_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_api_health_center_page_uses_in_memory_events_only():
    assert "API_HEALTH_EVENTS_KEY" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_api_health_center_page_has_no_network_or_mutation_paths():
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "update_result",
        "delete_proof",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_api_health_center_page_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "provider",
        "status_code",
        "success_count",
        "error_count",
        "records_count",
        "latency_ms",
        "data_age_minutes",
        "fallback_active",
        "context_available",
        "odds_available",
        "add_event",
        "clear_events",
        "run_health_check",
        "event_ready",
        "events_cleared",
        "report_ready",
        "api_ok",
        "api_degraded",
        "api_stale",
        "api_down",
        "fallback_active_status",
        "report_not_complete",
        "data_complete",
        "data_incomplete",
        "usage_events",
        "provider_results",
        "report_summary",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_api_health_center_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
