from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import builtins
import importlib
import json
import math
import os
import re
import time
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

VERIFICATION_VERSION = "report_export_verification_v1"
LIVE_MAX_AGE_SECONDS = 10 * 60
PREGAME_MAX_AGE_SECONDS = 60 * 60
PRICE_TOLERANCE = 0.015
LINE_TOLERANCE = 0.01
BLOCKING_STATUSES = {
    "STALE_TIMESTAMP",
    "PRICE_MOVED",
    "LINE_MOVED",
    "EVENT_MISMATCH",
    "MARKET_NOT_FOUND",
    "API_FETCH_FAILED",
    "SNAPSHOT_MISSING",
    "EXPORT_BLOCKED",
}
ALLOWED_PUBLIC_STATUSES = {
    "VERIFIED LIVE",
    "VERIFIED RECENT",
    "STALE — EXPORT BLOCKED",
    "PRICE MOVED — EXPORT BLOCKED",
    "LINE MOVED — EXPORT BLOCKED",
    "API UNAVAILABLE — NOT VERIFIED",
    "HISTORICAL RESULT — NOT LIVE",
    "PROVIDER DATA UNAVAILABLE",
}
SECRET_KEYS = (
    "ODDS_API_KEY",
    "THE_ODDS_API_KEY",
    "SPORTSDATAIO_API_KEY",
    "SPORTS_DATA_IO_API_KEY",
    "SPORTSDATA_API_KEY",
)
TIME_KEYS = (
    "verified_timestamp",
    "current_verified_timestamp",
    "odds_last_refresh",
    "last_api_refresh_time",
    "odds_timestamp",
    "price_timestamp",
    "odds_updated_at",
    "line_timestamp",
    "locked_at_utc",
    "timestamp",
    "commence_time",
)
PRICE_KEYS = ("verified_price", "current_verified_price", "decimal_price", "decimal_odds", "best_price", "odds_at_pick", "odds")
LINE_KEYS = ("verified_line", "current_line", "provider_line", "line", "point", "handicap", "total_line", "spread_line", "run_line")
EVENT_KEYS = ("provider_event_id", "event_id", "game_id", "fixture_id", "sportsdataio_event_id", "sdio_event_id", "odds_api_event_id")
PLACEHOLDER_TOKENS = (
    "verify price",
    "context unavailable",
    "no live",
    "not returned for this event",
    "data not returned",
    "player data not returned",
    "uploaded/cached row",
    "http" + "error",
)


@dataclass
class ProviderError:
    provider: str
    endpoint: str
    status: str
    message: str
    timestamp: str
    blocking: bool
    section: str


@dataclass
class RowVerification:
    status: str
    public_status: str
    export_allowed: bool
    reasons: list[str] = field(default_factory=list)
    provider_errors: list[ProviderError] = field(default_factory=list)
    source_mode: str = ""
    row_index: int = 0


@dataclass
class ExportVerificationResult:
    rows: list[dict[str, Any]]
    export_allowed: bool
    blocked_count: int
    stale_ignored_count: int
    quarantined_rows: list[dict[str, Any]] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat(timespec="seconds")


