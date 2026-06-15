from __future__ import annotations

import io
import math
from typing import Any

import pandas as pd
import streamlit as st


def _clean_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def _find_col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {_clean_key(col): col for col in df.columns}
    for name in names:
        key = _clean_key(name)
        if key in lookup:
            return lookup[key]
    for col in df.columns:
        key = _clean_key(col)
        if any(_clean_key(name) in key for name in names):
            return col
    return None


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _prob(value: Any) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return number if 0.0 <= number <= 1.0 else None


def _implied(value: Any) -> float | None:
    price = _num(value)
    if price is None:
        return None
    if price > 1.01:
        return 1.0 / price
    if price >= 100:
        return 100.0 / (price + 100.0)
    if price <= -100:
        return abs(price) / (abs(price) + 100.0)
    return None


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def _sport_family(sport: str) -> str:
    text = _clean_key(sport)
    if any(token in text for token in ("mma", "ufc", "boxing", "combat", "pfl", "bellator")):
        return "combat"
    if any(token in text for token in ("mlb", "baseball")):
        return "baseball"
    if any(token in text for token in ("nba", "wnba", "basketball", "ncaab")):
        return "basketball"
    if any(token in text for token in ("nfl", "ncaaf", "football")) and "soccer" not in text:
        return "football"
    if any(token in text for token in ("soccer", "fifa", "uefa", "liga", "premier", "mls")):
        return "soccer"
    if "tennis" in text:
        return "tennis"
    if "hockey" in text or "nhl" in text:
        return "hockey"
    return "general"


def _typical_total(family: str) -> float:
    return {"soccer": 2.6, "basketball": 221.0, "football": 45.0, "baseball": 8.5, "hockey": 6.0, "tennis": 23.0, "combat": 1.0}.get(family, 3.0)


def _score_estimate(pick: str, sport: str, probability: float | None, total: float | None, spread: float | None) -> tuple[str, str, str]:
    family = _sport_family(sport)
    if family == "combat":
        return "", "", "not_applicable"
    total_value = total if total is not None and total > 0 else _typical_total(family)
    p = probability if probability is not None else 0.55
    edge = max(-0.45, min(0.45, p - 0.50))
    margin = spread if spread is not None else edge * {"soccer": 2.2, "basketball": 22, "football": 16, "baseball": 3.2, "hockey": 2.5, "tennis": 6}.get(family, 3)
    winner_score = max(0.0, (total_value + abs(margin)) / 2)
    loser_score = max(0.0, total_value - winner_score)
    if family in {"soccer", "baseball", "hockey"}:
        ws, ls = round(winner_score), round(loser_score)
    elif family == "tennis":
        ws, ls = max(2, round(winner_score / 7)), max(0, round(loser_score / 7))
    else:
        ws, ls = round(winner_score), round(loser_score)
    return f"{pick} {ws} - Opponent {ls}" if pick else f"{ws}-{ls}", "model_estimate", "Estimated from probability, sport type, and any total/spread fields found."


def _first_value(row: pd.Series, names: tuple[str, ...]) -> Any:
    lookup = {_clean_key(col): col for col in row.index}
    for name in names:
        col = lookup.get(_clean_key(name))
        if col is not None and row.get(col) not in (None, ""):
            return row.get(col)
    for col in row.index:
        key = _clean_key(col)
        if any(_clean_key(name) in key for name in names) and row.get(col) not in (None, ""):
            return row.get(col)
    return ""


def _combat_round(row: pd.Series, pick: str, probability: float | None) -> tuple[str, str, str]:
    round_value = _first_value(row, ("round", "predicted_round", "method_round", "finish_round"))
    method_value = _first_value(row, ("method", "predicted_method", "finish_method", "win_method"))
    if round_value or method_value:
        return " / ".join(str(x) for x in (method_value, round_value) if x not in (None, "")), "csv_market_or_field", "Round/method came from a detected CSV field."
    p = probability or 0.55
    if p >= 0.72:
        return f"{pick} by decision or late finish", "model_estimate", "No official round prop found; estimated from strong favorite probability."
    if p >= 0.60:
        return f"{pick} by decision", "model_estimate", "No official round prop found; estimated from moderate favorite probability."
    return "close fight / decision most likely", "model_estimate", "No official round prop found; estimated from near-even probability."


