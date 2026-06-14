from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PickStoreSummary:
    db_path: str
    run_count: int
    pick_count: int
    final_bet_count: int
    watch_count: int
    rejected_count: int
    unfinished_count: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_store(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_type TEXT NOT NULL,
                run_mode TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT '',
                pipeline_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                output_dir TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS picks (
                pick_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                event_key TEXT NOT NULL,
                sport TEXT NOT NULL DEFAULT '',
                league TEXT NOT NULL DEFAULT '',
                market TEXT NOT NULL DEFAULT '',
                selection TEXT NOT NULL DEFAULT '',
                start_time TEXT NOT NULL DEFAULT '',
                pick_time TEXT NOT NULL DEFAULT '',
                bankroll_action TEXT NOT NULL DEFAULT '',
                ensemble_status TEXT NOT NULL DEFAULT '',
                recommended_stake_units REAL NOT NULL DEFAULT 0,
                best_price REAL,
                closing_odds REAL,
                result TEXT NOT NULL DEFAULT '',
                actual_winner TEXT NOT NULL DEFAULT '',
                profit_loss_units REAL,
                clv REAL,
                model_version TEXT NOT NULL DEFAULT '',
                pipeline_version TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, event_key, market, selection)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                pick_id TEXT NOT NULL,
                snapshot_time TEXT NOT NULL DEFAULT '',
                bookmaker TEXT NOT NULL DEFAULT '',
                price REAL,
                is_closing INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL,
                FOREIGN KEY(pick_id) REFERENCES picks(pick_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    lowered = {str(key).strip().lower().replace(" ", "_"): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower().replace(" ", "_"))
        if value not in (None, ""):
            return _clean(value)
    return ""


def _float(value: Any) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def event_key(row: Mapping[str, Any]) -> str:
    game_id = _first(row, ("sdio_game_id", "sportsdataio_game_id", "game_id", "sdio_result_game_id", "event_id"))
    if game_id:
        return f"game:{game_id}"
    event = _first(row, ("event", "event_name", "game", "match", "fixture"))
    start = _first(row, ("start_time", "start", "event_start", "date", "commence_time"))
    return f"event:{event}|start:{start}"


def create_run(
    db_path: str | Path,
    *,
    run_type: str = "manual",
    run_mode: str = "manual",
    model_version: str = "",
    pipeline_version: str = "",
    output_dir: str = "",
    notes: str = "",
    run_id: str | None = None,
) -> str:
    initialize_store(db_path)
    run_id = run_id or str(uuid.uuid4())
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, run_type, run_mode, model_version, pipeline_version, created_at, output_dir, notes)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, run_type, run_mode, model_version, pipeline_version, utc_now_iso(), output_dir, notes),
        )
        conn.commit()
    return run_id


def upsert_pick(db_path: str | Path, run_id: str, row: Mapping[str, Any], *, model_version: str = "", pipeline_version: str = "") -> str:
    initialize_store(db_path)
    now = utc_now_iso()
    pick_id = _first(row, ("pick_id",)) or str(uuid.uuid4())
    key = event_key(row)
    sport = _first(row, ("sport",))
    league = _first(row, ("league", "competition"))
    market = _first(row, ("market", "market_key", "prop_type", "bet_type"))
    selection = _first(row, ("selection", "prediction", "pick", "team", "player_name"))
    start_time = _first(row, ("start_time", "start", "event_start", "date", "commence_time"))
    pick_time = _first(row, ("pick_time", "entry_time", "created_at", "timestamp", "as_of"))
    action = _first(row, ("bankroll_action",))
    ensemble_status = _first(row, ("ensemble_status",))
    stake = _float(_first(row, ("recommended_stake_units",))) or 0.0
    price = _float(_first(row, ("best_price", "entry_odds", "price", "odds", "decimal_odds")))
    close = _float(_first(row, ("closing_odds", "closing_price")))
    result = _first(row, ("result", "outcome", "win_loss", "graded_result"))
    actual_winner = _first(row, ("actual_winner", "sdio_result_winner"))
    clv = _float(_first(row, ("closing_line_value", "clv")))
    raw_json = json.dumps(dict(row), sort_keys=True)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO picks(
                pick_id, run_id, event_key, sport, league, market, selection, start_time, pick_time,
                bankroll_action, ensemble_status, recommended_stake_units, best_price, closing_odds,
                result, actual_winner, profit_loss_units, clv, model_version, pipeline_version,
                raw_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, event_key, market, selection) DO UPDATE SET
                bankroll_action=excluded.bankroll_action,
                ensemble_status=excluded.ensemble_status,
                recommended_stake_units=excluded.recommended_stake_units,
                best_price=excluded.best_price,
                closing_odds=excluded.closing_odds,
                result=excluded.result,
                actual_winner=excluded.actual_winner,
                clv=excluded.clv,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            (
                pick_id,
                run_id,
                key,
                sport,
                league,
                market,
                selection,
                start_time,
                pick_time,
                action,
                ensemble_status,
                stake,
                price,
                close,
                result,
                actual_winner,
                clv,
                model_version,
                pipeline_version,
                raw_json,
                now,
                now,
            ),
        )
        conn.commit()
    return pick_id


