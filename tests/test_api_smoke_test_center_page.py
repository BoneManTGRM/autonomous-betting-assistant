import ast
from pathlib import Path

PAGE = Path("pages/api_smoke_test_center.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_api_smoke_page_imports_services():
    for token in ("build_api_smoke_report", "export_api_smoke_report_json", "parse_json_payload"):
        assert token in SOURCE


def test_api_smoke_page_exposes_controls():
    for token in (
        "api_smoke_workspace_id",
        "api_smoke_odds_response",
        "api_smoke_sportsdata_response",
        "api_smoke_weather_response",
        "api_smoke_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_api_smoke_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "status",
        "ready_provider_count",
        "review_provider_count",
        "missing_key_count",
        "no_sample_count",
        "preview_only",
        "proof_rows_changed",
        "key_readiness",
        "request_plans",
        "payload_analysis",
    ):
        assert token in SOURCE


def test_api_smoke_page_has_status_language():
    for token in ("API READY", "REVIEW REQUIRED", "MISSING KEYS", "NO SAMPLE RESPONSE", "PREVIEW ONLY", "NO PROOF ROWS CHANGED"):
        assert token in SOURCE


def test_api_smoke_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "odds_response",
        "sportsdata_response",
        "weather_response",
        "run",
        "ready",
        "review",
        "missing",
        "empty",
        "preview_only",
        "proof_safe",
        "summary",
        "keys",
        "plans",
        "payloads",
        "download",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_api_smoke_page_does_not_display_secret_values_directly():
    assert "display_value" in SOURCE
    assert "st.secrets" in SOURCE
    assert "st.write(st.secrets" not in SOURCE
    assert "st.json(st.secrets" not in SOURCE


def test_api_smoke_page_has_no_proof_change_or_external_call_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + ".", "append_" + "performance_rows", "sync_rows" + "_by_source", "approve_" + "ledger_import"):
        assert token not in SOURCE
