import ast
from pathlib import Path

PAGE = Path("pages/proof_hardening_closeout.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_proof_closeout_page_imports_services():
    for token in (
        "build_proof_hardening_closeout_from_text",
        "export_closeout_json",
        "export_evidence_summary_csv",
        "export_closeout_checks_csv",
        "export_closeout_manifest_json",
    ):
        assert token in SOURCE


def test_proof_closeout_page_exposes_controls():
    for token in (
        "proof_closeout_workspace_id",
        "proof_closeout_canonical_json",
        "proof_closeout_restart_json",
        "proof_closeout_readonly_json",
        "proof_closeout_wiring_json",
        "proof_closeout_dashboard_json",
        "proof_closeout_review_json",
        "proof_closeout_operator_ack",
        "proof_closeout_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_proof_closeout_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "closeout_id",
        "closeout_hash",
        "mode",
        "closeout_status",
        "issue_21_recommendation",
        "operator_acknowledged",
        "evidence_summaries",
        "closeout_checks",
        "next_actions",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_proof_closeout_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "canonical",
        "restart",
        "readonly",
        "wiring",
        "dashboard",
        "review",
        "ack",
        "run",
        "summary",
        "evidence",
        "checks",
        "actions",
        "safety",
        "download_json",
        "download_evidence",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_proof_closeout_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
