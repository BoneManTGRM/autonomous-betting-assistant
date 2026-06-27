from __future__ import annotations

from typing import Any, Iterable, Mapping

BAD = {"", "nan", "none", "null", "n/a", "na", "--"}


def row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip().lower() not in BAD:
            return str(value).strip()
    return default


def number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None or str(value).strip().lower() in BAD:
            continue
        try:
            raw = str(value).replace("%", "").replace(",", "").strip()
            out = float(raw)
            if "%" in str(value) and abs(out) > 1:
                out /= 100
            return out
        except Exception:
            continue
    return None


def market(data: Mapping[str, Any], language: str) -> str:
    blob = f"{text(data, 'market_type', 'bet_type', 'market')} {text(data, 'pick', 'prediction', 'selection', 'public_pick')}".lower()
    if "corner" in blob or "córner" in blob:
        return "Córners" if language == "es" else "Corners"
    if "btts" in blob or "both teams" in blob or "ambos" in blob:
        return "Ambos equipos anotan" if language == "es" else "Both Teams To Score"
    if "double chance" in blob or "doble oportunidad" in blob:
        return "Doble oportunidad" if language == "es" else "Double Chance"
    if "over" in blob or "under" in blob or "más de" in blob or "menos de" in blob:
        return "Más/Menos" if language == "es" else "Over/Under"
    if "home" in blob or "away" in blob or "local" in blob or "visitante" in blob:
        return "Local/Visitante" if language == "es" else "Home/Away"
    return text(data, "market_type", "bet_type", "market", default="Mercado" if language == "es" else "Market")


def item_ok(data: Mapping[str, Any], minimum: float) -> dict[str, Any] | None:
    price = number(data, "decimal_price", "odds", "best_price")
    conf = number(data, "confidence", "model_probability", "final_probability")
    edge = number(data, "model_market_edge", "edge")
    value = number(data, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    if price is None or conf is None:
        return None
    if conf > 1:
        conf /= 100
    if edge is not None and abs(edge) > 1:
        edge /= 100
    if price <= 0 or conf < minimum:
        return None
    if (edge is not None and edge < 0) or (value is not None and value < 0):
        return None
    status = " ".join(str(data.get(key, "")) for key in ("learning_status", "consumer_action", "recommended_action", "data_issue_reason")).lower()
    if any(token in status for token in ("blocked", "stale", "research only", "no play")):
        return None
    out = dict(data)
    out["_ml_price"] = price
    out["_ml_conf"] = max(0.0, min(conf, 0.98))
    return out


def event_key(data: Mapping[str, Any]) -> str:
    return " ".join(text(data, "event", "public_event", "matchup", "event_name", default="unknown").lower().split())


def different_events(items: list[Mapping[str, Any]]) -> bool:
    keys = [event_key(item) for item in items]
    return len(keys) == len(set(keys))


def build(rows: Iterable[Any]) -> dict[str, Any] | None:
    source = [dict(row(item)) for item in rows]
    for lane, threshold, count in (("safe_two", 0.62, 2), ("value_two", 0.58, 2), ("higher_three", 0.60, 3)):
        pool = [item_ok(item, threshold) for item in source]
        pool = [item for item in pool if item is not None]
        pool.sort(key=lambda item: (float(item["_ml_conf"]), float(item["_ml_price"])), reverse=True)
        chosen = pool[:count]
        if len(chosen) == count and different_events(chosen):
            combo_price = 1.0
            combo_conf = 1.0
            for item in chosen:
                combo_price *= float(item["_ml_price"])
                combo_conf *= float(item["_ml_conf"])
            return {"lane": lane, "items": chosen, "price": combo_price, "confidence": combo_conf * 0.92}
    return None


def label_lane(value: str, language: str) -> str:
    if language == "es":
        return {"safe_two": "Parlay más seguro de 2 selecciones", "value_two": "Parlay de valor de 2 selecciones", "higher_three": "Parlay de mayor riesgo de 3 selecciones"}.get(value, value)
    return {"safe_two": "Safer 2-leg parlay", "value_two": "Value 2-leg parlay", "higher_three": "Higher-risk 3-leg parlay"}.get(value, value)


def format_items(rows: Iterable[Any], language: str = "en", limit: int = 3) -> list[str]:
    source = [dict(row(item)) for item in rows]
    built = build(source)
    if not built:
        return ["No se recomienda parlay", "No hay suficientes selecciones compatibles.", "Faltan cuotas verificadas."][:limit] if language == "es" else ["No parlay recommended", "Not enough compatible selections.", "Verified odds are missing."][:limit]
    lines = [label_lane(str(built["lane"]), language)]
    for item in built["items"][:2]:
        choice = text(item, "pick", "selection", "prediction", "public_pick", default="Selection")
        lines.append(f"{choice} ({market(item, language)}) @ {float(item['_ml_price']):.2f}")
    if len(lines) < limit:
        price_label = "Cuota combinada" if language == "es" else "Combined odds"
        prob_label = "Probabilidad estimada" if language == "es" else "Estimated probability"
        lines.append(f"{price_label}: {float(built['price']):.2f} · {prob_label}: {float(built['confidence']):.0%}")
    return lines[:limit]
