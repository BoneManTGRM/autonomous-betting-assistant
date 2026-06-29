import ast
from pathlib import Path

PAGE = Path("pages/local_update_simulation.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_local_sim_page_imports_services():
    for token in ("build_local_update_simulation_from_text", "export_simulation_manifest_json"):
        assert token in SOURCE


def test_local_sim_page_exposes_controls():
    for token in (
        "local_sim_workspace_id",
        "local_sim_locked_csv",
        "local_sim_provider_events",
        "local_sim_confirmation_json",
        "local_sim_value_json",
        "local_sim_odds_payload",
        "local_sim_sportsdata_payload",
        "local_sim_weather_payload",
        "local_sim_shadow_csv",
        "local_sim_review_json",
        "local_sim_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_local_sim_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "simulation_id",
        "simulation_hash",
        "status",
        "locked_row_count",
        "provider_event_count",
        "ready_provider_count",
        "matched_count",
        "package_changed_count",
        "intake_verified_count",
        "intake_review_count",
        "intake_shadow_count",
        "intake_quarantine_count",
        "preview_only",
        "files_written",
        "proof_rows_changed",
        "smoke_summary",
        "match_report",
        "offline_package",
        "adaptive_intake",
        "review_flags",
    ):
        assert token in SOURCE


def test_local_sim_page_has_status_language():
    for token in ("SIMULATION READY", "REVIEW REQUIRED", "NO ROWS", "PREVIEW ONLY", "NO FILES WRITTEN", "NO PROOF ROWS CHANGED"):
        assert token in SOURCE


def test_local_sim_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "locked_csv",
        "provider_events",
        "confirmation_json",
        "value_json",
        "odds_payload",
        "sportsdata_payload",
        "weather_payload",
        "shadow_csv",
        "review_json",
        "match_threshold",
        "review_threshold",
        "verified_confidence",
        "intake_review_confidence",
        "run",
        "ready",
        "review",
        "empty",
        "preview_only",
        "no_files",
        "safe",
        "summary",
        "smoke",
        "match",
        "package",
        "intake",
        "flags",
        "download",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_local_sim_page_has_download_manifest():
    assert "aba_local_update_simulation_" in SOURCE
    assert "application/json" in SOURCE


def test_local_sim_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
