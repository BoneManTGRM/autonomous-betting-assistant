from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .pdf_report import render_report_pdf
from .report_feed_service import build_report_feed
from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import (
    MagazineBrand,
    cards_to_json,
    grouped_report,
    render_consumer_magazine_html,
    render_markdown_summary,
    safe_text,
)


@dataclass(frozen=True)
class ReportExportBundle:
    html: str
    markdown: str
    whatsapp: str
    json_text: str
    csv_text: str
    pdf_bytes: bytes
    feed: dict[str, Any]


def clean_legacy_report_labels(text: str) -> str:
    return (
        str(text or "")
        .replace("No Play / Removed", "Research / Learning")
        .replace("No Play", "Research / Learning")
        .replace("No play", "Research / Learning")
        .replace("No jugar / removidas", "Investigación / aprendizaje")
        .replace("No jugar", "Investigación / aprendizaje")
    )


def render_whatsapp_report(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, max_items: int = 8) -> str:
    brand_obj = brand if isinstance(brand, MagazineBrand) else MagazineBrand(**{key: value for key, value in dict(brand).items() if key in MagazineBrand.__dataclass_fields__})
    es = str(brand_obj.language or "en").lower().startswith("es")
    groups = grouped_report(cards)
    sections = (
        ("best_plays", "Oficial +EV" if es else "Official +EV"),
        ("watchlist", "Price Watch" if es else "Price Watch"),
        ("no_play", "Investigación / aprendizaje" if es else "Research / Learning"),
    )
    lines = [brand_obj.report_title, f"{brand_obj.brand_name} — {brand_obj.tagline}", ""]
    for key, title in sections:
        section = groups.get(key, pd.DataFrame())
        lines.append(title)
        if section.empty:
            lines.append("— " + ("Sin tarjetas." if es else "No cards."))
        for _, row in section.head(max_items).iterrows():
            item = row.to_dict()
            event = safe_text(item.get("event")) or "Matchup"
            pick = safe_text(item.get("public_pick") or item.get("prediction"))
            action = safe_text(item.get("consumer_action") or item.get("recommended_action"))
            result = safe_text(item.get("result_status")) or "PENDING"
            learning = safe_text(item.get("learning_status"))
            market = safe_text(item.get("market_read"))
            lines.append(f"— {event}: {pick}")
            lines.append(f"  {'Acción' if es else 'Action'}: {action}")
            lines.append(f"  {'Resultado' if es else 'Result'}: {result}")
            if learning:
                lines.append(f"  {'Aprendizaje' if es else 'Learning'}: {learning}")
            if market:
                lines.append(f"  {'Mercado' if es else 'Market'}: {market}")
        lines.append("")
    if brand_obj.disclaimer:
        lines.append(brand_obj.disclaimer)
    return clean_legacy_report_labels("\n".join(lines).strip())


def build_report_export_bundle(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer", public: bool = False) -> ReportExportBundle:
    cards = apply_learning_layer_compat(cards)
    html = clean_legacy_report_labels(render_consumer_magazine_html(cards, brand, mode=mode))
    markdown = clean_legacy_report_labels(render_markdown_summary(cards, brand, mode=mode))
    whatsapp = render_whatsapp_report(cards, brand)
    json_text = cards_to_json(cards)
    csv_text = cards.to_csv(index=False)
    pdf_bytes = render_report_pdf(cards, brand, mode=mode)
    feed = build_report_feed(cards, brand, mode=mode, public=public)
    return ReportExportBundle(html=html, markdown=markdown, whatsapp=whatsapp, json_text=json_text, csv_text=csv_text, pdf_bytes=pdf_bytes, feed=feed)
