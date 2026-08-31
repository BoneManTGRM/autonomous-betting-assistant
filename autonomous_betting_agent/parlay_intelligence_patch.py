from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any, Mapping
import re

PATCH_VERSION = "parlay_intelligence_diagnostics_v1"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, Mapping) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _is_no_verified(data: Mapping[str, Any]) -> bool:
    blob = " ".join(_clean(data.get(key)).lower() for key in ("event", "game", "matchup", "prediction", "pick", "final_decision", "recommendation", "report_verification_reason", "report_verification_class"))
    return "no verified buyer picks" in blob or _clean(data.get("report_verification_class")) == "NO_VERIFIED_BUYER_PICKS"


def _summary_counts(summary: Mapping[str, Any] | None, row: Mapping[str, Any] | None = None) -> dict[str, int]:
    raw = dict(summary or {}) or dict((row or {}).get("report_count_summary") or {})
    return {
        "verified": int(raw.get("verified_buyer_picks", 0) or 0),
        "watchlist": int(raw.get("watchlist_verify_price_rows", 0) or 0),
        "price_rejected": int(raw.get("price_rejected_rows", 0) or 0),
        "research": int(raw.get("research_only_rows", 0) or 0),
        "audit": int(raw.get("audit_only_rows", 0) or 0),
        "provider_fail": int(raw.get("rows_excluded_by_provider_failure", 0) or 0),
        "stale": int(raw.get("rows_excluded_by_stale_timestamp", 0) or 0),
        "line_mismatch": int(raw.get("rows_excluded_by_line_mismatch", 0) or 0),
    }


