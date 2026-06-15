from __future__ import annotations

import io
import math
import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

TEXT = {
    "en": {
        "section": "What Are the Odds / CSV Odds Breakdown",
        "caption": "Analyze a Pro Predictor report or uploaded CSV for winner odds, no-vig fair odds, edge, EV, score estimate, spread/total, round/method, home run, and prop-style fields.",
        "note": "Best accuracy comes when the CSV contains every outcome in a market. If the file only has one pick per event, the tool still calculates raw implied edge, fair odds, EV, and score estimates, while no-vig fields stay blank.",
        "latest": "Use latest Pro Predictor results from this run",
        "upload": "Upload odds/report CSV",
        "paste": "Or paste CSV text",
        "depth": "Report depth",
        "simple": "Simple",
        "detailed": "Detailed",
        "full": "Full ARA",
        "analyze": "Analyze odds",
        "waiting": "Run Pro Predictor first, or upload/paste a CSV here.",
        "source": "Source",
        "rows": "Rows analyzed",
        "candidates": "Candidate rows",
        "score_rows": "Score estimates",
        "official_props": "Official/csv props",
        "main": "Main odds report",
        "extras": "Scores, props, and extras",
        "diag": "Diagnostics",
        "summary": "Quick summary",
        "download_main": "Download odds breakdown CSV",
        "download_props": "Download scores/props CSV",
        "no_props": "No round, home run, or official prop fields were detected. Score estimates still appear here when the model can infer them.",
        "missing_prob": "Some rows have no model probability. Check Diagnostics to see which probability column was detected.",
        "no_vig_note": "No-vig requires multiple outcomes for the same event/market. This file appears to contain one selected pick per event, so raw implied edge is more useful than no-vig.",
        "top_value": "Top value candidates",
    },
    "es": {
        "section": "Qué dicen las cuotas / Desglose CSV",
        "caption": "Analiza un reporte de Predictor Pro o CSV subido para ganador, cuotas justas sin margen, ventaja, EV, marcador estimado, spread/total, round/método, home run y campos tipo prop.",
        "note": "La mejor precisión llega cuando el CSV contiene todos los resultados de un mercado. Si el archivo solo tiene un pick por evento, aún calcula ventaja implícita bruta, cuotas justas, EV y marcador estimado, mientras los campos sin margen quedan en blanco.",
        "latest": "Usar resultados más recientes de Predictor Pro",
        "upload": "Subir CSV de cuotas/reporte",
        "paste": "O pegar texto CSV",
        "depth": "Profundidad del reporte",
        "simple": "Simple",
        "detailed": "Detallado",
        "full": "ARA completo",
        "analyze": "Analizar cuotas",
        "waiting": "Ejecuta Predictor Pro primero, o sube/pega un CSV aquí.",
        "source": "Fuente",
        "rows": "Filas analizadas",
        "candidates": "Filas candidatas",
        "score_rows": "Marcadores estimados",
        "official_props": "Props oficiales/csv",
        "main": "Reporte principal de cuotas",
        "extras": "Marcadores, props y extras",
        "diag": "Diagnóstico",
        "summary": "Resumen rápido",
        "download_main": "Descargar desglose de cuotas CSV",
        "download_props": "Descargar marcadores/props CSV",
        "no_props": "No se detectaron campos de round, home run o props oficiales. Los marcadores estimados aún aparecen aquí cuando el modelo puede inferirlos.",
        "missing_prob": "Algunas filas no tienen probabilidad del modelo. Revisa Diagnóstico para ver qué columna de probabilidad se detectó.",
        "no_vig_note": "Sin margen requiere varios resultados del mismo evento/mercado. Este archivo parece contener un pick por evento, así que la ventaja implícita bruta es más útil que sin-margen.",
        "top_value": "Mejores candidatos de valor",
    },
}

