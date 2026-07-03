from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from .adaptive_learning import apply_adaptive_learning
from .four_tool_orchestrator import page_health, page_health_frame
from .live_odds import scan_market
from .multi_source_fusion import fuse_row
from .pick_hold_store import save_held_rows
from .pro_predictor_filtering import apply_filter_audit, diagnostic_mode_allowed, make_research_diagnostic_candidates
from .scanner_strength import score_scanner_frame, scanner_strength_summary
from .sidebar_nav import render_app_sidebar

APP_VERSION = "pro-predictor-v25-min-filter-audit"


def _secret(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, "") or "").strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _next_sunday() -> date:
    base = date.today()
    return base + timedelta(days=(6 - base.weekday()) % 7 or 7)


def _event_date(value: Any) -> date | None:
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
    return parsed.astimezone(timezone.utc).date()


def _future(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < parsed.astimezone(timezone.utc)
    except Exception:
        return False


def _rows_from_events(events: list[Any], *, latest_event_date: date, min_books: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events:
        event_day = _event_date(getattr(event, "commence_time", ""))
        if event_day is None or event_day > latest_event_date:
            continue
        event_name = f"{getattr(event, 'away_team', '')} at {getattr(event, 'home_team', '')}".strip()
        for outcome in getattr(event, "outcomes", []) or []:
            books = int(getattr(event, "bookmaker_count", 0) or getattr(outcome, "source_count", 0) or 0)
            if books < int(min_books):
                continue
            price = getattr(outcome, "best_price", None) or getattr(outcome, "average_price", None)
            market_probability = float(getattr(outcome, "normalized_probability", 0.0) or 0.0)
            fused = fuse_row({"market_probability": market_probability, "learning_adjustment": 0.0})
            model_probability = round(float(fused.final_probability or 0.0), 6)
            implied = None if not price or float(price) <= 1 else round(1 / float(price), 6)
            rows.append({
                "event": event_name,
                "event_id": getattr(event, "event_id", ""),
                "sport": getattr(event, "sport_title", ""),
                "sport_key": getattr(event, "sport_key", ""),
                "event_start_utc": getattr(event, "commence_time", ""),
                "event_date": str(event_day),
                "home_team": getattr(event, "home_team", ""),
                "away_team": getattr(event, "away_team", ""),
                "market_type": getattr(outcome, "market", "h2h") or "h2h",
                "line_point": getattr(outcome, "point", None),
                "prediction": getattr(outcome, "name", ""),
                "model_probability": model_probability,
                "model_probability_clean": model_probability,
                "market_probability": round(market_probability, 6),
                "market_implied_probability": implied,
                "model_market_edge": None if implied is None else round(model_probability - implied, 6),
                "decimal_price": price,
                "odds_at_pick": price,
                "best_price": price,
                "average_price": getattr(outcome, "average_price", None),
                "worst_price": getattr(outcome, "worst_price", None),
                "bookmaker": getattr(outcome, "best_bookmaker", "") or "",
                "bookmaker_count": books,
                "books": books,
                "market_overround": getattr(event, "market_overround", None),
                "odds_source": "The Odds API",
                "reliability_score": fused.reliability_score,
                "confidence": fused.confidence,
            })
    return pd.DataFrame(rows)


def _add_scores(frame: pd.DataFrame, *, strong_edge: float) -> pd.DataFrame:
    scored = score_scanner_frame(frame)
    if scored.empty:
        return scored
    prob = pd.to_numeric(scored.get("model_probability_clean"), errors="coerce").fillna(0.0)
    edge = pd.to_numeric(scored.get("model_market_edge"), errors="coerce").fillna(0.0)
    signal = pd.to_numeric(scored.get("scanner_strength_score"), errors="coerce").fillna(0.0)
    scored["agent_score"] = (prob * 55.0 + edge.clip(-0.10, 0.15) * 180.0 + signal * 0.20).clip(0, 100).round(3)
    scored["agent_decision"] = "review"
    scored.loc[(edge >= float(strong_edge)) & (prob >= 0.66), "agent_decision"] = "strong_review"
    scored["decision_rank"] = scored["agent_decision"].map({"strong_review": 1, "review": 2}).fillna(3)
    scored["lock_ready"] = scored["event_start_utc"].apply(_future)
    scored["decision_reasons"] = ""
    scored["decision_signals"] = "large_list_volume_candidate"
    learned = apply_adaptive_learning(scored)
    learned["agent_score"] = pd.to_numeric(learned.get("learned_agent_score"), errors="coerce").fillna(learned["agent_score"]).round(3)
    learned["decision_signals"] = learned["decision_signals"].astype(str) + "; adaptive_learning_ranker"
    return learned


def _persist(decisions: pd.DataFrame, large: pd.DataFrame, handoff: pd.DataFrame) -> None:
    workspace_id = str(st.session_state.get("aba_test_window_id", "test_01") or "test_01")
    for target in {workspace_id, "test_01"}:
        save_held_rows("pro_predictor_latest_rows", handoff, target)
        save_held_rows("pro_predictor_high_confidence_rows", large, target)
        save_held_rows("ara_latest_predictions", handoff, target)


def render_page() -> None:
    st.set_page_config(page_title="Pro Predictor", layout="wide")
    render_app_sidebar("pro_predictor", language_key="pro_predictor_language", selector="radio")
    st.title("Pro Predictor")
    st.caption(f"App version: {APP_VERSION}")

    api_key = _secret("ODDS_API_KEY", "THE_ODDS_API_KEY")
    st.metric("Odds API", "Enabled" if api_key else "Missing")
    sport_key = st.text_input("Sport key", value="baseball_mlb")
    regions = st.multiselect("Bookmaker regions", ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "eu", "uk"])
    markets = st.multiselect("Markets", ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])
    max_events = st.number_input("Max events", min_value=1, max_value=500, value=500, step=25)
    latest_event_date = st.date_input("Latest event date", value=_next_sunday())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    min_books = c1.number_input("Minimum books", min_value=1, max_value=25, value=1, step=1)
    min_prob = c2.number_input("Minimum model probability", min_value=0.0, max_value=0.99, value=0.58, step=0.01)
    min_edge = c3.number_input("Minimum edge", min_value=-0.25, max_value=0.50, value=-0.03, step=0.005, format="%.3f")
    strong_edge = c4.number_input("Strong edge threshold", min_value=0.0, max_value=0.50, value=0.04, step=0.005, format="%.3f")
    min_signal = c5.number_input("Minimum signal strength", min_value=0.0, max_value=100.0, value=38.0, step=1.0)
    min_agent = c6.number_input("Large-list min learned score", min_value=0.0, max_value=100.0, value=35.0, step=1.0)
    max_rows = st.number_input("Max large-list rows", min_value=1, max_value=1000, value=700, step=25)
    pattern_mode = st.selectbox("Pattern Points mode", ["Research learning 55+", "Strong test 65+", "Official proof 75+", "Elite proof 85+", "Low-confidence pattern candidates"], index=1)

    if not st.button("Run Pro Predictor", type="primary", use_container_width=True):
        return
    if not api_key:
        st.error("Odds API key is required.")
        st.stop()

    try:
        events = scan_market(api_key, sport_key.strip() or "baseball_mlb", regions=",".join(regions), max_events=int(max_events), markets=",".join(markets or ["h2h"]))
        skipped = []
    except Exception as exc:
        events = []
        skipped = [str(exc)[:220]]
    raw = _rows_from_events(events, latest_event_date=latest_event_date, min_books=int(min_books))
    scan_counts = pd.DataFrame([{"sport_key": sport_key, "events_returned": len(events), "rows_built": len(raw)}])
    if raw.empty:
        st.info("No prediction rows passed the filters.")
        st.warning("No live rows were built before filtering. Check sport key, dates, market availability, minimum books, and API access.")
        st.dataframe(scan_counts, use_container_width=True, hide_index=True)
        for item in skipped:
            st.write(f"- {item}")
        st.stop()

    scored = _add_scores(raw, strong_edge=float(strong_edge))
    decisions, audit = apply_filter_audit(scored, min_prob=float(min_prob), min_edge=float(min_edge), min_signal=float(min_signal), min_agent=float(min_agent))
    diagnostic = False
    if decisions.empty:
        allow = diagnostic_mode_allowed(min_signal=float(min_signal), min_agent=float(min_agent)) or pattern_mode in {"Research learning 55+", "Low-confidence pattern candidates"}
        if allow:
            decisions = make_research_diagnostic_candidates(scored, audit, max_rows=int(max_rows))
            diagnostic = not decisions.empty
        if decisions.empty:
            st.info("No prediction rows passed the filters.")
            st.dataframe(audit, use_container_width=True, hide_index=True)
            st.dataframe(scan_counts, use_container_width=True, hide_index=True)
            st.stop()
        st.warning("Showing real research-only diagnostic rows because strict gates removed every normal row.")

    sort_cols = [col for col in ["learned_agent_score", "agent_score", "scanner_strength_score", "model_probability_clean", "model_market_edge"] if col in decisions.columns]
    decisions = decisions.sort_values(sort_cols, ascending=False, na_position="last").reset_index(drop=True) if sort_cols else decisions.reset_index(drop=True)
    large = decisions.head(int(max_rows)).reset_index(drop=True)
    lock_ready = large[large["lock_ready"].astype(bool)].copy() if "lock_ready" in large.columns else pd.DataFrame()
    handoff = large
    st.session_state["pro_predictor_all_rows"] = decisions.to_dict("records")
    st.session_state["pro_predictor_high_confidence_rows"] = large.to_dict("records")
    st.session_state["pro_predictor_latest_rows"] = handoff.to_dict("records")
    st.session_state["ara_latest_predictions"] = handoff.to_dict("records")
    st.session_state["ara_latest_predictions_source"] = "Pro Predictor research diagnostics" if diagnostic else "Pro Predictor adaptive large-list volume"
    st.session_state["ara_latest_predictions_saved_at"] = pd.Timestamp.utcnow().isoformat()
    _persist(decisions, large, handoff)

    st.success("Rows saved to session and handoff store.")
    strength = scanner_strength_summary(decisions)
    health = page_health(handoff, page="pro_predictor")
    m = st.columns(6)
    m[0].metric("All passed", len(decisions))
    m[1].metric("Large list", len(large))
    m[2].metric("Lock ready", len(lock_ready))
    m[3].metric("Avg signal", "N/A" if strength["avg_score"] is None else strength["avg_score"])
    m[4].metric("Premium signals", strength["premium_scan"])
    m[5].metric("Next", health["next_action"])
    st.dataframe(page_health_frame(handoff, page="pro_predictor"), use_container_width=True, hide_index=True)
    display_cols = [col for col in ["event", "sport_key", "market_type", "line_point", "prediction", "model_probability_clean", "market_implied_probability", "model_market_edge", "decimal_price", "bookmaker", "agent_decision", "agent_score", "recommendation_tier", "filter_blocker_reason", "scanner_strength_score", "lock_ready"] if col in decisions.columns]
    tabs = st.tabs(["Large-list", "All rows", "Lock-ready", "Filter audit"])
    with tabs[0]:
        st.dataframe(large[display_cols] if display_cols else large, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(decisions[display_cols] if display_cols else decisions, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(lock_ready, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(audit, use_container_width=True, hide_index=True)
        st.dataframe(scan_counts, use_container_width=True, hide_index=True)