def _secret(*names: str) -> str:
    getter = getattr(builtins, "get_secret", None)
    if callable(getter):
        try:
            value = str(getter(*names) or "").strip()
            if value:
                return value
        except Exception:
            pass
    try:
        import streamlit as st  # type: ignore
        for name in names:
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _safe_float(value: Any) -> float | None:
    text = _clean(value).replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _decimal(value: Any) -> float | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if parsed <= -100:
        return 1.0 + 100.0 / abs(parsed)
    if parsed >= 100:
        return 1.0 + parsed / 100.0
    return parsed if parsed > 1 else None


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        text = _clean(row.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
            return text
    return ""


def _parse_time(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_id(row: Mapping[str, Any]) -> str:
    return _first(row, EVENT_KEYS)


def _timestamp(row: Mapping[str, Any]) -> datetime | None:
    for key in TIME_KEYS:
        parsed = _parse_time(row.get(key))
        if parsed:
            return parsed
    return None


def _price(row: Mapping[str, Any]) -> float | None:
    for key in PRICE_KEYS:
        parsed = _decimal(row.get(key))
        if parsed:
            return parsed
    return None


def _line(row: Mapping[str, Any]) -> float | None:
    for key in LINE_KEYS:
        parsed = _safe_float(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).strip()


def _teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _first(row, ("away_team", "team_a", "team1"))
    home = _first(row, ("home_team", "team_b", "team2"))
    if away and home:
        return away, home
    event = _first(row, ("public_event", "event", "game", "matchup", "event_name"))
    for sep in (" vs ", " VS ", " at ", " @ ", " v "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return "", ""


def _is_june_stale(row: Mapping[str, Any], now: datetime) -> bool:
    ts = _timestamp(row)
    if not ts:
        return False
    return ts.year == now.year and ts.month == 6 and now.month > 6


def _is_historical(row: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(row.get(k)).lower() for k in ("result", "grade", "status", "event_status", "report_lane", "source_mode"))
    return any(token in blob for token in ("win", "loss", "push", "graded", "completed", "final", "ledger-history", "historical"))


def _is_live_market(row: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(row.get(k)).lower() for k in ("is_live", "live", "in_play", "market_status", "event_status", "status"))
    return any(token in blob for token in ("live", "in play", "in-play", "inplay", "true"))


def _verified_marker(row: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(row.get(k)).lower() for k in ("odds_verified", "price_verified", "verified_odds", "provider_verified", "verification_status", "odds_status", "report_truth_status", "odds_source"))
    if any(token in blob for token in ("uploaded", "cached", "saved", "handoff", "fallback", "verify", "not verified")):
        return False
    return any(token in blob for token in ("live", "verified", "true", "provider matched", "current-run"))


def _public_status(status: str, live: bool = False) -> str:
    mapping = {
        "VERIFIED_LIVE": "VERIFIED LIVE",
        "VERIFIED_RECENT": "VERIFIED RECENT",
        "STALE_TIMESTAMP": "STALE — EXPORT BLOCKED",
        "PRICE_MOVED": "PRICE MOVED — EXPORT BLOCKED",
        "LINE_MOVED": "LINE MOVED — EXPORT BLOCKED",
        "API_FETCH_FAILED": "API UNAVAILABLE — NOT VERIFIED",
        "MARKET_NOT_FOUND": "API UNAVAILABLE — NOT VERIFIED",
        "EVENT_MISMATCH": "API UNAVAILABLE — NOT VERIFIED",
        "SNAPSHOT_MISSING": "PROVIDER DATA UNAVAILABLE",
        "PROVIDER_UNSUPPORTED": "PROVIDER DATA UNAVAILABLE",
        "HISTORICAL": "HISTORICAL RESULT — NOT LIVE",
    }
    return mapping.get(status, "VERIFIED LIVE" if live else "VERIFIED RECENT")


def _provider_error(provider: str, endpoint: str, message: str, *, blocking: bool, section: str, status: str = "API_FETCH_FAILED") -> ProviderError:
    safe = re.sub(r"api[_-]?key=[^&\s]+", "api_key=***", _clean(message), flags=re.I)
    for key in SECRET_KEYS:
        value = os.getenv(key, "")
        if value:
            safe = safe.replace(value, "***")
    return ProviderError(provider, endpoint, status, safe[:180], _iso_now(), blocking, section)


def run_capture_market_snapshots() -> dict[str, Any]:
    """Run the local capture workflow when it exists; fail closed without leaking secrets."""
    started = _iso_now()
    modules = ("capture_market_snapshots", "autonomous_betting_agent.capture_market_snapshots")
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        for attr in ("capture_market_snapshots", "main", "run"):
            fn = getattr(module, attr, None)
            if callable(fn):
                try:
                    result = fn()
                    return {"status": "CAPTURE_RAN", "module": module_name, "function": attr, "started_at": started, "finished_at": _iso_now(), "result_type": type(result).__name__}
                except Exception as exc:
                    return {"status": "CAPTURE_FAILED", "module": module_name, "function": attr, "started_at": started, "finished_at": _iso_now(), "safe_error": exc.__class__.__name__}
    return {"status": "CAPTURE_WORKFLOW_UNAVAILABLE", "started_at": started, "finished_at": _iso_now()}


def _odds_api_sport_key(row: Mapping[str, Any]) -> str:
    explicit = _first(row, ("odds_api_sport_key", "sport_key", "odds_sport_key"))
    if explicit:
        return explicit
    text = " ".join(_clean(row.get(k)).lower() for k in ("sport", "league", "competition"))
    if "wnba" in text:
        return "basketball_wnba"
    if "nba" in text:
        return "basketball_nba"
    if "mlb" in text or "baseball" in text:
        return "baseball_mlb"
    if "nfl" in text:
        return "americanfootball_nfl"
    if "nhl" in text:
        return "icehockey_nhl"
    return ""


def fetch_live_odds_snapshot(row: Mapping[str, Any], *, timeout: float = 3.0) -> tuple[dict[str, Any] | None, ProviderError | None]:
    key = _secret("ODDS_API_KEY", "THE_ODDS_API_KEY")
    if not key:
        return None, _provider_error("Odds API", "odds", "Odds API key missing", blocking=True, section="odds", status="API_KEY_MISSING")
    sport_key = _odds_api_sport_key(row)
    if not sport_key:
        return None, _provider_error("Odds API", "odds", "sport key unavailable for row", blocking=True, section="odds", status="PROVIDER_UNSUPPORTED")
    params = urlencode({"apiKey": key, "regions": _first(row, ("odds_region", "region")) or "us", "markets": _first(row, ("odds_market_key", "market_key")) or "h2h,spreads,totals", "oddsFormat": "decimal"})
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds?{params}"
    try:
        req = Request(url, headers={"User-Agent": "ABA-Signal-Pro/1.0"})
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - fixed provider URL; API key never logged
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return {"provider": "Odds API", "sport_key": sport_key, "payload": payload, "fetched_at": _iso_now()}, None
    except Exception as exc:
        return None, _provider_error("Odds API", "odds", exc.__class__.__name__, blocking=True, section="odds")


def _snapshot_required(row: Mapping[str, Any]) -> bool:
    return not _is_historical(row)


def verify_row_for_export(row_like: Mapping[str, Any], *, source_mode: str = "", now: datetime | None = None, live_snapshot: Mapping[str, Any] | None = None, row_index: int = 0) -> tuple[dict[str, Any], RowVerification]:
    now = now or _now()
    row = dict(row_like)
    reasons: list[str] = []
    errors: list[ProviderError] = []
    live = _is_live_market(row)
    max_age = LIVE_MAX_AGE_SECONDS if live else PREGAME_MAX_AGE_SECONDS
    ts = _timestamp(row)
    status = "VERIFIED_LIVE" if live else "VERIFIED_RECENT"
    allowed = True
    if _is_historical(row):
        status, allowed = "HISTORICAL", False
        reasons.append("Historical/graded row cannot be used as live export truth")
    elif _is_june_stale(row, now):
        status, allowed = "STALE_TIMESTAMP", False
        reasons.append("June timestamp quarantined for current live export")
    elif not ts:
        status, allowed = "STALE_TIMESTAMP", False
        reasons.append("Missing provider timestamp")
    elif (now - ts).total_seconds() > max_age:
        status, allowed = "STALE_TIMESTAMP", False
        reasons.append(f"Provider timestamp older than {max_age // 60} minutes")
    if allowed and not _verified_marker(row):
        status, allowed = "API_FETCH_FAILED", False
        reasons.append("No live verified provider marker on row")
    if allowed and _snapshot_required(row):
        snapshot_present = any(_clean(row.get(k)) for k in ("market_snapshot", "odds_snapshot", "snapshot_id", "current_verified_price", "verified_price"))
        if not snapshot_present:
            status, allowed = "SNAPSHOT_MISSING", False
            reasons.append("Required market snapshot fields missing")
    if live_snapshot and isinstance(live_snapshot.get("row"), Mapping):
        live_row = live_snapshot["row"]
        saved_event = _event_id(row)
        live_event = _event_id(live_row)
        if allowed and saved_event and live_event and saved_event != live_event:
            status, allowed = "EVENT_MISMATCH", False
            reasons.append("Live event ID does not match saved row")
        saved_teams = {_norm(x) for x in _teams(row) if _norm(x)}
        live_teams = {_norm(x) for x in _teams(live_row) if _norm(x)}
        if allowed and saved_teams and live_teams and not saved_teams.issubset(live_teams | saved_teams.intersection(live_teams)):
            status, allowed = "EVENT_MISMATCH", False
            reasons.append("Live teams do not match saved row")
        saved_price, live_price = _price(row), _price(live_row)
        if allowed and saved_price and live_price and abs(saved_price - live_price) > PRICE_TOLERANCE:
            status, allowed = "PRICE_MOVED", False
            reasons.append("Live price moved beyond tolerance")
        saved_line, live_line = _line(row), _line(live_row)
        if allowed and saved_line is not None and live_line is not None and abs(saved_line - live_line) > LINE_TOLERANCE:
            status, allowed = "LINE_MOVED", False
            reasons.append("Live line moved beyond tolerance")
    if not allowed and status in {"API_FETCH_FAILED", "MARKET_NOT_FOUND", "PROVIDER_UNSUPPORTED"}:
        errors.append(_provider_error("Verification Gate", "pre_export", "; ".join(reasons) or status, blocking=True, section="export", status=status))
    public = _public_status(status, live=live)
    row["export_verification_status"] = status
    row["export_public_status"] = public
    row["export_allowed"] = str(bool(allowed))
    row["export_blocked_reason"] = "; ".join(reasons)
    row["risk"] = public
    row["risk_level"] = public
    row["risk_label"] = public
    row["profit_guard_status"] = public
    row["report_truth_status"] = public
    if allowed:
        row["odds_verified"] = "true"
        row["price_verified"] = "true"
        row["provider_match_status"] = "Provider matched"
    else:
        row["odds_verified"] = "false"
        row["price_verified"] = "false"
        row["provider_match_status"] = status
    row["export_verification_version"] = VERIFICATION_VERSION
    row["verification_checked_at"] = now.isoformat(timespec="seconds")
    return row, RowVerification(status, public, allowed, reasons, errors, source_mode, row_index)


def sanitize_export_sections(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if out.get("export_allowed") != "True" and out.get("export_allowed") is not True:
        out["chain_notes"] = ""
        out["parlay_notes"] = ""
        out["parlay_recommendation"] = ""
    for key, value in list(out.items()):
        if isinstance(value, str) and any(token in value.lower() for token in PLACEHOLDER_TOKENS):
            if key in {"injury_report", "injuries", "lineup_status", "sports_context_summary", "preview_summary", "matchup_notes", "team_stats_summary"}:
                out[key] = ""
    return out


def verify_rows_for_export(rows: Iterable[Mapping[str, Any]], *, source_mode: str = "", run_capture: bool = True, now: datetime | None = None) -> ExportVerificationResult:
    now = now or _now()
    raw_rows = [dict(row) for row in rows]
    capture = run_capture_market_snapshots() if run_capture else {"status": "CAPTURE_SKIPPED"}
    verified_rows: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    checks: list[RowVerification] = []
    for idx, row in enumerate(raw_rows):
        checked, check = verify_row_for_export(row, source_mode=source_mode, now=now, row_index=idx)
        checked = sanitize_export_sections(checked)
        checks.append(check)
        if check.export_allowed:
            verified_rows.append(checked)
        else:
            quarantined.append(checked)
    blocked = len([c for c in checks if not c.export_allowed])
    stale = len([c for c in checks if c.status == "STALE_TIMESTAMP"])
    manifest = {
        "verification_version": VERIFICATION_VERSION,
        "capture": capture,
        "total_rows": len(raw_rows),
        "verified_rows": len(verified_rows),
        "blocked_rows": blocked,
        "stale_rows_ignored": stale,
        "statuses": [asdict(c) for c in checks],
        "checked_at": now.isoformat(timespec="seconds"),
    }
    return ExportVerificationResult(verified_rows, bool(verified_rows) and blocked == 0, blocked, stale, quarantined, manifest)


def manifest_json(result: ExportVerificationResult) -> str:
    return json.dumps(result.manifest, indent=2, sort_keys=True, default=str)
