from dataclasses import dataclass, fields
import hashlib
import html as html_lib
import json
from typing import Any, Mapping

import pandas as pd

from autonomous_betting_agent.pdf_report import render_report_pdf
from autonomous_betting_agent.report_feed_service import build_report_feed
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat
from autonomous_betting_agent.report_product_layer import (
    MagazineBrand,
    cards_to_json,
    event_text,
    grouped_report,
    pick_text,
    render_consumer_magazine_html,
    render_markdown_summary,
    safe_text,
    value_text,
)
from autonomous_betting_agent.report_summary import build_report_summary_bundle
from autonomous_betting_agent.two_page_decision_export import build_two_page_decision_export
from autonomous_betting_agent.report_verification_gate import VERSION as VERIFICATION_GATE_VERSION, classify_report_row


@dataclass(frozen=True)
class ReportExportBundle:
    html: str
    markdown: str
    whatsapp: str
    json_text: str
    csv_text: str
    pdf_bytes: bytes
    feed: dict[str, Any]
    summary_markdown: str = ""
    summary_csv_text: str = ""
    summary_table: dict[str, Any] | None = None
    decision_markdown: str = ""
    decision_csv_text: str = ""
    provider_capability_csv_text: str = ""
    page1_decision: dict[str, Any] | None = None
    page2_decision: dict[str, Any] | None = None
    provider_capabilities: list[dict[str, Any]] | None = None
    verification_manifest: dict[str, Any] | None = None


def clean_legacy_report_labels(text: str) -> str:
    return (
        str(text or "")
        .replace("No Play / Removed", "Research / Learning")
        .replace("No Play", "Research / Learning")
        .replace("No play", "Research / Learning")
        .replace("No jugar / removidas", "Investigación / aprendizaje")
        .replace("No jugar", "Investigación / aprendizaje")
    )


def _brand_from(brand: MagazineBrand | Mapping[str, Any]) -> MagazineBrand:
    if isinstance(brand, MagazineBrand):
        return brand
    allowed = {field.name for field in fields(MagazineBrand)}
    return MagazineBrand(**{key: value for key, value in dict(brand).items() if key in allowed})


def _render_summary_html(markdown: str) -> str:
    lines = ["<section class=\"report-summary-explanations\">", "<hr>"]
    for line in str(markdown or "").splitlines():
        if line.startswith("### "):
            lines.append(f"<h3>{html_lib.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            lines.append(f"<h2>{html_lib.escape(line[3:])}</h2>")
        elif line:
            lines.append(f"<p>{html_lib.escape(line)}</p>")
        else:
            lines.append("<br>")
    lines.append("</section>")
    return "\n".join(lines)


def _verified_cards(cards: pd.DataFrame) -> pd.DataFrame:
    source = cards.copy(deep=True) if isinstance(cards, pd.DataFrame) else pd.DataFrame(cards)
    return pd.DataFrame([classify_report_row(row) for row in source.to_dict("records")])


def _records_sha256(cards: pd.DataFrame) -> str:
    payload = json.dumps(cards.to_dict("records"), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verification_manifest(cards: pd.DataFrame, *, input_sha256: str) -> dict[str, Any]:
    records = cards.to_dict("records")
    counts: dict[str, int] = {}
    for row in records:
        key = str(row.get("report_verification_class") or "UNCLASSIFIED")
        counts[key] = counts.get(key, 0) + 1
    return {
        "schema_version": "aba_report_manifest_v1",
        "verification_gate_version": VERIFICATION_GATE_VERSION,
        "input_sha256": input_sha256,
        "row_count": len(records),
        "classification_counts": counts,
        "live_api_claims": sum(bool(row.get("automated_live_provider_verified")) for row in records),
        "manual_verified_inputs": sum(bool(row.get("manual_verified_input")) for row in records),
    }


def render_whatsapp_report(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, max_items: int = 8) -> str:
    brand_obj = _brand_from(brand)
    language = "es" if str(brand_obj.language or "en").lower().startswith("es") else "en"
    es = language == "es"
    groups = grouped_report(cards)
    sections = (
        ("best_plays", "Oficial +EV" if es else "Official +EV"),
        ("watchlist", "Seguimiento de precio" if es else "Price Watch"),
        ("no_play", "Investigación / aprendizaje" if es else "Research / Learning"),
    )
    lines = [value_text(brand_obj.report_title, language), f"{brand_obj.brand_name} — {value_text(brand_obj.tagline, language)}", ""]
    for key, title in sections:
        section = groups.get(key, pd.DataFrame())
        lines.append(title)
        if section.empty:
            lines.append("— " + ("Sin tarjetas." if es else "No cards."))
        for _, row in section.head(max_items).iterrows():
            item = row.to_dict()
            event = event_text(item.get("public_event") or item.get("event") or "Matchup", language)
            pick = pick_text(item.get("public_pick") or item.get("prediction"), language)
            action = value_text(item.get("consumer_action") or item.get("recommended_action"), language)
            result = value_text(safe_text(item.get("result_status")) or "PENDING", language)
            learning = value_text(item.get("learning_status"), language)
            market = value_text(item.get("market_read"), language)
            lines.append(f"— {event}: {pick}")
            lines.append(f"  {'Acción' if es else 'Action'}: {action}")
            lines.append(f"  {'Resultado' if es else 'Result'}: {result}")
            if learning:
                lines.append(f"  {'Aprendizaje' if es else 'Learning'}: {learning}")
            if market:
                lines.append(f"  {'Mercado' if es else 'Market'}: {market}")
        lines.append("")
    if brand_obj.disclaimer:
        lines.append(value_text(brand_obj.disclaimer, language))
    return clean_legacy_report_labels("\n".join(lines).strip())


def build_report_export_bundle(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = "consumer", public: bool = False) -> ReportExportBundle:
    cards = apply_learning_layer_compat(cards)
    input_sha256 = _records_sha256(cards)
    cards = _verified_cards(cards)
    manifest = _verification_manifest(cards, input_sha256=input_sha256)
    decision = build_two_page_decision_export(cards)
    cards_with_decisions = decision.cards
    summary = build_report_summary_bundle(cards_with_decisions)
    cards_with_summary = summary.rows
    base_html = render_consumer_magazine_html(cards, brand, mode=mode)
    html = clean_legacy_report_labels(base_html + "\n" + _render_summary_html(summary.markdown) + "\n" + _render_summary_html(decision.markdown))
    markdown = clean_legacy_report_labels(render_markdown_summary(cards, brand, mode=mode) + "\n\n" + summary.markdown + "\n\n" + decision.markdown)
    whatsapp = render_whatsapp_report(cards, brand)
    json_text = cards_to_json(cards_with_summary)
    csv_text = summary.csv_text
    pdf_bytes = render_report_pdf(cards, brand, mode=mode, summary_markdown=summary.markdown + "\n\n" + decision.markdown)
    feed = dict(build_report_feed(cards, brand, mode=mode, public=public))
    feed["verification_manifest"] = manifest
    return ReportExportBundle(
        html=html,
        markdown=markdown,
        whatsapp=whatsapp,
        json_text=json_text,
        csv_text=csv_text,
        pdf_bytes=pdf_bytes,
        feed=feed,
        summary_markdown=summary.markdown,
        summary_csv_text=summary.csv_text,
        summary_table=summary.table,
        decision_markdown=decision.markdown,
        decision_csv_text=decision.diagnostics_csv_text,
        provider_capability_csv_text=decision.provider_capability_csv_text,
        page1_decision=decision.page1,
        page2_decision=decision.page2,
        provider_capabilities=decision.provider_capabilities,
        verification_manifest=manifest,
    )