def record_pick_rows(db_path: str | Path, run_id: str, rows: Iterable[Mapping[str, Any]], *, model_version: str = "", pipeline_version: str = "") -> int:
    count = 0
    for row in rows:
        upsert_pick(db_path, run_id, row, model_version=model_version, pipeline_version=pipeline_version)
        count += 1
    return count


def list_unfinished_picks(db_path: str | Path) -> list[dict[str, Any]]:
    initialize_store(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM picks
            WHERE COALESCE(result, '') = '' OR lower(result) IN ('pending', 'ungraded', 'unknown')
            ORDER BY start_time, created_at
            """
        ).fetchall()
    return [dict(row) for row in rows]


def update_pick_result(db_path: str | Path, pick_id: str, *, result: str, actual_winner: str = "", profit_loss_units: float | None = None, closing_odds: float | None = None, clv: float | None = None) -> None:
    initialize_store(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE picks
            SET result=?, actual_winner=?, profit_loss_units=?, closing_odds=COALESCE(?, closing_odds), clv=COALESCE(?, clv), updated_at=?
            WHERE pick_id=?
            """,
            (result, actual_winner, profit_loss_units, closing_odds, clv, utc_now_iso(), pick_id),
        )
        conn.commit()


def export_history_rows(db_path: str | Path) -> list[dict[str, Any]]:
    initialize_store(db_path)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM picks ORDER BY pick_time, created_at").fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            raw = json.loads(item.get("raw_json") or "{}")
        except json.JSONDecodeError:
            raw = {}
        raw.update({key: value for key, value in item.items() if key != "raw_json"})
        output.append(raw)
    return output


def write_history_csv(db_path: str | Path, output_csv: str | Path) -> None:
    rows = export_history_rows(db_path)
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def summarize_store(db_path: str | Path) -> PickStoreSummary:
    initialize_store(db_path)
    with connect(db_path) as conn:
        run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        pick_count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        final_bet_count = conn.execute("SELECT COUNT(*) FROM picks WHERE bankroll_action='BET'").fetchone()[0]
        watch_count = conn.execute("SELECT COUNT(*) FROM picks WHERE bankroll_action='WATCH'").fetchone()[0]
        rejected_count = conn.execute("SELECT COUNT(*) FROM picks WHERE bankroll_action='REJECT'").fetchone()[0]
        unfinished_count = conn.execute("SELECT COUNT(*) FROM picks WHERE COALESCE(result, '') = '' OR lower(result) IN ('pending', 'ungraded', 'unknown')").fetchone()[0]
    return PickStoreSummary(
        db_path=str(db_path),
        run_count=int(run_count),
        pick_count=int(pick_count),
        final_bet_count=int(final_bet_count),
        watch_count=int(watch_count),
        rejected_count=int(rejected_count),
        unfinished_count=int(unfinished_count),
    )


def write_summary(summary: PickStoreSummary, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
