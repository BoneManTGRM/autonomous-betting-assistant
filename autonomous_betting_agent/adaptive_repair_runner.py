"""System-wide ABA Adaptive Repair Runner.

Phase 3A keeps the runner event-triggered, simulation-only, and safe. It can
scan available local sources, uploaded rows, or future hooks, but it never
changes live picks, confidence, filters, bet tiers, bankroll logic, sportsbook
recommendations, or production model behavior.
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
from autonomous_betting_agent.security import file_sha256, redact_secret_text, sanitize_filename

SIMULATION_RUNS_DIR = Path("data/adaptive_repair/simulation_runs")
MIN_RYE_SAMPLE_SIZE = 30
MIN_SHADOW_SAMPLE_SIZE = 30
MIN_READY_QUALITY_SCORE = 70.0

SAFETY_STATE = {
    "Repair Mode": "OFF",
    "Shadow Mode": "OFF",
    "Live Pick Changes": "OFF",
    "Learning Impact": "Simulation only",
    "TGRM Activation": "OFF",
    "Hidden Value Activation": "OFF",
    "Confidence Calibration Activation": "OFF",
    "Bet Tier Changes": "OFF",
    "Production Model Mutation": "OFF",
}

FALSE_FLAGS = {
    "production_repairs_active": False,
    "shadow_mode_active": False,
    "live_pick_changes": False,
}


@dataclass
class SourceScanResult:
    name: str
    available: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    source_hash: str = ""
    source_path: str = ""

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "row_count": self.row_count,
            "error": redact_text(self.error),
            "source_hash": self.source_hash,
            "source_path": redact_text(self.source_path),
        }


@dataclass
class AdaptiveRunnerReport:
    run_id: str
    timestamp: str
    safety_state: dict[str, str]
    sources: list[dict[str, Any]]
    source_summary: dict[str, Any]
    diagnostics: dict[str, Any]
    pattern_candidates: list[dict[str, Any]]
    readiness: dict[str, Any]
    unavailable_data: list[str]
    production_repairs_active: bool = False
    shadow_mode_active: bool = False
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


def safe_csv_rows_from_path(path: Path) -> list[dict[str, Any]]:
    return read_csv_rows(path)


def load_proof_ledger_rows() -> list[dict[str, Any]]:
    from autonomous_betting_agent.proof_ledger import load_ledger

    frame = load_ledger()
    if frame is None or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _load_csvs_from_dir(directory: Path, label: str, max_files: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("*.csv"))[:max_files]:
        if "adaptive_repair" in str(path):
            continue
        for row in safe_csv_rows_from_path(path):
            row = dict(row)
            row.setdefault("source_file", str(path))
            row.setdefault("source_label", label)
            rows.append(row)
    return rows


def _scan_source(name: str, loader: Callable[[], list[dict[str, Any]]], *, source_path: str = "") -> SourceScanResult:
    try:
        rows = loader()
        source_hash = hash_rows(rows) if rows else ""
        return SourceScanResult(name=name, available=bool(rows), rows=rows, source_hash=source_hash, source_path=source_path)
    except Exception as exc:
        return SourceScanResult(name=name, available=False, rows=[], error=f"{type(exc).__name__}: {exc}", source_path=source_path)


def system_source_adapters(data_root: Path = Path("data")) -> list[SourceScanResult]:
    adapters: list[tuple[str, Callable[[], list[dict[str, Any]]], str]] = [
        ("local_proof_ledger", load_proof_ledger_rows, "proof_ledger.load_ledger"),
        ("local_csv_ledgers", lambda: _load_csvs_from_dir(data_root / "ledgers", "local_csv_ledgers"), str(data_root / "ledgers")),
        ("graded_prediction_exports", lambda: _load_csvs_from_dir(data_root / "exports", "graded_prediction_exports"), str(data_root / "exports")),
        ("learning_page_compatible_rows", lambda: _load_csvs_from_dir(data_root / "learning", "learning_page_compatible_rows"), str(data_root / "learning")),
        ("public_proof_dashboard_rows", lambda: _load_csvs_from_dir(data_root / "proof_dashboard", "public_proof_dashboard_rows"), str(data_root / "proof_dashboard")),
    ]
    return [_scan_source(name, loader, source_path=path) for name, loader, path in adapters]


def uploaded_source(name: str, rows: Sequence[Mapping[str, Any]], *, source_hash: str = "", source_path: str = "") -> SourceScanResult:
    safe_rows = [dict(row) for row in rows]
    return SourceScanResult(
        name=name,
        available=bool(safe_rows),
        rows=safe_rows,
        source_hash=source_hash or hash_rows(safe_rows),
        source_path=source_path,
    )


def source_summary(sources: Sequence[SourceScanResult]) -> dict[str, Any]:
    return {
        "sources_scanned": len(sources),
        "available_sources": [source.name for source in sources if source.available],
        "unavailable_sources": [source.name for source in sources if not source.available and not source.error],
        "failed_sources": [source.name for source in sources if source.error],
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
        "Shadow_Mode_activation": False,
    }


def _pattern(name: str, pattern_type: str, source: str, sample_size: int, affected_scope: str, evidence: str) -> dict[str, Any]:
    return {
        "pattern_name": name,
        "pattern_type": pattern_type,
        "source": source,
        "sample_size": sample_size,
        "affected_scope": affected_scope,
        "evidence_summary": redact_text(evidence),
        "status": "watchlist",
        "repair_allowed": False,
        "reason_no_activation": "Phase 3A is simulation-only/readiness-only. No live repair activation is allowed.",
    }


def pattern_candidates(report: Mapping[str, Any], diagnostics: Mapping[str, Any], unavailable_data: Sequence[str]) -> list[dict[str, Any]]:
    base = diagnostics.get("base_report", {})
    candidates: list[dict[str, Any]] = []
    for item in base.get("watchlist_patterns", []) or []:
        candidates.append(_pattern(
            str(item.get("pattern_name", "adaptive_watchlist")),
            str(item.get("pattern_type", "watchlist")),
            "combined_sources",
            int(item.get("sample_size", 0) or 0),
            "system_scan",
            str(item.get("recommendation", item.get("evidence_summary", "watchlist-only candidate"))),
        ))

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


def build_runner_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    sources: Sequence[SourceScanResult],
    timestamp: str | None = None,
) -> AdaptiveRunnerReport:
    safe_rows = [dict(row) for row in rows]
    diagnostics_obj = build_enhanced_diagnostics(safe_rows, dataset_name="adaptive_repair_runner")
    diagnostics = diagnostics_obj.to_dict()
    unavailable = column_limitations(diagnostics.get("column_coverage", {}))
    candidates = pattern_candidates({}, diagnostics, unavailable)
    readiness = readiness_report(diagnostics, unavailable)
    timestamp = timestamp or utc_timestamp()
    source_hash = hash_rows(safe_rows)
    run_id = create_run_id(timestamp=timestamp, source_hash=source_hash, total_rows=len(safe_rows), source_count=len(sources))
    return AdaptiveRunnerReport(
        run_id=run_id,
        timestamp=timestamp,
        safety_state=dict(SAFETY_STATE),
        sources=[source.summary() for source in sources],
        source_summary=source_summary(sources),
        diagnostics=diagnostics,
        pattern_candidates=candidates,
        readiness=readiness,
        unavailable_data=list(unavailable),
        **FALSE_FLAGS,
    )


def run_adaptive_repair_scan(
    *,
    uploaded_rows: Sequence[Mapping[str, Any]] | None = None,
    uploaded_filename: str = "uploaded_rows.csv",
    uploaded_bytes: bytes | None = None,
    include_system_sources: bool = True,
    data_root: Path = Path("data"),
    timestamp: str | None = None,
) -> AdaptiveRunnerReport:
    sources: list[SourceScanResult] = []
    if uploaded_rows is not None:
        source_hash = file_sha256(uploaded_bytes or json.dumps(list(uploaded_rows), sort_keys=True, default=str).encode("utf-8"))
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=source_hash, source_path=sanitize_filename(uploaded_filename)))
    if include_system_sources:
        sources.extend(system_source_adapters(data_root=data_root))
    rows = combined_rows(sources)
    return build_runner_report(rows, sources=sources, timestamp=timestamp)


def run_adaptive_repair_scan_from_csv(
    path: str | Path,
    *,
    include_system_sources: bool = False,
    data_root: Path = Path("data"),
    timestamp: str | None = None,
) -> AdaptiveRunnerReport:
    path = Path(path)
    data = path.read_bytes()
    rows = rows_from_csv_bytes(data)
    return run_adaptive_repair_scan(
        uploaded_rows=rows,
        uploaded_filename=path.name,
        uploaded_bytes=data,
        include_system_sources=include_system_sources,
        data_root=data_root,
        timestamp=timestamp,
    )


def runner_report_to_markdown(report: AdaptiveRunnerReport) -> str:
    data = report.to_dict()
    diagnostics = build_enhanced_diagnostics([], dataset_name="empty")
    diagnostics.base_report = data["diagnostics"].get("base_report", diagnostics.base_report)
    diagnostics.data_quality = data["diagnostics"].get("data_quality", diagnostics.data_quality)
    diagnostics.column_coverage = data["diagnostics"].get("column_coverage", diagnostics.column_coverage)
    diagnostics.duplicate_rows = int(data["diagnostics"].get("duplicate_rows", 0) or 0)
    diagnostics.mixed_outcome_events = int(data["diagnostics"].get("mixed_outcome_events", 0) or 0)
    diagnostics.multi_market_events = int(data["diagnostics"].get("multi_market_events", 0) or 0)
    diagnostics.same_event_groups = data["diagnostics"].get("same_event_groups", [])
    diagnostics.missing_required_field_examples = data["diagnostics"].get("missing_required_field_examples", [])
    lines = [
        f"# ABA Adaptive Repair Runner Scan: {data['run_id']}",
        "",
        f"Timestamp: {data['timestamp']}",
        "",
        "## Safety state",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in data["safety_state"].items())
    lines.extend(["", "## Source summary", ""])
    summary = data["source_summary"]
    lines.extend([
        f"- Sources scanned: {summary['sources_scanned']}",
        f"- Available sources: {', '.join(summary['available_sources']) or 'none'}",
        f"- Unavailable sources: {', '.join(summary['unavailable_sources']) or 'none'}",
        f"- Failed sources: {', '.join(summary['failed_sources']) or 'none'}",
        f"- Total rows found: {summary['total_rows_found']}",
        "",
        "## Phase 0-2 diagnostics",
        "",
        diagnostics_to_markdown(diagnostics).strip(),
        "",
        "## RYE / Shadow readiness",
        "",
        f"- RYE_ready: {data['readiness']['RYE_ready']}",
        f"- Shadow_Mode_ready: {data['readiness']['Shadow_Mode_ready']}",
        f"- RYE activation: {data['readiness']['RYE_activation']}",
        f"- Shadow Mode activation: {data['readiness']['Shadow_Mode_activation']}",
        f"- Reasons not ready: {', '.join(data['readiness']['reason_not_ready']) or 'none'}",
        "",
        "## Watchlist-only pattern candidates",
        "",
    ])
    if data["pattern_candidates"]:
        lines.extend(f"- {item['pattern_name']}: {item['evidence_summary']}" for item in data["pattern_candidates"])
    else:
        lines.append("- none")
    lines.extend(["", "## Safety conclusion", "", "No live repairs, live confidence changes, live filters, bet-tier changes, bankroll changes, or production model mutations were activated."])
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
            runs.append({
                "run_id": data.get("run_id", path.parent.name),
                "timestamp": data.get("timestamp", ""),
                "json_path": str(path),
                "markdown_path": str(path.with_name("simulation_report.md")),
                "total_rows": data.get("source_summary", {}).get("total_rows_found", 0),
                "data_quality_score": data.get("diagnostics", {}).get("data_quality", {}).get("score"),
            })
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
