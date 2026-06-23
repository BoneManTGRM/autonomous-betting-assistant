from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
FEED_ROOT = REPO_ROOT / "data" / "unified_report_feeds"

PUBLIC_FIELDS = (
    "event", "sport", "public_sport", "public_pick", "recommended_action", "consumer_action",
    "model_lean_label", "price_value_label", "official_status_label", "result_status",
    "learning_status", "official_publish_ready", "client_report_ready", "learning_ready",
    "data_issue_reason", "market_read", "why_it_matters", "game_preview", "report_lane",
    "report_lane_v2", "publish_ready",
)
TECHNICAL_FIELDS = (
    "decimal_price", "model_probability", "market_probability", "model_market_edge",
    "expected_value_per_unit", "profit_units", "odds_verified", "proof_id", "locked_at_utc",
    "odds_source", "bookmaker", "model_probability_source", "tennis_blocked",
)


def normalize_feed_id(value: Any) -> str:
    text = safe_text(value).lower() or "default"
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text)[:80]


def brand_to_dict(brand: MagazineBrand | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(brand, Mapping):
        return dict(brand)
    if is_dataclass(brand):
        return asdict(brand)
    return {}


def _bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(bool).sum())


def _issue_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty or "data_issue_reason" not in frame.columns:
        return 0
    return int(frame["data_issue_reason"].map(lambda value: bool(safe_text(value))).sum())


def _records(frame: pd.DataFrame, *, include_technical: bool = False) -> list[dict[str, Any]]:
    fields = PUBLIC_FIELDS + (TECHNICAL_FIELDS if include_technical else ())
    cols = [column for column in fields if column in frame.columns]
    if not cols:
        return []
    return frame[cols].fillna("").to_dict("records")


def _lane(frame: pd.DataFrame, values: set[str]) -> pd.DataFrame:
    if frame is None or frame.empty or "report_lane_v2" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["report_lane_v2"].isin(values)].copy()


def build_report_feed(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer", public: bool = False) -> dict[str, Any]:
    cards = apply_learning_layer_compat(cards)
    brand_data = brand_to_dict(brand)
    workspace_id = normalize_feed_id(brand_data.get("workspace_id"))
    generated_at = datetime.now(timezone.utc).isoformat()
    feed_id = hashlib.sha256(f"{workspace_id}|{mode}|{generated_at}|{public}".encode("utf-8")).hexdigest()[:20]
    include_technical = safe_text(mode).lower() in {"analyst", "proof", "analyst_proof"}
    official = cards[cards.get("official_publish_ready", pd.Series(False, index=cards.index)).astype(bool)].copy() if not cards.empty else pd.DataFrame()
    price_watch = _lane(cards, {"strong_prediction_price_watch", "learning_candidate", "research_play"})
    graded = _lane(cards, {"graded_winner", "graded_loss"})
    data_blocked = cards[cards.get("data_issue_reason", pd.Series("", index=cards.index)).map(lambda value: bool(safe_text(value)))].copy() if not cards.empty else pd.DataFrame()
    return {
        "schema_version": "aba-report-feed-v2",
        "feed_id": feed_id,
        "workspace_id": workspace_id,
        "visibility": "public" if public else "private",
        "mode": mode,
        "generated_at": generated_at,
        "brand": brand_data,
        "counts": {
            "total_cards": int(len(cards)),
            "official_publish_ready": _bool_count(cards, "official_publish_ready"),
            "client_report_ready": _bool_count(cards, "client_report_ready"),
            "learning_ready": _bool_count(cards, "learning_ready"),
            "data_issues": _issue_count(cards),
            "price_watch_research": int(len(price_watch)),
            "graded_results": int(len(graded)),
        },
        "groups": {
            "official_ev": _records(official, include_technical=include_technical),
            "price_watch_research": _records(price_watch, include_technical=include_technical),
            "graded_results": _records(graded, include_technical=include_technical),
            "data_blocked": _records(data_blocked, include_technical=include_technical),
        },
        "notes": "Informational report feed. Official +EV status remains separate from result grading and learning readiness.",
    }


def save_report_feed(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer", public: bool = False) -> dict[str, Any]:
    feed = build_report_feed(cards, brand, mode=mode, public=public)
    folder = FEED_ROOT / normalize_feed_id(feed.get("workspace_id"))
    folder.mkdir(parents=True, exist_ok=True)
    latest = folder / "latest.json"
    specific = folder / f"{feed['feed_id']}.json"
    text = json.dumps(feed, ensure_ascii=False, indent=2)
    latest.write_text(text, encoding="utf-8")
    specific.write_text(text, encoding="utf-8")
    feed["saved_paths"] = {"latest": str(latest), "feed": str(specific)}
    return feed
