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
        "local_sim_match_threshold",
        "local_sim_review_threshold",
        "local_sim_verified_confidence",
        "local_sim_intake_review_confidence",
        "local_sim_locked_csv",
        "local_sim_provider_json",
        "local_sim_confirmation_json",
        "local_sim_value_json",
        "local_sim_shadow_csv",
        "local_sim_review_json",
        "local_sim_run",
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
        "matched_count",
        "package_changed_count",
        "verified_lane_count",
        "review_lane_count",
        "shadow_lane_count",
        "quarantine_lane_count",
        "official_metrics_row_count",
        "shadow_learning_row_count",
        "preview_only",
        "files_written",
        "live_changes",
        "stage_summary",
        "downloads",
    ):
        assert token in SOURCE


def test_local_sim_page_has_status_language():
    for token in ("SIMULATION READY", "REVIEW REQUIRED", "NO ROWS", "PREVIEW ONLY", "NO FILES WRITTEN", "NO LIVE CHANGES"):
        assert token in SOURCE


def test_local_sim_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "locked_csv",
        "provider_json",
        "confirmation_json",
        "value_json",
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
        "no_live",
        "summary",
        "stages",
        "downloads",
        "manifest",
        "download",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_local_sim_page_has_downloads():
    for token in ("aba_local_simulation_manifest_", "aba_local_simulation_", "st.download_button", "application/json", "text/csv"):
        assert token in SOURCE


def test_local_sim_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
