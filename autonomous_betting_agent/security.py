from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 250_000
MAX_CSV_COLUMNS = 250
ALLOWED_UPLOAD_EXTENSIONS = {'.csv', '.txt'}
DANGEROUS_EXTENSIONS = {'.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar', '.scr', '.com', '.msi', '.sh', '.py'}
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n')
SECRET_PATTERNS = (
    re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*[^,\s]+'),
    re.compile(r'(?i)(sk-[a-z0-9_-]{20,})'),
    re.compile(r'(?i)(ghp_[a-z0-9_]{20,})'),
)


@dataclass(frozen=True)
class SecurityCheck:
    name: str
    passed: bool
    severity: str
    message: str


def sanitize_filename(filename: str) -> str:
    name = Path(str(filename or 'upload.csv')).name
    name = re.sub(r'[^a-zA-Z0-9_.-]+', '_', name).strip('._')
    return name[:160] or 'upload.csv'


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data or b'').hexdigest()


def validate_upload_name(filename: str) -> list[SecurityCheck]:
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    checks: list[SecurityCheck] = []
    checks.append(SecurityCheck('safe_filename', safe_name == Path(str(filename or '')).name or bool(safe_name), 'medium', f'Using safe filename: {safe_name}'))
    checks.append(SecurityCheck('allowed_extension', suffix in ALLOWED_UPLOAD_EXTENSIONS, 'high', f'Extension {suffix or "missing"} is allowed only if it is CSV/text.'))
    checks.append(SecurityCheck('dangerous_extension_block', suffix not in DANGEROUS_EXTENSIONS, 'critical', f'Executable/script uploads are blocked: {suffix or "missing"}.'))
    return checks


def validate_upload_bytes(data: bytes, *, max_bytes: int = MAX_UPLOAD_BYTES) -> list[SecurityCheck]:
    size = len(data or b'')
    return [
        SecurityCheck('file_size_limit', size <= max_bytes, 'high', f'File size is {size} bytes; limit is {max_bytes} bytes.'),
        SecurityCheck('not_empty', size > 0, 'medium', 'File is not empty.' if size > 0 else 'File is empty.'),
    ]


def validate_dataframe(frame: pd.DataFrame) -> list[SecurityCheck]:
    if frame is None:
        return [SecurityCheck('dataframe_present', False, 'high', 'No dataframe was loaded.')]
    rows, cols = frame.shape
    checks = [
        SecurityCheck('row_limit', rows <= MAX_CSV_ROWS, 'high', f'Rows: {rows}; max: {MAX_CSV_ROWS}.'),
        SecurityCheck('column_limit', cols <= MAX_CSV_COLUMNS, 'high', f'Columns: {cols}; max: {MAX_CSV_COLUMNS}.'),
    ]
    formula_cells = count_formula_injection_cells(frame)
    checks.append(SecurityCheck('csv_formula_cells_detected', formula_cells == 0, 'medium', f'Formula-like cells detected: {formula_cells}. They will be escaped on download.'))
    secret_hits = count_secret_like_cells(frame)
    checks.append(SecurityCheck('secret_like_cells_detected', secret_hits == 0, 'high', f'Secret-like cells detected: {secret_hits}. They should be redacted before sharing.'))
    return checks


def all_checks_passed(checks: Iterable[SecurityCheck], *, include_medium: bool = False) -> bool:
    severities = {'critical', 'high'} | ({'medium'} if include_medium else set())
    return all(check.passed or check.severity not in severities for check in checks)


def count_formula_injection_cells(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    count = 0
    for col in frame.columns:
        series = frame[col].dropna().astype(str)
        count += int(series.map(lambda value: value.startswith(FORMULA_PREFIXES)).sum())
    return count


def escape_csv_formula_value(value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return value


def escape_csv_formulas(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    out = frame.copy()
    for col in out.columns:
        out[col] = out[col].map(escape_csv_formula_value)
    return out


def redact_secret_text(value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub('[REDACTED_SECRET]', redacted)
    return redacted


def count_secret_like_cells(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    count = 0
    for col in frame.columns:
        series = frame[col].dropna().astype(str)
        count += int(series.map(lambda value: redact_secret_text(value) != value).sum())
    return count


def redact_secrets_in_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    out = frame.copy()
    for col in out.columns:
        out[col] = out[col].map(redact_secret_text)
    return out


def secure_csv_download(frame: pd.DataFrame, *, redact_secrets: bool = True) -> str:
    out = frame.copy() if frame is not None else pd.DataFrame()
    if redact_secrets:
        out = redact_secrets_in_frame(out)
    out = escape_csv_formulas(out)
    return out.to_csv(index=False)


def safe_join(base_dir: Path, *parts: str) -> Path:
    base = Path(base_dir).resolve()
    candidate = base.joinpath(*(sanitize_filename(part) for part in parts if part)).resolve()
    if base != candidate and base not in candidate.parents:
        raise ValueError('Unsafe path traversal attempt blocked.')
    return candidate


def checks_to_frame(checks: Iterable[SecurityCheck]) -> pd.DataFrame:
    return pd.DataFrame([check.__dict__ for check in checks])