ES_COLS = {
    "event": "evento",
    "sport": "deporte",
    "market_type": "tipo_mercado",
    "prediction": "pronostico",
    "model_probability": "probabilidad_modelo",
    "market_probability": "probabilidad_mercado",
    "best_price": "mejor_cuota",
    "decimal_price": "cuota_decimal",
    "implied_probability": "probabilidad_implicita",
    "no_vig_implied_probability": "probabilidad_sin_margen",
    "market_hold": "margen_casa",
    "model_minus_implied": "modelo_menos_implicita",
    "model_minus_no_vig": "modelo_menos_sin_margen",
    "edge_source": "fuente_ventaja",
    "fair_decimal_price": "cuota_justa_decimal",
    "fair_american_price": "cuota_justa_americana",
    "computed_ev_decimal": "ev_calculado_decimal",
    "estimated_ev": "ev_estimado_original",
    "odds_quality_score": "puntaje_calidad_cuotas",
    "decision": "decision",
    "decision_reason": "razon_decision",
    "confidence": "confianza",
    "books": "casas",
    "api_coverage_score": "puntaje_cobertura_api",
    "estimated_score": "marcador_estimado",
    "score_source": "fuente_marcador",
    "score_note": "nota_marcador",
    "warning": "advertencia",
    "prop_type": "tipo_prop",
    "prop_estimate": "estimacion_prop",
    "source": "fuente",
    "note": "nota",
}
ES_VALUES = {
    "strong_candidate": "candidato_fuerte",
    "candidate": "candidato",
    "watch_only": "solo_vigilar",
    "skip": "omitir",
    "model_estimate": "estimacion_modelo",
    "csv_market_or_field": "mercado_o_campo_csv",
    "csv_field": "campo_csv",
    "raw_implied_edge": "ventaja_implicita_bruta",
    "no_vig_edge": "ventaja_sin_margen",
    "moneyline/winner": "moneyline/ganador",
}


def _lang() -> str:
    return "es" if str(st.session_state.get("global_language", "English")) == "Español" else "en"


def _t(key: str) -> str:
    return TEXT[_lang()].get(key, TEXT["en"].get(key, key))


def _clean_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _find_col(df: pd.DataFrame, aliases: tuple[str, ...], contains: tuple[str, ...] = ()) -> str | None:
    lookup = {_clean_key(col): col for col in df.columns}
    alias_keys = [_clean_key(alias) for alias in aliases]
    for key in alias_keys:
        if key in lookup:
            return lookup[key]
    compact_lookup = {key.replace("_", ""): col for key, col in lookup.items()}
    for key in alias_keys:
        compact = key.replace("_", "")
        if compact in compact_lookup:
            return compact_lookup[compact]
    contains_keys = [_clean_key(item) for item in contains]
    for col in df.columns:
        col_key = _clean_key(col)
        if any(item and item in col_key for item in contains_keys):
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
    if not text or text.lower() in {"nan", "none", "null", "unknown", "n/a", "pendiente", "desconocido"}:
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


