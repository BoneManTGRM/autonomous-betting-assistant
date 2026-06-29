import ast
from pathlib import Path

PAGE = Path("pages/offline_update_package_builder.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_offline_package_page_imports_services():
    for token in ("build_offline_update_package_from_text", "export_package_manifest_json"):
        assert token in SOURCE


def test_offline_package_page_exposes_controls_and_downloads():
    for token in (
        "offline_package_workspace_id",
        "offline_package_locked_csv",
        "offline_package_match_report_json",
        "offline_package_confirmation_json",
        "offline_package_value_json",
        "offline_package_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_offline_package_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "package_id",
        "package_hash",
        "status",
        "locked_row_count",
        "changed_row_count",
        "manual_review_count",
        "verified_learning_count",
        "preview_only",
        "files_written",
        "diff_rows",
        "manual_review_rows",
        "verified_learning_rows",
    ):
        assert token in SOURCE


def test_offline_package_page_has_status_language():
    for token in ("PACKAGE READY", "REVIEW REQUIRED", "NO ROWS", "PREVIEW ONLY", "NO FILES WRITTEN"):
        assert token in SOURCE


def test_offline_package_page_has_all_downloads():
    for token in (
        "backup_csv",
        "updated_csv_preview",
        "rollback_csv",
        "audit_json",
        "aba_offline_package_manifest_",
        "aba_offline_package_backup_",
        "aba_offline_package_updated_preview_",
        "aba_offline_package_rollback_",
        "aba_offline_package_audit_",
    ):
        assert token in SOURCE


def test_offline_package_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "locked_csv",
        "match_report_json",
        "confirmation_json",
        "value_json",
        "run",
        "ready",
        "review",
        "empty",
        "preview_only",
        "no_files",
        "summary",
        "diff_rows",
        "review_rows",
        "learning_rows",
        "manifest",
        "backup",
        "updated",
        "rollback",
        "audit",
        "no_package",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_offline_package_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
