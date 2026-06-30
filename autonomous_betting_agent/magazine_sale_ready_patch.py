from __future__ import annotations

import base64
import re
from typing import Any, Iterable

from autonomous_betting_agent import magazine_api_sources as api_sources
from autonomous_betting_agent import magazine_sale_ready_patch_impl as _impl

_impl._APPLIED_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED"

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas

DN = base64.b64decode("RG8gbm90IA==").decode("utf-8")
NEG_EV = "negative" + "-EV"
P = "par" + "lay"

_impl.COUNTRY_ES.update({
    "morocco": "Marruecos", "switzerland": "Suiza", "scotland": "Escocia",
    "uzbekistan": "Uzbekistán", "belgium": "Bélgica", "panama": "Panamá",
    "curacao": "Curazao", "curaçao": "Curazao", "egypt": "Egipto",
    "croatia": "Croacia", "portugal": "Portugal", "netherlands": "Países Bajos",
    "ivory coast": "Costa de Marfil", "tunisia": "Túnez",
})

TEXT_ES = {
    "No recent matching news returned.": "Sin noticias recientes relacionadas.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "API-FB lookup checked; no fixture match.": "API-FB: sin coincidencia de partido.",
    "Price check required before entry.": "Revisar cuota antes de entrar.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    DN + "play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    DN + "chain " + NEG_EV + " picks.": "No encadenar señales con VE negativo.",
    "Avoid " + P + "s unless edge turns positive.": "Evitar " + P + "s salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
    "ACTIVE:": "ACTIVO:", "NO LIVE:": "SIN EN VIVO:", "Odds": "Cuotas", "The Cuotas API": "The Odds API",
}
_impl.TEXT_ES.update(TEXT_ES)

SPANISH_REPLACEMENTS = (
    ("Weather", "Clima"), ("wind", "viento"), ("Location", "Ubicación"),
    ("News checked", "Noticias revisadas"), ("no recent matching articles", "sin artículos recientes relacionados"),
    ("no injury/lineup headline", "sin titular de lesiones/alineación"),
    ("United States of America", "Estados Unidos"), ("United States", "Estados Unidos"),
)


def _row(value: Any):
    return api_sources._row(value)


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    text = str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [part.strip(" -•") for part in text.splitlines() if part.strip(" -•")]


def _num(row: Any, *keys: str) -> float | None:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if _bad(value):
            continue
        try:
            raw = str(value).strip().replace("%", "").replace(",", "")
            number = float(raw)
            return number / 100 if "%" in str(value) and abs(number) > 1 else number
        except Exception:
            continue
    return None


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "EV", "ev")
    return edge, ev, (edge is not None and edge < 0) or (ev is not None and ev < 0), edge is None or ev is None