def _decimal_price(value: Any) -> float | None:
    price = _num(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def _pct(value: float | None) -> str:
    return "" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def _round_num(value: float | None, digits: int = 4) -> float | str:
    return "" if value is None or pd.isna(value) else round(float(value), digits)


def _fair_decimal(probability: float | None) -> float | None:
    if probability is None or probability <= 0:
        return None
    return 1.0 / probability


def _fair_american(probability: float | None) -> str:
    if probability is None or probability <= 0 or probability >= 1:
        return ""
    if probability >= 0.5:
        return str(int(round(-100.0 * probability / (1.0 - probability))))
    return f"+{int(round(100.0 * (1.0 - probability) / probability))}"


def _infer_sport(row: pd.Series, explicit: str, columns: list[str]) -> str:
    if explicit and explicit.lower() not in {"unknown", "nan", "none"}:
        return explicit
    all_text = " ".join([str(c) for c in columns] + [str(row.get(c, "")) for c in row.index]).lower()
    if "fifa" in all_text or "soccer" in all_text or "football/soccer" in all_text:
        return "soccer"
    return "unknown"


def _sport_family(sport: str) -> str:
    text = _clean_key(sport)
    if any(token in text for token in ("mma", "ufc", "boxing", "combat", "pfl", "bellator")):
        return "combat"
    if any(token in text for token in ("mlb", "baseball", "beisbol")):
        return "baseball"
    if any(token in text for token in ("nba", "wnba", "basketball", "ncaab", "basquet")):
        return "basketball"
    if any(token in text for token in ("nfl", "ncaaf", "football")) and "soccer" not in text:
        return "football"
    if any(token in text for token in ("soccer", "fifa", "uefa", "liga", "premier", "mls", "futbol")):
        return "soccer"
    if "tennis" in text or "tenis" in text:
        return "tennis"
    if "hockey" in text or "nhl" in text:
        return "hockey"
    return "general"


def _typical_total(family: str) -> float:
    return {"soccer": 2.6, "basketball": 221.0, "football": 45.0, "baseball": 8.5, "hockey": 6.0, "tennis": 23.0, "combat": 1.0}.get(family, 3.0)


def _first_value(row: pd.Series, names: tuple[str, ...]) -> Any:
    lookup = {_clean_key(col): col for col in row.index}
    for name in names:
        col = lookup.get(_clean_key(name))
        if col is not None:
            value = row.get(col)
            if value not in (None, "") and not (isinstance(value, float) and math.isnan(value)):
                return value
    return ""


def _opponent_from_event(event: str, pick: str) -> str:
    event_text = str(event or "")
    pick_text = str(pick or "")
    for sep in (" at ", " vs ", " v ", " @ "):
        if sep in event_text:
            parts = [part.strip() for part in event_text.split(sep, 1)]
            if len(parts) == 2:
                return parts[0] if pick_text.lower() in parts[1].lower() else parts[1]
    return "Opponent" if _lang() == "en" else "Rival"


def _score_estimate(event: str, pick: str, sport: str, probability: float | None, total: float | None, spread: float | None, row: pd.Series) -> tuple[str, str, str]:
    exact = _first_value(row, ("correct_score", "predicted_score", "score_prediction", "estimated_score", "marcador_estimado"))
    if exact not in (None, ""):
        return str(exact), "csv_market_or_field", "Score came from a detected CSV field."
    family = _sport_family(sport)
    if family == "combat":
        return "", "", "not_applicable"
    total_value = total if total is not None and total > 0 else _typical_total(family)
    p = probability if probability is not None else 0.55
    edge = max(-0.45, min(0.45, p - 0.50))
    margin = abs(spread) if spread is not None else abs(edge * {"soccer": 2.2, "basketball": 22, "football": 16, "baseball": 3.2, "hockey": 2.5, "tennis": 6}.get(family, 3))
    winner_score = max(0.0, (total_value + margin) / 2)
    loser_score = max(0.0, total_value - winner_score)
    if family in {"soccer", "baseball", "hockey"}:
        ws, ls = round(winner_score), round(loser_score)
        if pick and p >= 0.50 and ws <= ls:
            ws = ls + 1
    elif family == "tennis":
        ws, ls = max(2, round(winner_score / 7)), max(0, round(loser_score / 7))
    else:
        ws, ls = round(winner_score), round(loser_score)
        if pick and p >= 0.50 and ws <= ls:
            ws = ls + 1
    opponent = _opponent_from_event(event, pick)
    return f"{pick} {ws} - {opponent} {ls}" if pick else f"{ws}-{ls}", "model_estimate", "Estimated from probability, sport type, and any total/spread fields found."


def _combat_round(row: pd.Series, pick: str, probability: float | None) -> tuple[str, str, str]:
    round_value = _first_value(row, ("round", "predicted_round", "method_round", "finish_round", "ronda"))
    method_value = _first_value(row, ("method", "predicted_method", "finish_method", "win_method", "metodo"))
    if round_value or method_value:
        return " / ".join(str(x) for x in (method_value, round_value) if x not in (None, "")), "csv_market_or_field", "Round/method came from a detected CSV field."
    p = probability or 0.55
    if p >= 0.72:
        return f"{pick} by decision or late finish", "model_estimate", "No official round prop found; estimated from strong favorite probability."
    if p >= 0.60:
        return f"{pick} by decision", "model_estimate", "No official round prop found; estimated from moderate favorite probability."
    return "close fight / decision most likely", "model_estimate", "No official round prop found; estimated from near-even probability."


def _home_run(row: pd.Series) -> tuple[str, str, str]:
    value = _first_value(row, ("home_run", "homerun", "hr", "to_hit_a_home_run", "home_run_probability", "jonron"))
    if value not in (None, ""):
        return str(value), "csv_market_or_field", "Home-run market/field was detected in the CSV."
    text = " ".join(str(row.get(col, "")) for col in row.index).lower()
    if "home run" in text or "homerun" in text or " hr" in text or "jonron" in text or "jonrón" in text:
        return "detected in row text", "csv_market_or_field", "Home-run wording was detected in the row."
    return "", "", ""


def _prop_fields(row: pd.Series) -> list[dict[str, Any]]:
    keywords = ("correct_score", "round", "ronda", "method", "metodo", "home_run", "homerun", "hr", "jonron", "td", "touchdown", "goal", "gol", "assist", "asistencia", "strikeout", "ponche", "player", "jugador", "prop", "over_under", "total", "spread", "handicap")
    props: list[dict[str, Any]] = []
    for col in row.index:
        key = _clean_key(col)
        if any(word in key for word in keywords):
            value = row.get(col)
            if value not in (None, "", "nan") and not (isinstance(value, float) and math.isnan(value)):
                props.append({"prop_type": str(col), "prop_estimate": value, "source": "csv_field", "note": "Detected from uploaded CSV column."})
    return props


def _quality(probability: float | None, implied: float | None, no_vig: float | None, books: float | None, api: float | None, confidence: str) -> float:
    score = 0.0
    score += 25 if probability is not None else 0
    score += 20 if implied is not None else 0
    score += 15 if no_vig is not None else 0
    if books is not None:
        score += min(15.0, max(0.0, float(books)) * 2.5)
    if api is not None:
        score += min(15.0, max(0.0, min(1.0, float(api))) * 15.0)
    conf = str(confidence or "").upper()
    score += 10 if "HIGH" in conf or "ALTA" in conf else 5 if "MED" in conf or "MEDIA" in conf else 0
    return round(min(100.0, score), 1)


def _decision(probability: float | None, edge: float | None, ev: float | None, confidence: str, quality: float) -> tuple[str, str]:
    conf = str(confidence or "").upper()
    if probability is None:
        return "watch_only", "Missing model probability."
    if "LOW" in conf or "BAJA" in conf:
        return "skip", "Low-confidence row."
    if quality < 45:
        return "watch_only", "Odds quality is too low or missing too many fields."
    if probability >= 0.70 and (edge is None or edge >= 0.0) and (ev is None or ev >= 0.0):
        return "strong_candidate", "High probability with positive or neutral value indicators."
    if probability >= 0.60 and (edge is None or edge >= -0.015) and (ev is None or ev >= -0.03):
        return "candidate", "Usable probability range; verify price movement and warnings."
    return "watch_only", "Not strong enough for the shortlist."


def _translate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if _lang() != "es" or frame.empty:
        return frame
    out = frame.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(lambda value: ES_VALUES.get(str(value), value))
    return out.rename(columns={col: ES_COLS.get(str(col), str(col)) for col in out.columns})


def build_odds_breakdown(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    columns = list(df.columns)
    event_col = _find_col(df, ("event", "evento", "event_name", "game", "partido", "match", "fixture"))
    sport_col = _find_col(df, ("sport", "deporte", "sport_title", "league", "liga", "competition"))
    pick_col = _find_col(df, ("prediction", "pronostico", "pronóstico", "pick", "seleccion", "selección", "predicted_side", "predicted_winner", "favorite", "favorito"))
    prob_col = _find_col(df, ("model_probability", "probabilidad_modelo", "final_probability_value", "valor_probabilidad_final", "prob_final", "final_probability", "probabilidad_final", "calibrated_probability", "probabilidad_calibrada", "predicted_probability", "probabilidad_pronosticada", "probability", "probabilidad"))
    market_prob_col = _find_col(df, ("market_probability", "market_probability_value", "prob_mercado", "probabilidad_mercado"))
    price_col = _find_col(df, ("best_price", "mejor_cuota", "decimal_price", "decimal_odds", "average_price", "avg_price", "odds", "cuotas", "price", "cuota"))
    market_col = _find_col(df, ("market_type", "tipo_mercado", "market", "mercado", "bet_type", "prop_type"))
    confidence_col = _find_col(df, ("confidence", "confianza", "read", "lectura", "classification", "decision"))
    total_col = _find_col(df, ("total", "line_total", "over_under", "points_total"))
    spread_col = _find_col(df, ("spread", "line_spread", "handicap"))
    ev_col = _find_col(df, ("computed_ev_decimal", "ev_calculado_decimal", "estimated_ev_decimal", "ev_estimado_decimal", "estimated_ev_value", "valor_ev_estimado", "ev", "edge"))
    warning_col = _find_col(df, ("fusion_warning", "warning", "weather_flag", "injury_source_reason", "alerta_clima", "motivo_revisar"))
    books_col = _find_col(df, ("books", "casas", "bookmakers", "bookmaker_count", "source_count"))
    api_col = _find_col(df, ("api_coverage_score", "puntaje_cobertura_api", "api_coverage", "cobertura_api"))

    records: list[dict[str, Any]] = []
    prop_rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        event = str(row.get(event_col, f"row {idx + 1}")) if event_col else f"row {idx + 1}"
        explicit_sport = str(row.get(sport_col, "")) if sport_col else ""
        sport = _infer_sport(row, explicit_sport, columns)
        pick = str(row.get(pick_col, "")) if pick_col else ""
        market_type = str(row.get(market_col, "moneyline/winner")) if market_col else "moneyline/winner"
        probability = _prob(row.get(prob_col)) if prob_col else None
        market_probability = _prob(row.get(market_prob_col)) if market_prob_col else None
        price = row.get(price_col, "") if price_col else ""
        decimal = _decimal_price(price)
        implied = market_probability if market_probability is not None else (None if decimal is None else 1.0 / decimal)
        ev_csv = _num(row.get(ev_col)) if ev_col else None
        computed_ev = None if probability is None or decimal is None else probability * decimal - 1.0
        total = _num(row.get(total_col)) if total_col else None
        spread = _num(row.get(spread_col)) if spread_col else None
        books = _num(row.get(books_col)) if books_col else None
        api = _num(row.get(api_col)) if api_col else None
        if api is not None and api > 1.0:
            api /= 100.0
        confidence = str(row.get(confidence_col, "")) if confidence_col else ""
        score, score_source, score_note = _score_estimate(event, pick, sport, probability, total, spread, row)
        records.append({
            "event": event,
            "sport": sport,
            "market_type": market_type,
            "prediction": pick,
            "model_probability": _pct(probability),
            "market_probability": _pct(market_probability),
            "best_price": price,
            "decimal_price": _round_num(decimal),
            "implied_probability": _pct(implied),
            "estimated_ev": "" if ev_csv is None else round(float(ev_csv), 4),
            "computed_ev_decimal": _round_num(computed_ev),
            "confidence": confidence,
            "books": "" if books is None else int(max(0, round(float(books)))),
            "api_coverage_score": "" if api is None else round(max(0.0, min(1.0, float(api))), 4),
            "estimated_score": score,
            "score_source": score_source,
            "score_note": score_note,
            "warning": row.get(warning_col, "") if warning_col else "",
            "_p": probability,
            "_implied": implied,
            "_ev": computed_ev if computed_ev is not None else ev_csv,
            "_books": books,
            "_api": api,
            "_group": f"{_clean_key(event)}|{_clean_key(market_type)}",
        })
        if score:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "estimated_score", "prop_estimate": score, "source": score_source, "note": score_note})
        family = _sport_family(sport)
        round_value, round_source, round_note = _combat_round(row, pick, probability) if family == "combat" else ("", "", "")
        hr_value, hr_source, hr_note = _home_run(row) if family == "baseball" or any("home" in _clean_key(c) or "hr" == _clean_key(c) for c in row.index) else ("", "", "")
        if round_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "round/method", "prop_estimate": round_value, "source": round_source, "note": round_note})
        if hr_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "home_run", "prop_estimate": hr_value, "source": hr_source, "note": hr_note})
        for prop in _prop_fields(row):
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, **prop})

    main = pd.DataFrame(records)
    if not main.empty:
        implied_sum = main.groupby("_group")['_implied'].transform(lambda s: sum(float(x) for x in s if x is not None and not pd.isna(x)))
        implied_count = main.groupby("_group")['_implied'].transform(lambda s: sum(1 for x in s if x is not None and not pd.isna(x)))
        no_vig_values: list[float | None] = []
        hold_values: list[float | None] = []
        edge_values: list[float | None] = []
        edge_source: list[str] = []
        decisions: list[str] = []
        reasons: list[str] = []
        quality_scores: list[float] = []
        for idx, rec in main.iterrows():
            p = rec["_p"]
            implied = rec["_implied"]
            no_vig = None
            hold = None
            if implied is not None and not pd.isna(implied) and implied_count.loc[idx] >= 2 and implied_sum.loc[idx] > 1.0:
                no_vig = float(implied) / float(implied_sum.loc[idx])
                hold = float(implied_sum.loc[idx]) - 1.0
            edge = None if p is None else (p - no_vig if no_vig is not None else p - implied if implied is not None and not pd.isna(implied) else None)
            quality = _quality(p, implied, no_vig, rec["_books"], rec["_api"], str(rec.get("confidence", "")))
            decision, reason = _decision(p, edge, rec["_ev"], str(rec.get("confidence", "")), quality)
            no_vig_values.append(no_vig)
            hold_values.append(hold)
            edge_values.append(edge)
            edge_source.append("no_vig_edge" if no_vig is not None else "raw_implied_edge")
            decisions.append(decision)
            reasons.append(reason)
            quality_scores.append(quality)
        main["no_vig_implied_probability"] = [_pct(x) for x in no_vig_values]
        main["market_hold"] = [_pct(x) for x in hold_values]
        main["model_minus_implied"] = [_pct((p - i) if p is not None and i is not None and not pd.isna(i) else None) for p, i in zip(main["_p"], main["_implied"])]
        main["model_minus_no_vig"] = [_pct(x) for x in edge_values]
        main["edge_source"] = edge_source
        main["fair_decimal_price"] = [_round_num(_fair_decimal(p)) for p in main["_p"]]
        main["fair_american_price"] = [_fair_american(p) for p in main["_p"]]
        main["odds_quality_score"] = quality_scores
        main["decision"] = decisions
        main["decision_reason"] = reasons
        order = {"strong_candidate": 3, "candidate": 2, "watch_only": 1, "skip": 0}
        main["_decision_order"] = main["decision"].map(order).fillna(0)
        main = main.sort_values(["_decision_order", "odds_quality_score", "_p"], ascending=[False, False, False])
        main = main.drop(columns=["_p", "_implied", "_ev", "_books", "_api", "_group", "_decision_order"])

    diagnostics = pd.DataFrame([{
        "rows_analyzed": len(df),
        "event_col": event_col or "missing",
        "sport_col": sport_col or "inferred_or_missing",
        "pick_col": pick_col or "missing",
        "probability_col": prob_col or "missing",
        "market_probability_col": market_prob_col or "missing",
        "price_col": price_col or "missing",
        "market_col": market_col or "default_moneyline_winner",
        "confidence_col": confidence_col or "missing",
        "total_col": total_col or "missing",
        "spread_col": spread_col or "missing",
        "ev_col": ev_col or "missing",
        "warning_col": warning_col or "missing",
        "books_col": books_col or "missing",
        "api_col": api_col or "missing",
        "input_columns": ", ".join(map(str, df.columns)),
    }])
    return main, pd.DataFrame(prop_rows).drop_duplicates(), diagnostics


