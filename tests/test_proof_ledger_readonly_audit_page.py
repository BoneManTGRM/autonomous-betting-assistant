import ast
from pathlib import Path

PAGE = Path("pages/proof_ledger_readonly_audit.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_proof_audit_page_imports_services():
    for token in (
        "build_proof_ledger_readonly_audit_from_text",
        "export_proof_audit_json",
        "export_proof_audit_checks_csv",
        "export_proof_audit_summaries_csv",
        "export_proof_audit_duplicates_csv",
        "export_proof_audit_manifest_json",
    ):
        assert token in SOURCE


def test_proof_audit_page_exposes_controls():
    for token in (
        "proof_audit_workspace_id",
        "proof_audit_proof_csv",
        "proof_audit_learning_csv",
        "proof_audit_dashboard_csv",
        "proof_audit_decision_csv",
        "proof_audit_page_csv",
        "proof_audit_store_csv",
        "proof_audit_dashboard_json",
        "proof_audit_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_proof_audit_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "audit_id",
        "audit_hash",
        "mode",
        "audit_status",
        "pass_count",
        "warn_count",
        "fail_count",
        "proof_row_count",
        "learning_row_count",
        "dashboard_row_count",
        "decision_row_count",
        "page_inventory_count",
        "store_inventory_count",
        "audit_checks",
        "dataset_summaries",
        "duplicate_event_groups",
        "page_inventory",
        "store_inventory",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_proof_audit_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "proof_csv",
        "learning_csv",
        "dashboard_csv",
        "decision_csv",
        "page_csv",
        "store_csv",
        "dashboard_json",
        "run",
        "summary",
        "checks",
        "datasets",
        "duplicates",
        "pages",
        "stores",
        "safety",
        "download_json",
        "download_checks",
        "download_summaries",
        "download_duplicates",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_proof_audit_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