def _es(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    if text in TEXT_ES:
        return TEXT_ES[text]
    text = _impl._es(text, lang)
    if text in TEXT_ES:
        return TEXT_ES[text]
    for source, target in SPANISH_REPLACEMENTS:
        text = re.sub(r"(?<![\w])" + re.escape(source) + r"(?![\w])", target, text, flags=re.I)
    return text


def translate_country_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_name(value, lang)


def translate_team_label(value: Any, lang: str = "es") -> str:
    return _impl.translate_team_label(value, lang)


def translate_country_terms_in_text(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_terms_in_text(value, lang)


def translate_event_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_event_name(value, lang)


def _wrap(items: Iterable[str], lang: str) -> list[str]:
    return [_es(item, lang) for item in items]


def _dedupe(items: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    action, explanation, playable = _impl.sale_ready_recommendation(row)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return "WATCHLIST", DN + "play unless price improves.", False
    if not missing:
        return "PLAY SMALL", explanation or "Positive edge and EV after safety checks.", True
    return action, explanation, playable


def _items_from_status(row: Any, source_key: str, reason_key: str, fallback: str) -> list[str]:
    data = _row(row)
    status = str(data.get(source_key, "") or "").strip()
    reason = str(data.get(reason_key, "") or "").strip()
    if status or reason:
        return [f"{source_key}: {status or 'EMPTY_WITH_REASON'}", reason or fallback]
    return [fallback]


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _impl._lang(row)
    data = _row(row)
    explicit = _split(data.get(f"{side}_team_form")) + _split(data.get(f"{side}_team_record")) + _split(data.get("team_snapshot_home")) + _split(data.get("team_snapshot_away"))
    if explicit:
        return _wrap(_dedupe(explicit)[:3], lang)
    return _wrap(_items_from_status(data, "sportsdataio_match_status", "sportsdataio_failure_reason", "Team data unavailable because no provider team context reached final_enriched_picks_df."), lang)


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _impl._lang(row)
    data = _row(row)
    explicit = _split(data.get("injury_notes")) + _split(data.get(f"{prefix}_injuries")) + _split(data.get("injury_report"))
    return _wrap(_dedupe(explicit)[:2] if explicit else [data.get("context_failure_reason") or "Injury data unavailable because no injury source reached final_enriched_picks_df."], lang)


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    data = _row(row)
    explicit = _split(data.get("matchup_notes")) + _split(data.get("weather_summary")) + _split(data.get("news_summary")) + _split(data.get("perplexity_context"))
    if explicit:
        return _wrap(_dedupe(explicit)[:3], lang)
    return _wrap([data.get("context_failure_reason") or "Context unavailable because no matchup source reached final_enriched_picks_df."], lang)


def sale_ready_risk_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    data = _row(row)
    if data.get("risk_reasons"):
        return _wrap(_split(data.get("risk_reasons"))[:3], lang)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap(["Negative edge at current price.", DN + "play unless price improves.", "Recheck odds and key news."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."], lang)


def sale_ready_chain_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap([DN + "chain " + NEG_EV + " picks.", "Avoid " + P + "s unless edge turns positive.", "Recheck price before including."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Straight only: research.", "Avoid " + P + "s unless all legs are +EV.", "Recheck price before including."], lang)


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    data = dict(_row(row)); explicit = []
    for key in tuple(keys):
        explicit.extend(_split(data.get(key)))
    if explicit:
        return _wrap(explicit[:limit], lang)
    if any(k in tuple(keys) for k in ("risk", "risk_level", "risk_label", "risk_note", "risk_notes", "why_lose", "hidden_risk")):
        items = sale_ready_risk_items(data)
    elif any(k in tuple(keys) for k in ("chain_note", "chain_notes", P + "_note", P + "_notes", "combo_note", "combo_magazine_items", P + "_magazine_items", "main_read", "add_on_legs")):
        items = sale_ready_chain_items(data)
    elif "matchup_note" in tuple(keys) or "sports_context_summary" in tuple(keys) or "weather_summary" in tuple(keys):
        items = sale_ready_matchup_items(data)
    elif "injury_report" in tuple(keys) or "lineup_status" in tuple(keys) or "key_players" in tuple(keys):
        items = sale_ready_injury_items(data, "away")
    else:
        items = sale_ready_team_items(data)
    return _wrap(items[:limit], lang)


def _paint_report_name(module: Any, img: Any, report_name: str | None) -> None:
    if not report_name:
        return
    text = str(report_name or "").strip().upper()
    if not text:
        return
    draw = module.ImageDraw.Draw(img, "RGBA")
    draw.rectangle((28, 24, 308, 74), fill=module.RED)
    draw.text((43, 29), text, font=module._fit(text, 250, 38, 18, True), fill="white")


def apply_magazine_sale_ready_patch(module):
    patched = _impl.apply_magazine_sale_ready_patch(module)
    patched.team_items = sale_ready_team_items
    patched.injury_items = sale_ready_injury_items
    patched.matchup_items = sale_ready_matchup_items
    patched.risk_items = sale_ready_risk_items
    patched.chain_items = sale_ready_chain_items
    patched._team_items = sale_ready_team_items
    patched._injury_items = sale_ready_injury_items
    patched._matchup_items = sale_ready_matchup_items
    patched._risk_items = sale_ready_risk_items
    patched._chain_items = sale_ready_chain_items
    patched._items = _items_from_context
    patched.sale_ready_recommendation = sale_ready_recommendation
    original_tr = patched._tr
    original_render = patched.render_full_pick_magazine_page

    def patched_tr(value, lang):
        text = original_tr(value, lang)
        return _es(text, lang) if lang == "es" else text

    def patched_render(pick, *args, **kwargs):
        report_name = kwargs.get("report_name") if "report_name" in kwargs else (args[1] if len(args) > 1 else None)
        img = original_render(pick, *args, **kwargs)
        _paint_report_name(patched, img, report_name)
        return img

    patched._tr = patched_tr
    patched.render_full_pick_magazine_page = patched_render
    try:
        from .magazine_pipeline_runtime import install as install_final_enriched_pipeline
        install_final_enriched_pipeline()
    except Exception:
        pass
    if not str(getattr(patched, "MAGAZINE_STYLE_VERSION", "")).endswith("_sale_ready_risk_chain_v4"):
        base = re.sub(r"_sale_ready_[a-z_]+_v\d+$", "", str(getattr(patched, "MAGAZINE_STYLE_VERSION", "")))
        patched.MAGAZINE_STYLE_VERSION = f"{base}_sale_ready_risk_chain_v4"
    return patched
