import ast
from pathlib import Path

PAGE = Path("pages/proof_archive_viewer.py")
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


def test_proof_archive_viewer_imports_read_only_archive_services():
    for token in (
        "build_proof_archive_snapshot",
        "build_proof_archive_index",
        "compare_proof_archive_snapshots",
        "validate_proof_archive_snapshot",
        "export_proof_archive_snapshot_json",
        "export_proof_archive_index_json",
    ):
        assert token in SOURCE


def test_proof_archive_viewer_exposes_snapshot_and_index_controls():
    for token in (
        "proof_archive_workspace_id",
        "proof_archive_package_type",
        "proof_archive_build_snapshot",
        "proof_archive_build_index",
        "PROOF_ARCHIVE_PACKAGE_TYPES",
    ):
        assert token in SOURCE


def test_proof_archive_viewer_displays_version_history_fields():
    for token in (
        "archive_id",
        "archive_hash",
        "created_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "private_export_hash",
        "qa_report_id",
        "qa_report_hash",
        "proof_ready",
        "proof_grade",
        "overall_passed",
        "archive_status",
        "redaction_passed",
    ):
        assert token in SOURCE


def test_proof_archive_viewer_has_version_comparison_and_baseline_control():
    assert "compare_proof_archive_snapshots(previous, snapshot)" in SOURCE
    assert "proof_archive_store_previous" in SOURCE
    assert "PROOF_ARCHIVE_VIEWER_PREVIOUS_KEY" in SOURCE


def test_proof_archive_viewer_downloads_are_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_proof_archive_snapshot_json(snapshot, public_safe=True).encode" in SOURCE
    assert "export_proof_archive_index_json(index, public_safe=True).encode" in SOURCE
    assert "proof_archive_snapshot_json_{safe_text(snapshot.get('archive_hash'))}" in SOURCE
    assert "proof_archive_index_json_{safe_text(index.get('archive_index_hash'))}" in SOURCE
    assert "_snapshot_filename(snapshot)" in SOURCE
    assert "_index_filename(index)" in SOURCE


def test_proof_archive_viewer_private_internal_labeling_exists():
    assert "PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES" in SOURCE
    assert "private_internal_only" in SOURCE
    assert "PRIVATE/INTERNAL ONLY" in SOURCE
    assert "public_client_safe" in SOURCE
    assert "PUBLIC/CLIENT SAFE" in SOURCE


def test_proof_archive_viewer_no_write_or_mutation_paths():
    forbidden = (
        "approve_ledger_import",
        "preview_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_proof_archive_viewer_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "package_type",
        "build_snapshot",
        "build_index",
        "snapshot_ready",
        "index_ready",
        "archive_summary",
        "archive_index",
        "version_compare",
        "private_internal_only",
        "public_client_safe",
        "archive_ready",
        "archive_failed",
        "validation",
        "download_snapshot",
        "download_index",
        "store_previous",
        "no_snapshot",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_proof_archive_viewer_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