def enrich_no_verified_report_row(value: Any, summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = _row(value)
    if not _is_no_verified(data):
        return data
    counts = _summary_counts(summary, data)
    short = (
        f"Gate summary: {counts['verified']} verified, {counts['watchlist']} watchlist, "
        f"{counts['price_rejected']} price rejected, {counts['research']} research-only, {counts['audit']} audit-only."
    )
    unlock = "Parlay unlock: need at least two current-provider legs with event ID, book, exact line when required, fresh timestamp, model probability, positive edge, and positive EV."
    scan = "Next scan should inventory moneyline, spread/run line/puck line, totals, team totals, and priced props across every available sportsbook before report selection."
    data.update({
        "event": "No verified buyer picks available from current provider data yet.",
        "game": "No verified buyer picks available from current provider data yet.",
        "matchup": "No verified buyer picks available from current provider data yet.",
        "away_team": "No Verified Picks",
        "home_team": "Current Provider Check",
        "team_a": "No Verified Picks",
        "team_b": "Current Provider Check",
        "sport": "Report Verification",
        "league": "ABA Signal Pro",
        "season_label": "Current Provider Gate",
        "risk": "RESEARCH ONLY",
        "risk_level": "RESEARCH ONLY",
        "risk_label": "RESEARCH ONLY",
        "profit_guard_status": "RESEARCH ONLY",
        "report_source": "no_verified_provider_gate",
        "report_source_label": "No verified current-provider picks",
        "report_data_scope": "No verified buyer picks",
        "report_truth_severity": "RESEARCH ONLY",
        "api_match_status": "Provider not matched",
        "provider_match_status": "Provider not matched",
        "odds_status": "NO_VERIFIED_BUYER_PICKS",
        "away_team_form": f"{short}; {scan}; Do not publish a pick until the gate verifies current provider data.",
        "home_team_form": f"Current-provider check: {unlock}; Missing data should be shown as watchlist or blocked, not promoted.",
        "away_injuries": "No verified pick row exists, so lineup/injury notes are diagnostic only. Pull SportsDataIO/news/lineup feeds before entry.",
        "home_injuries": "Current provider check must confirm injury/news context separately from odds. Do not infer availability from price movement.",
        "sports_context_summary": f"{short} {unlock}",
        "matchup_notes": f"{short}; {unlock}; {scan}",
        "news_summary": "No publishable pick was produced. Use this report to repair data coverage rather than to enter a position.",
        "why_bullets": f"No current provider row passed every buyer-pick gate.; {short}; {unlock}; {scan}",
        "final_explanation": f"{short} {unlock}",
        "action_reason": f"{short} {unlock}",
        "recommendation_reason": f"{short} {unlock}",
    })
    data["parlay_intelligence_summary"] = short
    data["parlay_unlock_requirements"] = unlock
    return data


def _reason_bucket(reason: str) -> str:
    text = _clean(reason).lower()
    if "line" in text:
        return "line missing/mismatch"
    if "provider" in text or "source" in text:
        return "provider/source not verified"
    if "timestamp" in text or "stale" in text or "fresh" in text:
        return "stale/missing timestamp"
    if "probability" in text or "model" in text:
        return "model probability missing"
    if "odds" in text or "price" in text:
        return "price missing/rejected"
    if "ev" in text or "edge" in text or "positive" in text:
        return "edge/EV not positive"
    if "correlation" in text or "same-game" in text:
        return "correlation not priced"
    if "event" in text:
        return "event ID missing"
    return text[:60] or "unknown rejection"


def _clear_leg_reason(page2: Any, market: Any, reason: str) -> str:
    text = _clean(reason)
    low = text.lower()
    try:
        line_required = bool(page2._line_required(market.normalized_market))
    except Exception:
        line_required = True
    if not line_required:
        line_status = "Line not required for this market type."
    elif getattr(market, "line", ""):
        line_status = f"Line verified: {market.line}."
    else:
        line_status = "Line missing: provider did not return exact spread/total/prop point."
    if "line" in low:
        return line_status
    if "provider" in low or "source" in low:
        return "Provider match missing: current sportsbook/provider row did not verify."
    if "timestamp" in low or "fresh" in low or "stale" in low:
        return "Fresh timestamp missing or stale: refresh the provider odds before publishing."
    if "model_probability" in low or "probability" in low or "model" in low:
        return "Model probability missing: market cannot be used for parlay math yet."
    if "odds" in low or "price" in low:
        return "Current provider price missing or rejected: sportsbook-level odds are required."
    if "ev" in low or "edge" in low or "positive" in low:
        return "Value check failed: edge and EV must both be positive."
    return text or line_status


def _leg_label(page2: Any, market: Any) -> str:
    odds = page2._odds(getattr(market, "decimal_odds", None)) if hasattr(page2, "_odds") else str(getattr(market, "decimal_odds", "N/A"))
    label = _clean(getattr(market, "full_label", "") or getattr(market, "selection", "") or getattr(market, "raw_market", "market"))
    return f"{label} @ {odds}"


def _market_scan(page2: Any, data: Mapping[str, Any]) -> dict[str, Any]:
    markets, diag = page2.discover_markets(dict(data))
    eligible, watchlist, blocked = [], [], []
    buckets: Counter[str] = Counter()
    line_status: Counter[str] = Counter()
    books = {str(getattr(m, "sportsbook", "")).strip() for m in markets if str(getattr(m, "sportsbook", "")).strip()}
    events = {str(getattr(m, "provider_event_id", "")).strip() for m in markets if str(getattr(m, "provider_event_id", "")).strip()}
    positive_ev = 0
    for market in markets:
        try:
            ok, reason = page2._leg_is_eligible(market)
        except Exception:
            ok, reason = False, _clean(getattr(market, "rejection_reason", "unknown rejection"))
        ev = getattr(market, "ev", None)
        edge = getattr(market, "edge", None)
        if ev is not None and edge is not None and ev > 0 and edge > 0:
            positive_ev += 1
        try:
            requires_line = bool(page2._line_required(market.normalized_market))
        except Exception:
            requires_line = True
        if not requires_line:
            line_status["line not required"] += 1
        elif getattr(market, "line", ""):
            line_status["line verified"] += 1
        else:
            line_status["line missing"] += 1
        if ok:
            eligible.append(market)
        else:
            clear = _clear_leg_reason(page2, market, reason)
            buckets[_reason_bucket(clear)] += 1
            if ev is not None and edge is not None and ev > 0 and edge > 0 and getattr(market, "decimal_odds", None):
                watchlist.append((market, clear))
            else:
                blocked.append((market, clear))
    return {
        "markets": markets,
        "diag": diag,
        "eligible": eligible,
        "watchlist": watchlist,
        "blocked": blocked,
        "reason_counts": buckets,
        "line_counts": line_status,
        "books": books,
        "events": events,
        "positive_ev": positive_ev,
    }


def _install_page2_patch() -> None:
    try:
        from autonomous_betting_agent import magazine_second_page_patch as page2
        from autonomous_betting_agent.report_public_quality import sanitize_public_items
    except Exception:
        return
    if getattr(page2, "_ABA_PARLAY_INTELLIGENCE_PATCH", "") == PATCH_VERSION:
        return
    original_sections = getattr(page2, "_page_two_sections", None)
    original_final_status = getattr(page2, "_final_status", None)
    original_advanced = getattr(page2, "advanced_market_diagnostics", None)
    if not callable(original_sections):
        return

    def enhanced_sections(
        data: dict[str, Any],
        lang: str,
        *,
        parlays=None,
        diagnostics=None,
    ):
        scan = _market_scan(page2, data)
        if parlays is None or diagnostics is None:
            parlays, diagnostics = page2.generate_parlay_candidates(data)
        diag = dict(diagnostics)
        playable = [p for p in parlays if p.status == page2.PARLAY_PLAYABLE]
        blocked_parlays = [p for p in parlays if p.status in {page2.PARLAY_BLOCKED, page2.PARLAY_AVOID}]
        reason_rows = [f"{name}: {count}" for name, count in scan["reason_counts"].most_common(5)] or ["No rejected market rows were returned by the scan."]
        line_rows = [f"{name}: {count}" for name, count in scan["line_counts"].most_common()] or ["No line data returned."]
        scan_rows = [
            f"Markets scanned: {len(scan['markets'])} · events: {len(scan['events']) or 1} · books: {len(scan['books']) or 0}.",
            f"Positive-EV legs: {scan['positive_ev']} · eligible legs: {len(scan['eligible'])} · watchlist legs: {len(scan['watchlist'])}.",
            f"Parlay candidates: {len(parlays)} · playable: {len(playable)} · blocked/avoid: {len(blocked_parlays)}.",
        ] + line_rows[:2]
        if playable:
            top_rows = [page2._parlay_line(p, lang) for p in playable[:5]]
        else:
            top_rows = [
                f"{page2.STRAIGHT_ANCHOR_ONLY}: no fully verified parlay qualified from the current market pool.",
                "This is not a failure: ABA needs two or more independently verified positive-EV legs before publishing a parlay.",
            ]
        two_leg = [page2._parlay_line(p, lang) for p in playable if "2-leg" in p.parlay_type][:5] or ["No verified 2-leg parlay. Need another independent priced positive-EV leg from a current sportsbook row."]
        watch_rows = [f"WATCHLIST: {_leg_label(page2, m)} · {reason}" for m, reason in scan["watchlist"][:5]] or ["No watchlist legs with positive EV were returned. Increase event/market/book scan coverage."]
        blocked_rows = [f"BLOCKED: {_leg_label(page2, m)} · {reason}" for m, reason in scan["blocked"][:5]] or ["No blocked leg details returned."]
        if blocked_parlays:
            blocked_rows += [f"PARLAY BLOCKED: {p.parlay_type} · {p.reason}" for p in blocked_parlays[:2]]
        unlock_rows = [
            "Scan moneyline, spreads/run lines/puck lines, totals, team totals, and priced props before report selection.",
            "Each leg needs event ID, sportsbook, exact line when required, odds, timestamp, model probability, edge, and EV.",
            "Use cross-game 2-leg parlays first; block same-game parlays unless sportsbook SGP price or correlation model exists.",
        ] + reason_rows[:2]
        source_rows = [
            f"Provider: {diag.get('provider_called', 'unknown')} · state {diag.get('provider_state', 'unknown')}.",
            f"Timestamp: {diag.get('timestamp', 'missing')} · repair status {diag.get('repair_status', 'stable')}.",
            f"Rejection mix: {', '.join(reason_rows[:3])}.",
        ]
        cancel_rows = [
            "Cancel if any leg loses current sportsbook price, exact line, timestamp, or positive EV.",
            "Cancel if same-game correlation is unpriced or a prop lacks prop-specific model probability.",
            "Cancel if live/flash market lacks live clock, score, odds, and provider timestamp.",
        ]
        return [
            ("Market Scan Summary", sanitize_public_items([page2._tr(x, lang) for x in scan_rows]), page2.BLUE),
            ("Top Parlay Recommendations", sanitize_public_items([page2._tr(x, lang) for x in top_rows[:5]]), page2.BLUE),
            ("Best 2-Leg Parlays", sanitize_public_items([page2._tr(x, lang) for x in two_leg[:5]]), page2.BLUE),
            ("Watchlist Legs", sanitize_public_items([page2._tr(x, lang) for x in watch_rows[:5]]), page2.GOLD),
            ("Blocked / Why", sanitize_public_items([page2._tr(x, lang) for x in blocked_rows[:5]]), page2.RED),
            ("Data Needed to Unlock", sanitize_public_items([page2._tr(x, lang) for x in unlock_rows[:5]]), page2.GOLD),
            ("Source Diagnostics", sanitize_public_items([page2._tr(x, lang) for x in source_rows]), page2.BLUE),
            ("Cancel Conditions", sanitize_public_items([page2._tr(x, lang) for x in cancel_rows]), page2.RED),
        ]

    def enhanced_final_status(
        data: dict[str, Any],
        lang: str,
        *,
        parlays=None,
        diagnostics=None,
    ):
        if callable(original_final_status):
            title, detail, color = original_final_status(
                data,
                lang,
                parlays=parlays,
                diagnostics=diagnostics,
            )
        else:
            title, detail, color = page2.NO_VERIFIED_PARLAY_AVAILABLE, "No verified parlay available.", page2.GOLD
        scan = _market_scan(page2, data)
        if title == page2.STRAIGHT_ANCHOR_ONLY or "No verified" in detail:
            detail = (
                f"{detail} Market pool: {len(scan['markets'])} scanned, {len(scan['eligible'])} eligible, "
                f"{len(scan['watchlist'])} watchlist, top gap: "
                f"{next(iter(scan['reason_counts']), 'need more current provider markets')}."
            )
        return title, page2._tr(detail, lang), color

    def enhanced_advanced_market_diagnostics(pick: Any) -> dict[str, Any]:
        base = original_advanced(pick) if callable(original_advanced) else {}
        data = _row(pick)
        scan = _market_scan(page2, data)
        base.update({
            "patch_version": PATCH_VERSION,
            "market_scan_summary": {
                "markets_scanned": len(scan["markets"]),
                "events_scanned": len(scan["events"]) or 1,
                "books_scanned": len(scan["books"]),
                "positive_ev_legs": scan["positive_ev"],
                "eligible_legs": len(scan["eligible"]),
                "watchlist_legs": len(scan["watchlist"]),
                "rejection_reasons": dict(scan["reason_counts"]),
                "line_status": dict(scan["line_counts"]),
            },
            "watchlist_leg_pool": [asdict(m) | {"clear_reason": reason} for m, reason in scan["watchlist"][:20]],
            "blocked_leg_pool": [asdict(m) | {"clear_reason": reason} for m, reason in scan["blocked"][:20]],
            "parlay_unlock_requirements": [
                "At least two current-provider eligible legs.",
                "Exact line required for spreads, totals, team totals, and props.",
                "Sportsbook-level price and fresh timestamp required.",
                "Positive edge and positive EV required for every leg.",
                "Same-game parlay requires sportsbook-returned SGP price or modeled correlation.",
            ],
        })
        return base

    page2._page_two_sections = enhanced_sections
    page2._final_status = enhanced_final_status
    page2.advanced_market_diagnostics = enhanced_advanced_market_diagnostics
    page2._ABA_PARLAY_INTELLIGENCE_PATCH = PATCH_VERSION


def _install_report_gate_patch() -> None:
    try:
        from autonomous_betting_agent import report_verification_gate as gate
    except Exception:
        return
    if getattr(gate, "_ABA_PARLAY_INTELLIGENCE_PATCH", "") == PATCH_VERSION:
        return
    original = getattr(gate, "_no_verified_row", None)
    if not callable(original):
        return

    def no_verified_with_intelligence(summary: Mapping[str, Any]):
        rows = original(summary)
        return [enrich_no_verified_report_row(row, summary) for row in rows]

    gate._no_verified_row = no_verified_with_intelligence
    gate._ABA_PARLAY_INTELLIGENCE_PATCH = PATCH_VERSION


def _install_magazine_patch(module: Any | None = None) -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as magazine
    except Exception:
        return
    if module is not None:
        magazine = module
    if getattr(magazine, "_ABA_PARLAY_INTELLIGENCE_PATCH", "") == PATCH_VERSION:
        return
    original_team = getattr(magazine, "_team_items", None)
    original_injury = getattr(magazine, "_injury_items", None)
    original_matchup = getattr(magazine, "_matchup_items", None)

    def team_items(row: Any, side: str = ""):
        data = enrich_no_verified_report_row(row)
        if _is_no_verified(data):
            key = "away_team_form" if side == "away" else "home_team_form"
            return [part.strip() for part in _clean(data.get(key)).split(";") if part.strip()][:4]
        return original_team(row, side) if callable(original_team) else []

    def injury_items(row: Any, prefix: str):
        data = enrich_no_verified_report_row(row)
        if _is_no_verified(data):
            key = "away_injuries" if prefix == "away" else "home_injuries"
            return [part.strip() for part in _clean(data.get(key)).split(";") if part.strip()][:3]
        return original_injury(row, prefix) if callable(original_injury) else []

    def matchup_items(row: Any):
        data = enrich_no_verified_report_row(row)
        if _is_no_verified(data):
            return [part.strip() for part in _clean(data.get("matchup_notes")).split(";") if part.strip()][:3]
        return original_matchup(row) if callable(original_matchup) else []

    magazine._team_items = team_items
    magazine._injury_items = injury_items
    magazine._matchup_items = matchup_items
    magazine._ABA_PARLAY_INTELLIGENCE_PATCH = PATCH_VERSION


def install(module: Any | None = None) -> None:
    _install_report_gate_patch()
    _install_page2_patch()
    _install_magazine_patch(module)