def _uploaded_or_pasted_csv(key_prefix: str) -> tuple[str, pd.DataFrame | None]:
    uploaded = st.file_uploader(_t("upload"), type=["csv"], key=f"{key_prefix}_odds_breakdown_upload")
    pasted = st.text_area(_t("paste"), height=120, key=f"{key_prefix}_odds_breakdown_paste")
    if uploaded is not None:
        return uploaded.name, pd.read_csv(uploaded)
    if pasted.strip():
        return "pasted_csv", pd.read_csv(io.StringIO(pasted.strip()))
    return "", None


def render_odds_breakdown_section(key_prefix: str = "what_are_the_odds") -> None:
    st.divider()
    with st.expander(_t("section"), expanded=True):
        st.caption(_t("caption"))
        st.info(_t("note"))
        depth = st.selectbox(_t("depth"), [_t("simple"), _t("detailed"), _t("full")], index=1, key=f"{key_prefix}_odds_breakdown_depth")

        latest_df = st.session_state.get("_aba_pro_predictor_latest_report")
        use_latest = False
        if isinstance(latest_df, pd.DataFrame) and not latest_df.empty:
            use_latest = st.checkbox(_t("latest"), value=True, key=f"{key_prefix}_odds_use_latest")
        source_label, raw_df = ("latest_pro_predictor", latest_df.copy()) if use_latest and isinstance(latest_df, pd.DataFrame) else _uploaded_or_pasted_csv(key_prefix)

        if raw_df is None:
            st.caption(_t("waiting"))
            return

        st.metric(_t("rows"), len(raw_df))
        st.caption(f"{_t('source')}: {source_label}")
        if st.button(_t("analyze"), type="primary", use_container_width=True, key=f"{key_prefix}_odds_breakdown_button"):
            main_df, props_df, diagnostics_df = build_odds_breakdown(raw_df)
            st.session_state[f"{key_prefix}_odds_main"] = main_df
            st.session_state[f"{key_prefix}_odds_props"] = props_df
            st.session_state[f"{key_prefix}_odds_diag"] = diagnostics_df

        main_df = st.session_state.get(f"{key_prefix}_odds_main")
        props_df = st.session_state.get(f"{key_prefix}_odds_props")
        diagnostics_df = st.session_state.get(f"{key_prefix}_odds_diag")
        if not isinstance(main_df, pd.DataFrame):
            return

        candidate_count = int(main_df["decision"].isin(["candidate", "strong_candidate"]).sum()) if "decision" in main_df.columns else 0
        score_count = 0 if not isinstance(props_df, pd.DataFrame) or props_df.empty else int((props_df["prop_type"] == "estimated_score").sum())
        csv_prop_count = 0 if not isinstance(props_df, pd.DataFrame) or props_df.empty else int(props_df["source"].astype(str).str.contains("csv", case=False, na=False).sum())
        missing_prob_count = int((main_df["model_probability"].astype(str).str.strip() == "").sum()) if "model_probability" in main_df.columns else len(main_df)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(_t("rows"), len(main_df))
        m2.metric(_t("candidates"), candidate_count)
        m3.metric(_t("score_rows"), score_count)
        m4.metric(_t("official_props"), csv_prop_count)

        if missing_prob_count:
            st.warning(_t("missing_prob"))
        if "no_vig_implied_probability" in main_df.columns and (main_df["no_vig_implied_probability"].astype(str).str.strip() == "").all():
            st.info(_t("no_vig_note"))

        tabs = st.tabs([_t("summary"), _t("main"), _t("extras"), _t("diag")])
        with tabs[0]:
            summary_cols = ["event", "sport", "prediction", "model_probability", "best_price", "implied_probability", "model_minus_implied", "computed_ev_decimal", "odds_quality_score", "decision", "estimated_score"]
            display = main_df[[col for col in summary_cols if col in main_df.columns]].copy()
            st.dataframe(_translate_frame(display), use_container_width=True, hide_index=True)
            top = main_df[main_df.get("decision", pd.Series(dtype=str)).isin(["strong_candidate", "candidate"])].head(10) if "decision" in main_df.columns else pd.DataFrame()
            if not top.empty:
                st.write(_t("top_value"))
                st.dataframe(_translate_frame(top[[col for col in summary_cols if col in top.columns]]), use_container_width=True, hide_index=True)
        with tabs[1]:
            if depth == _t("simple"):
                display_cols = ["event", "sport", "prediction", "model_probability", "best_price", "implied_probability", "model_minus_implied", "decision", "estimated_score"]
                display = main_df[[col for col in display_cols if col in main_df.columns]].copy()
            else:
                display = main_df.copy()
            st.dataframe(_translate_frame(display), use_container_width=True, hide_index=True)
            download_df = _translate_frame(main_df)
            st.download_button(_t("download_main"), data=download_df.to_csv(index=False), file_name="what_are_the_odds_breakdown.csv", mime="text/csv", key=f"{key_prefix}_odds_main_download")
        with tabs[2]:
            if not isinstance(props_df, pd.DataFrame) or props_df.empty:
                st.info(_t("no_props"))
            else:
                st.dataframe(_translate_frame(props_df), use_container_width=True, hide_index=True)
                st.download_button(_t("download_props"), data=_translate_frame(props_df).to_csv(index=False), file_name="what_are_the_odds_scores_props.csv", mime="text/csv", key=f"{key_prefix}_odds_props_download")
        with tabs[3]:
            if isinstance(diagnostics_df, pd.DataFrame):
                st.dataframe(_translate_frame(diagnostics_df), use_container_width=True, hide_index=True)
            if depth != _t("full"):
                st.caption("Choose Full ARA to show all detail columns in the main report." if _lang() == "en" else "Elige ARA completo para ver todas las columnas detalladas en el reporte principal.")
