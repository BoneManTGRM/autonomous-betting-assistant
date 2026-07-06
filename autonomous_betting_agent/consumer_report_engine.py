from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class BrandSettings:
    brand_name: str = "ABA Signal Pro"
    workspace_id: str = "default"
    language: str = "en"
    report_title: str = "Magazine Report"
    primary_color: str = "#1E3A8A"
    secondary_color: str = "#3B82F6"
    accent_color: str = "#10B981"
    font_family: str = "Inter, system-ui, sans-serif"
    logo_url: str = ""
    company_name: str = "ABA Signal Pro"

    def __init__(self, **kwargs: Any) -> None:
        self.brand_name = kwargs.get("brand_name", kwargs.get("company_name", "ABA Signal Pro"))
        self.workspace_id = kwargs.get("workspace_id", "default")
        self.language = kwargs.get("language", "en")
        self.report_title = kwargs.get("report_title", "Magazine Report")
        self.primary_color = kwargs.get("primary_color", "#1E3A8A")
        self.secondary_color = kwargs.get("secondary_color", "#3B82F6")
        self.accent_color = kwargs.get("accent_color", "#10B981")
        self.font_family = kwargs.get("font_family", "Inter, system-ui, sans-serif")
        self.logo_url = kwargs.get("logo_url", "")
        self.company_name = kwargs.get("company_name", self.brand_name)


def _prob(row: pd.Series) -> float:
    try:
        return float(row.get("model_probability", row.get("probability", 0)) or 0)
    except Exception:
        return 0.0


def _market_label(market: str, language: str) -> str:
    market = str(market or "").lower()
    labels = {
        "h2h": ("Moneyline", "Ganador"),
        "moneyline": ("Moneyline", "Ganador"),
        "spread": ("Spread", "Hándicap"),
        "totals": ("Total", "Total"),
        "btts": ("BTTS", "Ambos anotan"),
    }
    en, es = labels.get(market, (market.title() or "Market", market.title() or "Mercado"))
    return es if language == "es" else en


def prepare_report_frame(data: Any, **kwargs: Any) -> pd.DataFrame:
    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data.get("rows", []) if isinstance(data, dict) else data)
    if frame.empty:
        return frame
    min_probability = float(kwargs.get("min_probability", 0) or 0)
    official_only = bool(kwargs.get("official_only", False))
    max_rows = int(kwargs.get("max_rows", len(frame)) or len(frame))
    if official_only and "official_ev_pick" in frame.columns:
        frame = frame[frame["official_ev_pick"].astype(bool)]
    if min_probability:
        probability = frame.get("model_probability", frame.get("probability", pd.Series([0] * len(frame), index=frame.index)))
        frame = frame[pd.to_numeric(probability, errors="coerce").fillna(0) >= min_probability]
    return frame.head(max_rows).reset_index(drop=True)


def consumer_cards(frame: Any, brand: BrandSettings | None = None) -> pd.DataFrame:
    brand = brand or BrandSettings()
    prepared = frame.copy() if isinstance(frame, pd.DataFrame) else prepare_report_frame(frame)
    rows: list[dict[str, Any]] = []
    for _, row in prepared.iterrows():
        probability = _prob(row)
        rows.append({
            "workspace_id": brand.workspace_id,
            "brand_name": brand.brand_name,
            "language": brand.language,
            "event": row.get("event", ""),
            "sport": row.get("sport", ""),
            "market": _market_label(row.get("market_type", row.get("market", "")), brand.language),
            "prediction": row.get("prediction", ""),
            "probability": probability,
            "price": row.get("decimal_price", row.get("decimal_odds", "")),
            "bookmaker": row.get("bookmaker", ""),
            "proof_id": row.get("proof_id", ""),
            "proof_status": row.get("proof_status", ""),
            "bullet_1": (f"El modelo proyecta {probability:.0%} de probabilidad." if brand.language == "es" else f"Model projects {probability:.0%} probability."),
            "bullet_2": (f"Tendencia: {row.get('agent_decision', 'review')}" if brand.language == "es" else f"Trend: {row.get('agent_decision', 'review')}"),
            "edge": row.get("model_edge", row.get("expected_value_per_unit", "")),
        })
    return pd.DataFrame(rows)


def cards_to_json(cards: Any, brand: BrandSettings | None = None) -> str:
    brand = brand or BrandSettings()
    payload = {
        "brand": {"brand_name": brand.brand_name, "workspace_id": brand.workspace_id, "language": brand.language},
        "cards": cards.to_dict(orient="records") if isinstance(cards, pd.DataFrame) else cards,
    }
    return json.dumps(payload, default=str, ensure_ascii=False)


def render_consumer_cards_html(cards: Any, brand: BrandSettings | None = None) -> str:
    brand = brand or BrandSettings()
    frame = cards if isinstance(cards, pd.DataFrame) else pd.DataFrame(cards)
    parts = [f"<section><h1>{html.escape(brand.brand_name)}</h1>"]
    for _, row in frame.iterrows():
        parts.append("<article class='consumer-card'>")
        for key in ["event", "market", "prediction", "bullet_1", "bullet_2", "proof_id"]:
            parts.append(f"<p><b>{html.escape(key)}</b>: {html.escape(str(row.get(key, '')))}</p>")
        parts.append("</article>")
    parts.append("</section>")
    return "".join(parts)


def render_magazine_markdown(cards: Any, brand: BrandSettings | None = None) -> str:
    brand = brand or BrandSettings()
    frame = cards if isinstance(cards, pd.DataFrame) else pd.DataFrame(cards)
    trend_label = "Tendencia" if brand.language == "es" else "Trend"
    lines = [f"# {brand.report_title}", f"Brand: {brand.brand_name}", f"Workspace: {brand.workspace_id}", ""]
    for _, row in frame.iterrows():
        lines.extend([
            f"## {row.get('event', '')}",
            f"Pick: {row.get('prediction', '')}",
            f"Market: {row.get('market', '')}",
            f"{trend_label}: {row.get('bullet_2', '')}",
            f"Proof: {row.get('proof_id', '')}",
            "",
        ])
    return "\n".join(lines)


def generate_consumer_report(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": data.get("report_id", "rpt_001"),
        "brand": BrandSettings(),
        "sections": data.get("sections", []),
        "generated_at": "2026-07-04T20:00:00Z",
    }


def generate_modeled_parlays(anchor: dict, legs: list[dict]) -> list[dict]:
    candidates = []
    if not legs:
        return candidates
    for i, leg in enumerate(legs[:3]):
        combo = {
            "legs": [anchor, leg] if i == 0 else [anchor, legs[0], leg],
            "type": f"{2 if i == 0 else 3}-leg modeled",
            "correlation": 0.65,
            "combined_ev": anchor.get("ev", 0) + leg.get("ev", 0),
        }
        if combo["combined_ev"] > 0:
            candidates.append(combo)
    return candidates
