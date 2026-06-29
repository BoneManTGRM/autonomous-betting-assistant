import ast
from pathlib import Path

PAGE = Path("pages/guarded_approval_layer.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_guarded_approval_page_imports_services():
    for token in ("build_guarded_approval_package_from_text", "export_approval_manifest_json", "REQUIRED_PHRASE"):
        assert token in SOURCE


def test_guarded_approval_page_exposes_controls():
    for token in (
        "guarded_approval_workspace_id",
        "guarded_approval_operator_name",
        "guarded_approval_note",
        "guarded_approval_phrase",
        "guarded_approval_base_csv",
        "guarded_approval_candidate_csv",
        "guarded_approval_manifest_json",
        "guarded_approval_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_guarded_approval_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "approval_id",
        "approval_hash",
        "status",
        "base_row_count",
        "candidate_row_count",
        "changed_row_count",
        "blocked_reason_count",
        "approval_phrase_required",
        "approval_phrase_matched",
        "preview_only",
        "files_written",
        "live_changes",
        "diff_rows",
        "blocked_reasons",
    ):
        assert token in SOURCE


def test_guarded_approval_page_has_status_language():
    for token in ("APPROVED PACKAGE", "APPROVAL BLOCKED", "NO ROWS", "PREVIEW ONLY", "NO FILES WRITTEN", "NO LIVE CHANGES"):
        assert token in SOURCE


def test_guarded_approval_page_has_downloads():
    for token in (
        "backup_csv",
        "approved_csv",
        "rollback_csv",
        "audit_json",
        "aba_guarded_approval_manifest_",
        "aba_guarded_approval_backup_",
        "aba_guarded_approval_approved_",
        "aba_guarded_approval_rollback_",
        "aba_guarded_approval_audit_",
    ):
        assert token in SOURCE


def test_guarded_approval_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "base_csv",
        "candidate_csv",
        "manifest_json",
        "operator_name",
        "approval_note",
        "approval_phrase",
        "required_phrase",
        "run",
        "approved",
        "blocked",
        "empty",
        "preview_only",
        "no_files",
        "no_live",
        "summary",
        "diff_rows",
        "blocked_reasons",
        "manifest",
        "backup",
        "approved_csv",
        "rollback",
        "audit",
        "no_package",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_guarded_approval_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
