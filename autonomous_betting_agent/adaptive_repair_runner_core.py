"""Core implementation for the Phase 3B Adaptive Repair Runner.

Phase 3B turns Shadow Mode on for counterfactual evaluation only. It still
forbids live repairs, live pick changes, confidence changes, bet-tier changes,
bankroll changes, sportsbook changes, and production model mutation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.adaptive_repair_diagnostics import build_enhanced_diagnostics, diagnostics_to_markdown
from autonomous_betting_agent.adaptive_repair_engine import read_csv_rows
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.security import file_sha256, redact_secret_text, sanitize_filename

SIMULATION_RUNS_DIR = Path("data/adaptive_repair/simulation_runs")
RUNNER_SCHEMA_VERSION = "adaptive_repair_runner_phase_3b_shadow_v1"
MIN_RYE_SAMPLE_SIZE = 30
MIN_SHADOW_SAMPLE_SIZE = 30
MIN_READY_QUALITY_SCORE = 70.0

SAFETY_STATE = {
    "Repair Mode": "OFF",
    "Shadow Mode": "ON",
    "Live Pick Changes": "OFF",
    "Learning Impact": "Shadow simulation only",
    "TGRM Activation": "OFF",
    "Hidden Value Activation": "OFF",
    "Confidence Calibration Activation": "OFF",
    "Bet Tier Changes": "OFF",
    "Production Model Mutation": "OFF",
}

SHADOW_FLAGS = {
    "production_repairs_active": False,
    "shadow_mode_active": True,
    "live_pick_changes": False,
}


@dataclass
class SourceFileResult:
    path: str
    available: bool
    row_count: int = 0
    error: str = ""
    source_hash: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "path": redact_text(self.path),
            "available": self.available,
            "row_count": self.row_count,
            "error": redact_text(self.error),
            "source_hash": self.source_hash,
        }


@dataclass
class SourceScanResult:
    name: str
    available: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    source_hash: str = ""
    source_path: str = ""
    file_results: list[SourceFileResult] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def loaded_files(self) -> int:
        return sum(1 for item in self.file_results if item.available)

    @property
    def failed_files(self) -> int:
        return sum(1 for item in self.file_results if item.error)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "row_count": self.row_count,
            "error": redact_text(self.error),
            "source_hash": self.source_hash,
            "source_path": redact_text(self.source_path),
            "loaded_files": self.loaded_files,
            "failed_files": self.failed_files,
            "file_results": [item.summary() for item in self.file_results],
        }


@dataclass
class AdaptiveRunnerReport:
    run_id: str
    timestamp: str
    schema_version: str
    safety_state: dict[str, str]
    reparodynamics_doctrine: dict[str, Any]
    sources: list[dict[str, Any]]
    source_summary: dict[str, Any]
    diagnostics: dict[str, Any]
    pattern_candidates: list[dict[str, Any]]
    readiness: dict[str, Any]
    activation_gate: dict[str, Any]
    unavailable_data: list[str]
    production_repairs_active: bool = False
    shadow_mode_active: bool = True
    live_pick_changes: bool = False

    def to_dict(self) -> dict[str, Any]:
        return redact_obj(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_text(value: Any) -> str:
    return str(redact_secret_text(value if value is not None else ""))


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {redact_text(key): redact_obj(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, tuple):
        return [redact_obj(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def rows_from_csv_bytes(data: bytes) -> list[dict[str, Any]]:
    text = (data or b"").decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def hash_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(redact_obj(list(rows)), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_run_id(*, timestamp: str, source_hash: str, total_rows: int, source_count: int) -> str:
    basis = f"{timestamp}|{source_hash}|{total_rows}|{source_count}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def stable_candidate_id(*, pattern_name: str, pattern_type: str, source: str, affected_scope: str, evidence: str) -> str:
    basis = "|".join([pattern_name, pattern_type, source, affected_scope, redact_text(evidence)])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def safe_csv_rows_from_path(path: Path) -> list[dict[str, Any]]:
    return read_csv_rows(path)


def load_proof_ledger_rows() -> list[dict[str, Any]]:
    from autonomous_betting_agent.proof_ledger import load_ledger

    frame = load_ledger()
    if frame is None or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _load_csvs_from_dir(directory: Path, label: str, max_files: int = 20) -> list[dict[str, Any]]:
    return _load_csv_dir_source(directory, label, max_files=max_files).rows


def _load_csv_dir_source(directory: Path, label: str, max_files: int = 20) -> SourceScanResult:
    rows: list[dict[str, Any]] = []
    file_results: list[SourceFileResult] = []
    if not directory.exists():
        return SourceScanResult(name=label, available=False, rows=[], source_path=str(directory))
    for path in sorted(directory.glob("*.csv"))[:max_files]:
        if "adaptive_repair" in str(path):
            continue
        try:
            file_rows = safe_csv_rows_from_path(path)
            file_hash = hash_rows(file_rows) if file_rows else ""
            file_results.append(SourceFileResult(path=str(path), available=bool(file_rows), row_count=len(file_rows), source_hash=file_hash))
            for row in file_rows:
                clean = dict(row)
                clean.setdefault("source_file", str(path))
                clean.setdefault("source_label", label)
                rows.append(clean)
        except Exception as exc:
            file_results.append(SourceFileResult(path=str(path), available=False, row_count=0, error=f"{type(exc).__name__}: {exc}"))
    source_hash = hash_rows(rows) if rows else ""
    errors = [item.error for item in file_results if item.error]
    return SourceScanResult(
        name=label,
        available=bool(rows),
        rows=rows,
        error="; ".join(errors[:3]),
        source_hash=source_hash,
        source_path=str(directory),
        file_results=file_results,
    )


def _scan_source(name: str, loader: Callable[[], list[dict[str, Any]]], *, source_path: str = "") -> SourceScanResult:
    try:
        rows = loader()
        source_hash = hash_rows(rows) if rows else ""
        return SourceScanResult(name=name, available=bool(rows), rows=rows, source_hash=source_hash, source_path=source_path)
    except Exception as exc:
        return SourceScanResult(name=name, available=False, rows=[], error=f"{type(exc).__name__}: {exc}", source_path=source_path)


def system_source_adapters(data_root: Path = Path("data")) -> list[SourceScanResult]:
    return [
        _scan_source("local_proof_ledger", load_proof_ledger_rows, source_path="proof_ledger.load_ledger"),
        _load_csv_dir_source(data_root / "ledgers", "local_csv_ledgers"),
        _load_csv_dir_source(data_root / "exports", "graded_prediction_exports"),
        _load_csv_dir_source(data_root / "learning", "learning_page_compatible_rows"),
        _load_csv_dir_source(data_root / "proof_dashboard", "public_proof_dashboard_rows"),
    ]


def uploaded_source(name: str, rows: Sequence[Mapping[str, Any]], *, source_hash: str = "", source_path: str = "") -> SourceScanResult:
    safe_rows = [dict(row) for row in rows]
    return SourceScanResult(name=name, available=bool(safe_rows), rows=safe_rows, source_hash=source_hash or hash_rows(safe_rows), source_path=source_path)


def source_summary(sources: Sequence[SourceScanResult]) -> dict[str, Any]:
    return {
        "sources_scanned": len(sources),
        "available_sources": [source.name for source in sources if source.available],
        "unavailable_sources": [source.name for source in sources if not source.available and not source.error],
        "failed_sources": [source.name for source in sources if source.error and not source.available],
        "sources_with_warnings": [source.name for source in sources if source.available and source.error],
        "loaded_files": sum(source.loaded_files for source in sources),
        "failed_files": sum(source.failed_files for source in sources),
        "total_rows_found": sum(source.row_count for source in sources),
    }


def combined_rows(sources: Sequence[SourceScanResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        for row in source.rows:
            clean = {str(key): redact_text(value) for key, value in dict(row).items()}
            clean.setdefault("adaptive_source", source.name)
            rows.append(clean)
    return rows


def column_limitations(column_coverage: Mapping[str, Mapping[str, Any]]) -> list[str]:
    limitations = []
    if not column_coverage.get("odds", {}).get("matched_column"):
        limitations.append("ROI simulation limited: odds column missing")
    if not column_coverage.get("closing_odds", {}).get("matched_column"):
        limitations.append("CLV simulation unavailable: closing odds column missing")
    if not column_coverage.get("confidence", {}).get("matched_column"):
        limitations.append("confidence calibration unavailable: confidence column missing")
    if not column_coverage.get("start_time", {}).get("matched_column"):
        limitations.append("start-time validation limited: start-time column missing")
    return limitations


def _coverage_ready(coverage: Mapping[str, Mapping[str, Any]], name: str) -> bool:
    return bool(coverage.get(name, {}).get("matched_column"))


def readiness_report(diagnostics: Mapping[str, Any], unavailable_data: Sequence[str]) -> dict[str, Any]:
    base = diagnostics.get("base_report", {})
    row_level = base.get("row_level", {})
    quality = diagnostics.get("data_quality", {})
    coverage = diagnostics.get("column_coverage", {})
    completed = int(row_level.get("completed", 0) or 0)
    score = float(quality.get("score", 0.0) or 0.0)
    mixed = int(diagnostics.get("mixed_outcome_events", 0) or 0)
    duplicates = int(base.get("duplicate_event_names", 0) or 0) + int(diagnostics.get("duplicate_rows", 0) or 0)

    reasons = []
    if completed < MIN_RYE_SAMPLE_SIZE:
        reasons.append(f"sample size below {MIN_RYE_SAMPLE_SIZE} completed win/loss rows")
    if score < MIN_READY_QUALITY_SCORE:
        reasons.append(f"data-quality score below {MIN_READY_QUALITY_SCORE}")
    if not _coverage_ready(coverage, "odds"):
        reasons.append("odds unavailable")
    if not _coverage_ready(coverage, "closing_odds"):
        reasons.append("closing odds unavailable")
    if not _coverage_ready(coverage, "confidence"):
        reasons.append("confidence unavailable")
    if duplicates:
        reasons.append("duplicate event/row risk present")
    if mixed:
        reasons.append("mixed-event risk present")
    if unavailable_data:
        reasons.extend(str(item) for item in unavailable_data[:5])

    shadow_reasons = []
    if completed < MIN_SHADOW_SAMPLE_SIZE:
        shadow_reasons.append(f"sample size below {MIN_SHADOW_SAMPLE_SIZE} completed win/loss rows")
    if score < MIN_READY_QUALITY_SCORE:
        shadow_reasons.append(f"data-quality score below {MIN_READY_QUALITY_SCORE}")
    if duplicates:
        shadow_reasons.append("duplicate event/row risk present")
    if mixed:
        shadow_reasons.append("mixed-event risk present")

    return {
        "RYE_ready": not reasons,
        "Shadow_Mode_ready": not shadow_reasons,
        "reason_not_ready": reasons if reasons else [],
        "shadow_mode_reason_not_ready": shadow_reasons if shadow_reasons else [],
        "RYE_activation": False,
        "Shadow_Mode_activation": True,
        "Shadow_Mode_live_changes": False,
    }


def activation_gate_report(diagnostics: Mapping[str, Any], readiness: Mapping[str, Any]) -> dict[str, Any]:
    base = diagnostics.get("base_report", {})
    row_level = base.get("row_level", {})
    quality = diagnostics.get("data_quality", {})
    coverage = diagnostics.get("column_coverage", {})
    duplicate_count = int(base.get("duplicate_event_names", 0) or 0) + int(diagnostics.get("duplicate_rows", 0) or 0)
    mixed_count = int(diagnostics.get("mixed_outcome_events", 0) or 0)
    completed = int(row_level.get("completed", 0) or 0)
    score = float(quality.get("score", 0.0) or 0.0)
    checks = {
        "minimum_sample_size_met": completed >= MIN_RYE_SAMPLE_SIZE,
        "data_quality_sufficient": score >= MIN_READY_QUALITY_SCORE,
        "odds_coverage_sufficient": _coverage_ready(coverage, "odds"),
        "closing_odds_coverage_sufficient": _coverage_ready(coverage, "closing_odds"),
        "confidence_coverage_sufficient": _coverage_ready(coverage, "confidence"),
        "duplicate_risk_acceptable": duplicate_count == 0,
        "mixed_event_risk_acceptable": mixed_count == 0,
        "rye_ready": bool(readiness.get("RYE_ready")),
        "shadow_mode_ready": bool(readiness.get("Shadow_Mode_ready")),
        "shadow_mode_active": True,
        "live_repair_allowed": False,
        "live_pick_changes_allowed": False,
    }
    return {
        "gate_status": "SHADOW_ONLY",
        "repair_activation": "OFF",
        "shadow_mode_activation": "ON",
        "reason": "Phase 3B runs Shadow Mode counterfactual evaluation only. Live repairs and live pick changes remain forbidden.",
        "checks": checks,
    }


def _pattern(name: str, pattern_type: str, source: str, sample_size: int, affected_scope: str, evidence: str) -> dict[str, Any]:
    return {
        "candidate_id": stable_candidate_id(pattern_name=name, pattern_type=pattern_type, source=source, affected_scope=affected_scope, evidence=evidence),
        "pattern_name": name,
        "pattern_type": pattern_type,
        "source": source,
        "sample_size": sample_size,
        "affected_scope": affected_scope,
        "evidence_summary": redact_text(evidence),
        "status": "shadow_watchlist",
        "shadow_mode_evaluation": True,
        "shadow_result": "pending_counterfactual_review",
        "repair_allowed": False,
        "production_activation": False,
        "reason_no_activation": "Phase 3B is Shadow Mode only. No live repair activation is allowed.",
    }


def pattern_candidates(report: Mapping[str, Any], diagnostics: Mapping[str, Any], unavailable_data: Sequence[str]) -> list[dict[str, Any]]:
    base = diagnostics.get("base_report", {})
    candidates: list[dict[str, Any]] = []
    for item in base.get("watchlist_patterns", []) or []:
        candidates.append(_pattern(str(item.get("pattern_name", "adaptive_watchlist")), str(item.get("pattern_type", "watchlist")), "combined_sources", int(item.get("sample_size", 0) or 0), "system_scan", str(item.get("recommendation", item.get("evidence_summary", "watchlist-only candidate")))))
    duplicate_rows = int(diagnostics.get("duplicate_rows", 0) or 0)
    duplicate_names = int(base.get("duplicate_event_names", 0) or 0)
    mixed = int(diagnostics.get("mixed_outcome_events", 0) or 0)
    total = int(base.get("total_rows", 0) or 0)
    if duplicate_rows or duplicate_names:
        candidates.append(_pattern("duplicate_event_risk_watchlist", "duplicate_risk", "combined_sources", total, "event_counting", f"Duplicate rows={duplicate_rows}; duplicate event names={duplicate_names}."))
    if mixed:
        candidates.append(_pattern("mixed_event_risk_watchlist", "mixed_event_risk", "combined_sources", total, "unique_event_counting", f"Mixed unique events detected: {mixed}."))
    if total and total < MIN_RYE_SAMPLE_SIZE:
        candidates.append(_pattern("weak_sample_size_limitation", "sample_size_limitation", "combined_sources", total, "readiness", f"Only {total} total row(s) found."))
    for limitation in unavailable_data:
        key = limitation.split(":", 1)[0].lower().replace(" ", "_").replace("-", "_")
        candidates.append(_pattern(f"{key}_watchlist", "data_limitation", "combined_sources", total, "readiness", limitation))
    return candidates


def build_runner_report(rows: Sequence[Mapping[str, Any]], *, sources: Sequence[SourceScanResult], timestamp: str | None = None) -> AdaptiveRunnerReport:
    safe_rows = [dict(row) for row in rows]
    diagnostics_obj = build_enhanced_diagnostics(safe_rows, dataset_name="adaptive_repair_runner")
    diagnostics = diagnostics_obj.to_dict()
    unavailable = column_limitations(diagnostics.get("column_coverage", {}))
    candidates = pattern_candidates({}, diagnostics, unavailable)
    readiness = readiness_report(diagnostics, unavailable)
    activation_gate = activation_gate_report(diagnostics, readiness)
    timestamp = timestamp or utc_timestamp()
    source_hash = hash_rows(safe_rows)
    run_id = create_run_id(timestamp=timestamp, source_hash=source_hash, total_rows=len(safe_rows), source_count=len(sources))
    return AdaptiveRunnerReport(run_id=run_id, timestamp=timestamp, schema_version=RUNNER_SCHEMA_VERSION, safety_state=dict(SAFETY_STATE), reparodynamics_doctrine=get_reparodynamics_doctrine(), sources=[source.summary() for source in sources], source_summary=source_summary(sources), diagnostics=diagnostics, pattern_candidates=candidates, readiness=readiness, activation_gate=activation_gate, unavailable_data=list(unavailable), **SHADOW_FLAGS)


def run_adaptive_repair_scan(*, uploaded_rows: Sequence[Mapping[str, Any]] | None = None, uploaded_filename: str = "uploaded_rows.csv", uploaded_bytes: bytes | None = None, include_system_sources: bool = True, data_root: Path = Path("data"), timestamp: str | None = None) -> AdaptiveRunnerReport:
    sources: list[SourceScanResult] = []
    if uploaded_rows is not None:
        source_hash = file_sha256(uploaded_bytes or json.dumps(list(uploaded_rows), sort_keys=True, default=str).encode("utf-8"))
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=source_hash, source_path=sanitize_filename(uploaded_filename)))
    if include_system_sources:
        sources.extend(system_source_adapters(data_root=data_root))
    rows = combined_rows(sources)
    return build_runner_report(rows, sources=sources, timestamp=timestamp)


def run_adaptive_repair_scan_from_csv(path: str | Path, *, include_system_sources: bool = False, data_root: Path = Path("data"), timestamp: str | None = None) -> AdaptiveRunnerReport:
    path = Path(path)
    data = path.read_bytes()
    rows = rows_from_csv_bytes(data)
    return run_adaptive_repair_scan(uploaded_rows=rows, uploaded_filename=path.name, uploaded_bytes=data, include_system_sources=include_system_sources, data_root=data_root, timestamp=timestamp)


def runner_report_to_markdown(report: AdaptiveRunnerReport) -> str:
    data = report.to_dict()
    doctrine = data.get("reparodynamics_doctrine", {})
    diagnostics = build_enhanced_diagnostics([], dataset_name="empty")
    diagnostics.base_report = data["diagnostics"].get("base_report", diagnostics.base_report)
    diagnostics.data_quality = data["diagnostics"].get("data_quality", diagnostics.data_quality)
    diagnostics.column_coverage = data["diagnostics"].get("column_coverage", diagnostics.column_coverage)
    diagnostics.duplicate_rows = int(data["diagnostics"].get("duplicate_rows", 0) or 0)
    diagnostics.mixed_outcome_events = int(data["diagnostics"].get("mixed_outcome_events", 0) or 0)
    diagnostics.multi_market_events = int(data["diagnostics"].get("multi_market_events", 0) or 0)
    diagnostics.same_event_groups = data["diagnostics"].get("same_event_groups", [])
    diagnostics.missing_required_field_examples = data["diagnostics"].get("missing_required_field_examples", [])
    lines = [f"# ABA Adaptive Repair Runner Scan: {data['run_id']}", "", f"Timestamp: {data['timestamp']}", f"Schema version: {data['schema_version']}", "", "## Safety state", ""]
    lines.extend(f"- {key}: {value}" for key, value in data["safety_state"].items())
    lines.extend(["", "## Reparodynamics Doctrine", "", str(doctrine.get("motive", "Reparodynamics is the operating doctrine of measured self-repair.")), ""])
    lines.extend([
        f"- Doctrine version: {doctrine.get('doctrine_version', 'phase_3b_shadow_v1')}",
        f"- Current phase: {doctrine.get('current_phase', 'Phase 3B')}",
        f"- Operating mode: {doctrine.get('operating_mode', 'Shadow Mode evaluation')}",
        f"- Repair philosophy: {doctrine.get('repair_philosophy', 'Evidence-gated targeted repair')}",
        f"- Live mutation: {doctrine.get('live_mutation', 'Forbidden')}",
        f"- Repair activation: {doctrine.get('repair_activation', 'OFF')}",
        f"- Shadow Mode activation: {doctrine.get('shadow_mode_activation', 'ON')}",
        f"- TGRM activation: {doctrine.get('tgrm_activation', 'OFF')}",
        f"- RYE activation: {doctrine.get('rye_activation', 'OFF')}",
        "- Runner role: system scanner and Shadow Mode report generator, not a live repair daemon.",
        "- Page role: dashboard/control panel for review, manual upload, and audit visibility.",
        "- Shadow candidates are not production repairs.",
        "- RYE readiness is not RYE activation.",
        "- Shadow Mode is active for counterfactual evaluation only.",
        "- ABA observes, evaluates in shadow, and requires later manual approval before any live repair.",
        f"- Final rule: {doctrine.get('final_rule', 'ABA may test repairs in Shadow Mode, but live repair remains forbidden.')}",
        "", "## Activation gate", "",
    ])
    gate = data["activation_gate"]
    lines.extend([f"- Gate status: {gate['gate_status']}", f"- Repair activation: {gate['repair_activation']}", f"- Shadow Mode activation: {gate.get('shadow_mode_activation', 'ON')}", f"- Reason: {gate['reason']}"])
    for key, value in gate.get("checks", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Source summary", ""])
    summary = data["source_summary"]
    lines.extend([
        f"- Sources scanned: {summary['sources_scanned']}",
        f"- Available sources: {', '.join(summary['available_sources']) or 'none'}",
        f"- Unavailable sources: {', '.join(summary['unavailable_sources']) or 'none'}",
        f"- Failed sources: {', '.join(summary['failed_sources']) or 'none'}",
        f"- Sources with warnings: {', '.join(summary.get('sources_with_warnings', [])) or 'none'}",
        f"- Loaded files: {summary.get('loaded_files', 0)}",
        f"- Failed files: {summary.get('failed_files', 0)}",
        f"- Total rows found: {summary['total_rows_found']}",
        "", "## Phase 0-2 diagnostics", "", diagnostics_to_markdown(diagnostics).strip(), "", "## RYE / Shadow readiness", "",
        f"- RYE_ready: {data['readiness']['RYE_ready']}",
        f"- Shadow_Mode_ready: {data['readiness']['Shadow_Mode_ready']}",
        f"- RYE activation: {data['readiness']['RYE_activation']}",
        f"- Shadow Mode activation: {data['readiness']['Shadow_Mode_activation']}",
        f"- Shadow Mode live changes: {data['readiness'].get('Shadow_Mode_live_changes', False)}",
        f"- Reasons not ready: {', '.join(data['readiness']['reason_not_ready']) or 'none'}",
        "", "## Shadow-only pattern candidates", "",
    ])
    if data["pattern_candidates"]:
        lines.extend(f"- {item['candidate_id']} | {item['pattern_name']}: {item['evidence_summary']} | shadow={item.get('shadow_mode_evaluation', False)} | live_repair_allowed={item.get('repair_allowed', False)}" for item in data["pattern_candidates"])
    else:
        lines.append("- none")
    lines.extend(["", "## Safety conclusion", "", "Shadow Mode evaluation is active. No live repairs, live confidence changes, live filters, bet-tier changes, bankroll changes, sportsbook changes, or production model mutations were activated."])
    return "\n".join(lines) + "\n"


def save_runner_report(report: AdaptiveRunnerReport, output_dir: Path = SIMULATION_RUNS_DIR) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / sanitize_filename(report.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "simulation_report.json"
    md_path = run_dir / "simulation_report.md"
    json_path.write_text(report.to_json(), encoding="utf-8")
    md_path.write_text(runner_report_to_markdown(report), encoding="utf-8")
    return {"run_dir": str(run_dir), "json_path": str(json_path), "markdown_path": str(md_path)}


def list_recent_simulation_runs(output_dir: Path = SIMULATION_RUNS_DIR, limit: int = 10) -> list[dict[str, Any]]:
    if not output_dir.exists():
        return []
    runs = []
    for path in sorted(output_dir.glob("*/simulation_report.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            runs.append({"run_id": data.get("run_id", path.parent.name), "timestamp": data.get("timestamp", ""), "json_path": str(path), "markdown_path": str(path.with_name("simulation_report.md")), "schema_version": data.get("schema_version", ""), "total_rows": data.get("source_summary", {}).get("total_rows_found", 0), "data_quality_score": data.get("diagnostics", {}).get("data_quality", {}).get("score")})
        except Exception:
            continue
    return runs


def column_mapping_preview(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    diagnostics = build_enhanced_diagnostics([dict(row) for row in rows], dataset_name="column_preview")
    coverage = diagnostics.column_coverage
    return {
        "result": coverage.get("result", {}).get("matched_column"),
        "event": coverage.get("event", {}).get("matched_column"),
        "sport": coverage.get("sport", {}).get("matched_column"),
        "market": coverage.get("market", {}).get("matched_column"),
        "odds": coverage.get("odds", {}).get("matched_column"),
        "closing_odds": coverage.get("closing_odds", {}).get("matched_column"),
        "confidence": coverage.get("confidence", {}).get("matched_column"),
        "edge": coverage.get("edge", {}).get("matched_column"),
        "start_time": coverage.get("start_time", {}).get("matched_column"),
        "limitations": column_limitations(coverage),
    }
