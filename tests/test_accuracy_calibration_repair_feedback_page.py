import ast
from pathlib import Path

PAGE = Path("pages/accuracy_calibration_repair_feedback.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_accuracy_calibration_page_imports_services():
    for token in (
        "build_accuracy_calibration_feedback_report_from_text",
        "export_accuracy_calibration_json",
        "export_calibrated_preview_csv",
        "export_evaluation_preview_csv",
        "export_repair_feedback_csv",
    ):
        assert token in SOURCE


def test_accuracy_calibration_page_exposes_controls():
    for token in (
        "accuracy_calibration_workspace_id",
        "accuracy_calibration_min_segment",
        "accuracy_calibration_shrinkage",
        "accuracy_calibration_ev_buffer",
        "accuracy_calibration_safety_margin",
        "accuracy_calibration_current_csv",
        "accuracy_calibration_history_csv",
        "accuracy_calibration_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_accuracy_calibration_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "calibration_id",
        "calibration_hash",
        "mode",
        "decision",
        "decision_reason",
        "current_row_count",
        "history_row_count",
        "training_rows",
        "evaluation_rows",
        "baseline_brier_score",
        "calibrated_brier_score",
        "brier_improvement",
        "baseline_log_loss",
        "calibrated_log_loss",
        "log_loss_improvement",
        "calibration_error_improvement",
        "playable_count",
        "blocked_count",
        "repair_feedback_count",
        "calibration_model",
        "calibrated_preview_rows",
        "evaluation_preview_rows",
        "repair_feedback",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_accuracy_calibration_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "current_csv",
        "history_csv",
        "min_segment",
        "shrinkage",
        "ev_buffer",
        "safety_margin",
        "run",
        "summary",
        "model",
        "preview",
        "evaluation",
        "feedback",
        "safety",
        "download_json",
        "download_preview",
        "download_evaluation",
        "download_feedback",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_accuracy_calibration_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