def _home_run(row: pd.Series) -> tuple[str, str, str]:
    value = _first_value(row, ("home_run", "homerun", "hr", "to_hit_a_home_run", "home_run_probability"))
    if value not in (None, ""):
        return str(value), "csv_market_or_field", "Home-run market/field was detected in the CSV."
    text = " ".join(str(row.get(col, "")) for col in row.index).lower()
    if "home run" in text or "homerun" in text or " hr" in text:
        return "detected in row text", "csv_market_or_field", "Home-run wording was detected in the row."
    return "", "", ""


def _prop_fields(row: pd.Series) -> list[dict[str, Any]]:
    keywords = ("score", "correct_score", "round", "method", "home_run", "homerun", "hr", "td", "touchdown", "goal", "assist", "strikeout", "player", "prop", "over_under", "total", "spread")
    props: list[dict[str, Any]] = []
    for col in row.index:
        key = _clean_key(col)
        if any(word in key for word in keywords):
            value = row.get(col)
            if value not in (None, "", "nan") and not (isinstance(value, float) and math.isnan(value)):
                props.append({"prop_type": str(col), "prop_estimate": value, "source": "csv_field", "note": "Detected from uploaded CSV column."})
    return props


def build_odds_breakdown(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_col = _find_col(df, ("event", "event_name", "game", "match", "fixture"))
    sport_col = _find_col(df, ("sport", "sport_title", "league", "competition"))
    pick_col = _find_col(df, ("prediction", "pick", "predicted_side", "predicted_winner", "favorite", "selection"))
    prob_col = _find_col(df, ("final_probability_value", "calibrated_probability", "predicted_probability", "market_probability_value", "probability", "market_probability"))
    price_col = _find_col(df, ("best_price", "decimal_odds", "average_price", "avg_price", "odds", "price"))
    market_col = _find_col(df, ("market_type", "market", "bet_type", "prop_type"))
    confidence_col = _find_col(df, ("confidence", "read", "classification"))
    total_col = _find_col(df, ("total", "line_total", "over_under", "points_total"))
    spread_col = _find_col(df, ("spread", "line_spread", "handicap"))
    ev_col = _find_col(df, ("estimated_ev_decimal", "estimated_ev_value", "ev", "edge"))
    main_rows: list[dict[str, Any]] = []
    prop_rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        event = str(row.get(event_col, f"row {idx + 1}")) if event_col else f"row {idx + 1}"
        sport = str(row.get(sport_col, "unknown")) if sport_col else "unknown"
        pick = str(row.get(pick_col, "")) if pick_col else ""
        probability = _prob(row.get(prob_col)) if prob_col else None
        price = row.get(price_col, "") if price_col else ""
        implied = _implied(price)
        total = _num(row.get(total_col)) if total_col else None
        spread = _num(row.get(spread_col)) if spread_col else None
        score, score_source, score_note = _score_estimate(pick, sport, probability, total, spread)
        main_rows.append({
            "event": event,
            "sport": sport,
            "market_type": str(row.get(market_col, "moneyline/winner")) if market_col else "moneyline/winner",
            "prediction": pick,
            "model_probability": _pct(probability),
            "best_price": price,
            "implied_probability": _pct(implied),
            "estimated_ev": row.get(ev_col, "") if ev_col else "",
            "confidence": str(row.get(confidence_col, "")) if confidence_col else "",
            "estimated_score": score,
            "score_source": score_source,
            "score_note": score_note,
        })
        family = _sport_family(sport)
        round_value, round_source, round_note = _combat_round(row, pick, probability) if family == "combat" else ("", "", "")
        hr_value, hr_source, hr_note = _home_run(row) if family == "baseball" or any("home" in _clean_key(c) or "hr" == _clean_key(c) for c in row.index) else ("", "", "")
        if round_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "round/method", "prop_estimate": round_value, "source": round_source, "note": round_note})
        if hr_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "home_run", "prop_estimate": hr_value, "source": hr_source, "note": hr_note})
        for prop in _prop_fields(row):
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, **prop})
    diagnostics = pd.DataFrame([{"rows_analyzed": len(df), "event_col": event_col or "missing", "sport_col": sport_col or "missing", "pick_col": pick_col or "missing", "probability_col": prob_col or "missing", "price_col": price_col or "missing", "market_col": market_col or "missing", "total_col": total_col or "missing", "spread_col": spread_col or "missing", "ev_col": ev_col or "missing"}])
    return pd.DataFrame(main_rows), pd.DataFrame(prop_rows).drop_duplicates(), diagnostics


