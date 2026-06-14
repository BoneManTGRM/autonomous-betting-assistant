from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

GAME_ID_COLUMNS = ("sdio_game_id", "sportsdataio_game_id", "game_id", "event_id", "sdio_result_game_id")
EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
START_COLUMNS = ("start", "start_time", "event_start", "date", "commence_time")
PICK_TIME_COLUMNS = ("pick_time", "entry_time", "created_at", "timestamp", "as_of")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
SELECTION_COLUMNS = ("selection", "prediction", "pick", "predicted_side", "team", "player_name")
PROBABILITY_COLUMNS = ("model_probability", "calibrated_probability", "probability", "confidence_probability", "prop_blended_probability", "prop_model_probability")
PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds", "sportsbook_odds")
BOOKMAKER_COLUMNS = ("bookmaker_count", "book_count", "books")
DATA_QUALITY_COLUMNS = ("data_quality", "prop_data_quality", "feature_data_quality")


@dataclass(frozen=True)
class ValidationPolicy:
    require_pick_time: bool = True
    require_start_time: bool = True
    require_price: bool = True
    require_market: bool = True
    require_selection: bool = True
    require_probability: bool = True
    reject_started_games: bool = True
    min_decimal_odds: float = 1.01
    max_decimal_odds: float = 100.0
    min_probability: float = 0.0
    max_probability: float = 1.0
    min_bookmaker_count: int | None = None
    min_data_quality: float | None = None


@dataclass(frozen=True)
class ValidationIssue:
    row_number: int
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    status: str
    raw_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    error_count: int
    warning_count: int
    output_csv: str | None
    issues_json: str | None
    issues: list[ValidationIssue]
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_probability(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    if number < 0 or number > 1:
        return None
    return number


def parse_price(value: Any) -> float | None:
    price = _float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def duplicate_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    game_id = _first(row, GAME_ID_COLUMNS)
    market = _first(row, MARKET_COLUMNS).lower()
    selection = _first(row, SELECTION_COLUMNS).lower()
    if game_id:
        return "game_id", game_id.removesuffix(".0").lower(), market, selection
    event = _first(row, EVENT_COLUMNS).lower()
    start = _first(row, START_COLUMNS).lower()
    return "event_start", f"{event}|{start}", market, selection


def validate_prediction_rows(rows: list[Mapping[str, Any]], policy: ValidationPolicy = ValidationPolicy(), *, now: datetime | None = None) -> tuple[list[dict[str, Any]], ValidationReport]:
    issues: list[ValidationIssue] = []
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    duplicate_rows = 0
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    for index, row in enumerate(rows, start=2):
        row_issues: list[ValidationIssue] = []
        key = duplicate_key(row)
        if key in seen:
            duplicate_rows += 1
            row_issues.append(ValidationIssue(index, "ERROR", "DUPLICATE_PICK", "Duplicate game/event + market + selection row."))
        seen.add(key)

        event = _first(row, EVENT_COLUMNS)
        game_id = _first(row, GAME_ID_COLUMNS)
        start_text = _first(row, START_COLUMNS)
        pick_time_text = _first(row, PICK_TIME_COLUMNS)
        market = _first(row, MARKET_COLUMNS)
        selection = _first(row, SELECTION_COLUMNS)
        probability = parse_probability(_first(row, PROBABILITY_COLUMNS))
        price = parse_price(_first(row, PRICE_COLUMNS))
        books = _float(_first(row, BOOKMAKER_COLUMNS))
        quality = _float(_first(row, DATA_QUALITY_COLUMNS))
        start_time = parse_time(start_text)
        pick_time = parse_time(pick_time_text)

        if not event and not game_id:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_EVENT_OR_GAME_ID", "Row needs an event name or game ID."))
        if policy.require_start_time and not start_text:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_START_TIME", "Row is missing start_time/start/date."))
        elif start_text and start_time is None:
            row_issues.append(ValidationIssue(index, "ERROR", "INVALID_START_TIME", "Start time could not be parsed."))
        if policy.require_pick_time and not pick_time_text:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_PICK_TIME", "Row is missing pick_time/entry_time."))
        elif pick_time_text and pick_time is None:
            row_issues.append(ValidationIssue(index, "ERROR", "INVALID_PICK_TIME", "Pick time could not be parsed."))
        if policy.reject_started_games and start_time and pick_time and pick_time >= start_time:
            row_issues.append(ValidationIssue(index, "ERROR", "PICK_AFTER_START", "Pick time is at or after event start time."))
        if policy.reject_started_games and start_time and start_time <= now_utc:
            row_issues.append(ValidationIssue(index, "WARNING", "EVENT_ALREADY_STARTED", "Event start time is in the past relative to validation time."))
        if policy.require_market and not market:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_MARKET", "Row is missing market."))
        if policy.require_selection and not selection:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_SELECTION", "Row is missing selection/prediction/pick."))
        if policy.require_probability and probability is None:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_OR_INVALID_PROBABILITY", "Row is missing model probability or probability is invalid."))
        elif probability is not None and not (policy.min_probability <= probability <= policy.max_probability):
            row_issues.append(ValidationIssue(index, "ERROR", "PROBABILITY_OUT_OF_RANGE", "Probability is outside allowed range."))
        if policy.require_price and price is None:
            row_issues.append(ValidationIssue(index, "ERROR", "MISSING_OR_INVALID_ODDS", "Row is missing valid odds/price."))
        elif price is not None and not (policy.min_decimal_odds <= price <= policy.max_decimal_odds):
            row_issues.append(ValidationIssue(index, "ERROR", "ODDS_OUT_OF_RANGE", "Decimal odds are outside allowed range."))
        if policy.min_bookmaker_count is not None and (books is None or books < policy.min_bookmaker_count):
            row_issues.append(ValidationIssue(index, "WARNING", "LOW_BOOKMAKER_COUNT", "Bookmaker count is below policy minimum."))
        if policy.min_data_quality is not None and (quality is None or quality < policy.min_data_quality):
            row_issues.append(ValidationIssue(index, "WARNING", "LOW_DATA_QUALITY", "Data quality is below policy minimum."))

        issues.extend(row_issues)
        error_codes = [issue.code for issue in row_issues if issue.severity == "ERROR"]
        warning_codes = [issue.code for issue in row_issues if issue.severity == "WARNING"]
        out = dict(row)
        out["validation_status"] = "INVALID" if error_codes else "VALID"
        out["validation_errors"] = "; ".join(error_codes)
        out["validation_warnings"] = "; ".join(warning_codes)
        out["validation_duplicate_key"] = "|".join(key)
        output.append(out)

    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in issues if issue.severity == "WARNING")
    invalid_rows = sum(1 for row in output if row.get("validation_status") == "INVALID")
    status = "PASS" if error_count == 0 else "FAIL"
    if status == "PASS" and warning_count:
        status = "WATCH"
    report = ValidationReport(
        status=status,
        raw_rows=len(rows),
        valid_rows=len(rows) - invalid_rows,
        invalid_rows=invalid_rows,
        duplicate_rows=duplicate_rows,
        error_count=error_count,
        warning_count=warning_count,
        output_csv=None,
        issues_json=None,
        issues=issues,
        notes=[
            "Validation runs before scoring so invalid rows do not silently enter performance tracking.",
            "Duplicate detection uses game_id + market + selection when available, otherwise event/start + market + selection.",
        ],
    )
    return output, report


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_report(report: ValidationReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
