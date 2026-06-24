"""Correlation and duplicate exposure safeguards for local proof rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _norm(value: Any) -> str:
    return _text(value).lower().replace("  ", " ")


def _float(row: Mapping[str, Any], *names: str) -> float:
    for name in names:
        value = row.get(name)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _is_official(row: Mapping[str, Any]) -> bool:
    ledger = _norm(row.get("ledger_type") or row.get("proof_type") or row.get("row_type"))
    official = _norm(row.get("official_ev_pick") or row.get("official"))
    return "official" in ledger or official in {"true", "1", "yes"}


def event_identity(row: Mapping[str, Any]) -> str:
    sport = _norm(row.get("sport") or row.get("sport_key") or row.get("league"))
    event = _norm(row.get("event_name") or row.get("event") or row.get("matchup") or row.get("game"))
    start = _norm(row.get("event_start_time") or row.get("commence_time") or row.get("event_start_utc"))
    return "|".join([sport, event, start])


def _event_pick_key(row: Mapping[str, Any]) -> str:
    pick = _norm(row.get("prediction") or row.get("pick") or row.get("selection"))
    market = _norm(row.get("market") or row.get("market_type") or row.get("bet_type"))
    return "|".join([event_identity(row), pick, market])


def detect_duplicate_proof_ids(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    proof_ids = [_text(row.get("proof_id")) for row in rows if _text(row.get("proof_id"))]
    counts = Counter(proof_ids)
    return [{"proof_id": proof_id, "count": count} for proof_id, count in counts.items() if count > 1]


def detect_duplicate_event_picks(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    samples: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = _event_pick_key(row)
        if key.strip("|"):
            counts[key] += 1
            samples.setdefault(key, row)
    out = []
    for key, count in counts.items():
        if count > 1:
            sample = samples[key]
            out.append(
                {
                    "event_identity": event_identity(sample),
                    "prediction": _text(sample.get("prediction") or sample.get("pick") or sample.get("selection")),
                    "market": _text(sample.get("market") or sample.get("market_type") or sample.get("bet_type")),
                    "count": count,
                }
            )
    return out


def detect_same_event_exposure(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = event_identity(row)
        if key.strip("|"):
            grouped[key].append(row)
    out = []
    for key, group in grouped.items():
        official_count = sum(1 for row in group if _is_official(row))
        if len(group) > 1 or official_count > 1:
            out.append({"event_identity": key, "rows": len(group), "official_rows": official_count})
    return out


def detect_related_market_exposure(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        selection = _norm(row.get("prediction") or row.get("pick") or row.get("selection"))
        market = _norm(row.get("market") or row.get("market_type") or row.get("bet_type"))
        if selection and market:
            grouped["|".join([event_identity(row), selection])].add(market)
    return [
        {"event_selection": key, "markets": sorted(markets), "market_count": len(markets)}
        for key, markets in grouped.items()
        if len(markets) > 1
    ]


def one_official_pick_per_event_filter(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    passthrough: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        if _is_official(payload):
            grouped[event_identity(payload)].append(payload)
        else:
            passthrough.append(payload)
    kept: list[dict[str, Any]] = []
    for group in grouped.values():
        best = sorted(
            group,
            key=lambda row: _float(row, "pattern_points", "agent_score", "scanner_strength_score", "model_probability"),
            reverse=True,
        )[0]
        kept.append(best)
    return passthrough + kept


def correlation_warnings(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    materialized = [dict(row) for row in rows]
    warnings: list[str] = []
    for item in detect_duplicate_proof_ids(materialized):
        warnings.append(f"Duplicate proof ID {item['proof_id']} appears {item['count']} times.")
    for item in detect_duplicate_event_picks(materialized):
        warnings.append(f"Duplicate event/pick/market appears {item['count']} times for {item['event_identity']}.")
    for item in detect_same_event_exposure(materialized):
        if item["official_rows"] > 1:
            warnings.append(f"Multiple official rows exist for one event: {item['event_identity']}.")
    for item in detect_related_market_exposure(materialized):
        warnings.append(f"Related market exposure found for {item['event_selection']}: {', '.join(item['markets'])}.")
    return warnings