def _read_csv_upload(key_prefix: str) -> pd.DataFrame | None:
    uploaded = st.file_uploader("Upload odds/report CSV", type=["csv"], key=f"{key_prefix}_odds_breakdown_upload")
    pasted = st.text_area("Or paste CSV text", height=120, key=f"{key_prefix}_odds_breakdown_paste")
    if uploaded is not None:
        return pd.read_csv(uploaded)
    if pasted.strip():
        return pd.read_csv(io.StringIO(pasted.strip()))
    return None


def render_odds_breakdown_section(key_prefix: str = "pro_predictor") -> None:
    st.divider()
    st.subheader("What Are the Odds")
    st.caption("Upload a Pro Predictor CSV or any odds/report CSV to break down winner odds, score estimate, spread/total, round/method, home run, props, EV, and warnings.")
    st.info("Official sportsbook props are used when the CSV contains those markets. Otherwise, score/round/home-run fields are model estimates and are labeled as model_estimate.")
    depth = st.selectbox("Report depth", ["Simple", "Detailed", "Full ARA"], index=1, key=f"{key_prefix}_odds_breakdown_depth")
    raw_df = _read_csv_upload(key_prefix)
    if raw_df is None:
        st.caption("Upload or paste a CSV to analyze all odds/prop-style fields.")
        return
    st.metric("Rows loaded", len(raw_df))
    if st.button("Analyze odds CSV", type="primary", use_container_width=True, key=f"{key_prefix}_odds_breakdown_button"):
        main_df, props_df, diagnostics_df = build_odds_breakdown(raw_df)
        st.session_state[f"{key_prefix}_odds_main"] = main_df
        st.session_state[f"{key_prefix}_odds_props"] = props_df
        st.session_state[f"{key_prefix}_odds_diag"] = diagnostics_df
    main_df = st.session_state.get(f"{key_prefix}_odds_main")
    props_df = st.session_state.get(f"{key_prefix}_odds_props")
    diagnostics_df = st.session_state.get(f"{key_prefix}_odds_diag")
    if isinstance(main_df, pd.DataFrame):
        st.write("Main odds report")
        if depth == "Simple":
            display = main_df[["event", "sport", "prediction", "model_probability", "best_price", "confidence", "estimated_score"]].copy()
        else:
            display = main_df.copy()
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button("Download main odds report", data=main_df.to_csv(index=False), file_name="pro_predictor_odds_breakdown.csv", mime="text/csv", key=f"{key_prefix}_odds_main_download")
    if isinstance(props_df, pd.DataFrame):
        st.write("Props and extras")
        if props_df.empty:
            st.info("No score, round, home run, or prop fields were detected. The page still produced a winner/market odds report from available columns.")
        else:
            st.dataframe(props_df, use_container_width=True, hide_index=True)
            st.download_button("Download props/extras report", data=props_df.to_csv(index=False), file_name="pro_predictor_props_breakdown.csv", mime="text/csv", key=f"{key_prefix}_odds_props_download")
    if isinstance(diagnostics_df, pd.DataFrame) and depth == "Full ARA":
        st.write("Diagnostics")
        st.dataframe(diagnostics_df, use_container_width=True, hide_index=True)
