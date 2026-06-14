from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .pick_store import list_unfinished_picks, update_pick_result
from .profit_goal import parse_price, unit_profit_loss
from .sportsdataio_results import enrich_predictions_with_results


@dataclass(frozen=True)
class ReconcileReport:
    db_path: str
    unfinished_before: int
    matched_rows: int
    graded_rows: int
    still_unfinished: int
    output_json: str | None
    notes: list[str]


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _pick_to_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    raw_json = row.get("raw_json")
    if raw_json:
        try:
            out.update(json.loads(str(raw_json)))
        except json.JSONDecodeError:
            pass
    out.update({key: value for key, value in row.items() if key != "raw_json"})
    if str(row.get("event_key", "")).startswith("game:"):
        out["sdio_game_id"] = str(row.get("event_key", "")).replace("game:", "", 1)
    out.setdefault("prediction", row.get("selection", ""))
    out.setdefault("selection", row.get("selection", ""))
    return out


def _normalize_result(result: str) -> str:
    value = str(result or "").strip().lower()
    if value in {"won", "win", "w", "correct", "hit"}:
        return "win"
    if value in {"lost", "loss", "l", "incorrect", "miss"}:
        return "loss"
    if value in {"push", "void", "tie"}:
        return "push"
    return value


def _profit_for_result(result: str, row: Mapping[str, Any]) -> float | None:
    normalized = _normalize_result(result)
    if normalized not in {"win", "loss", "push"}:
        return None
    price = parse_price(row.get("best_price") or row.get("entry_odds") or row.get("price"))
    return unit_profit_loss(normalized, price)


def reconcile_results(
    *,
    db_path: str | Path,
    canonical_games_csv: str | Path,
    output_json: str | Path | None = None,
) -> ReconcileReport:
    unfinished = list_unfinished_picks(db_path)
    predictions = [_pick_to_prediction(row) for row in unfinished]
    games = read_csv_rows(canonical_games_csv)
    enriched = enrich_predictions_with_results(predictions, games)
    matched = 0
    graded = 0
    for original, row in zip(unfinished, enriched):
        if row.get("sdio_result_match_status") == "matched":
            matched += 1
        result = _normalize_result(str(row.get("result") or ""))
        if result in {"win", "loss", "push"}:
            graded += 1
            update_pick_result(
                db_path,
                original["pick_id"],
                result=result,
                actual_winner=str(row.get("actual_winner") or row.get("sdio_result_winner") or ""),
                profit_loss_units=_profit_for_result(result, row),
                closing_odds=None,
                clv=None,
            )
    still_unfinished = len(list_unfinished_picks(db_path))
    report = ReconcileReport(
        db_path=str(db_path),
        unfinished_before=len(unfinished),
        matched_rows=matched,
        graded_rows=graded,
        still_unfinished=still_unfinished,
        output_json=str(output_json) if output_json else None,
        notes=[
            "Reconciliation only grades rows that can be matched to final game data.",
            "Rows remain unfinished when games are not final or matching is ambiguous/unavailable.",
        ],
    )
    if output_json:
        output = Path(output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
