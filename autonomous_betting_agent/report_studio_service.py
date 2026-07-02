from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from .magazine_row_ordering import order_magazine_rows
from .report_export_service import ReportExportBundle, build_report_export_bundle
from .report_feed_service import build_report_feed
from .report_learning_layer import calibration_audit
from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, enrich_rows, grouped_report, lang_code, safe_text
from .row_normalizer import normalize_frame
from .sports_context import CONTEXT_UNAVAILABLE, enrich_sports_context


@dataclass(frozen=True)
class ReportStudioFilters:
    selected_sports: tuple[str, ...] = ()
    max_rows: int = 75
    language: str = "en"
    mode: str = "consumer"
    public_feed: bool = False
    include_sports_context: bool = True


@dataclass(frozen=True)
class ReportStudioDiagnostics:
    raw_rows: int
    normalized_rows: int
    filtered_rows: int
    cards: int
    official_publish_ready: int
    client_report_ready: int
    learning_ready: int
    data_issues: int
    source_note: str = ""


@dataclass(frozen=True)
class ReportStudioState:
    raw: pd.DataFrame
    normalized: pd.DataFrame
    filtered: pd.DataFrame
    cards: pd.DataFrame
    groups: dict[str, pd.DataFrame]
    audit: dict[str, pd.DataFrame]
    exports: ReportExportBundle
    feed: dict[str, Any]
    diagnostics: ReportStudioDiagnostics
    filters: ReportStudioFilters
    brand: MagazineBrand
    context_note: str = ""


_SOURCE_COPY = {
    "en": {
        "current-run": (
            "Current run / session rows",
            "Current slate",
            "Current session rows are being used. Verify live odds and news before publishing.",
            "INFO",
        ),
        "uploaded": (
            "Uploaded fallback rows",
            "Uploaded report input",
            "Uploaded rows are being used. Treat as verification-only unless API fields show LIVE.",
            "VERIFY",
        ),
        "saved-handoff": (
            "Saved handoff rows",
            "Saved current handoff",
            "Saved handoff rows are being used. Confirm this is the newest run before publishing.",
            "VERIFY",
        ),
        "ledger-history": (
            "Proof ledger history",
            "Historical proof ledger",
            "This is proof-ledger history, not a live current-slate magazine. Run Pro Predictor/Odds Lock Pro or upload the newest CSV before publishing.",
            "HISTORY_ONLY",
        ),
        "none": ("No report source", "No rows loaded", "No report source is loaded.", "BLOCKED"),
    },
    "es": {
        "current-run": (
            "Filas actuales de sesión",
            "Cartelera actual",
            "Se usan filas actuales de sesión. Verificar cuotas y noticias antes de publicar.",
            "INFO",
        ),
        "uploaded": (
            "Filas subidas / fallback",
            "Entrada subida para reporte",
            "Se usan filas subidas. Tratar como solo verificación salvo que los campos API muestren LIVE.",
            "VERIFICAR",
        ),
        "saved-handoff": (
            "Filas guardadas de traspaso",
            "Traspaso actual guardado",
            "Se usan filas guardadas de traspaso. Confirmar que es la corrida más reciente antes de publicar.",
            "VERIFICAR",
        ),
        "ledger-history": (
            "Historial del ledger de prueba",
            "Ledger histórico de prueba",
            "Esto es historial del ledger de prueba, no una revista en vivo de la cartelera actual. Ejecuta Pro Predictor/Odds Lock Pro o sube el CSV más reciente antes de publicar.",
            "SOLO_HISTORIAL",
        ),
        "none": ("Sin fuente de reporte", "Sin filas cargadas", "No hay fuente de reporte cargada.", "BLOQUEADO"),
    },
}


def _to_frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(list(rows))


def _brand_from(value: MagazineBrand | Mapping[str, Any]) -> MagazineBrand:
    if isinstance(value, MagazineBrand):
        return value
    allowed = set(MagazineBrand.__dataclass_fields__)
    return MagazineBrand(**{key: val for key, val in dict(value).items() if key in allowed})


def _source_mode(source_note: str) -> str:
    text = safe_text(source_note).lower()
    if text.startswith("uploaded:"):
        return "uploaded"
    if text.startswith("session:"):
        return "current-run"
    if text.startswith("saved:"):
        return "saved-handoff"
    if "persistent_proof_ledger" in text or "ledger-history" in text:
        return "ledger-history"
    return "none"


def _source_contract(source_note: str, language: str) -> dict[str, str]:
    lang = lang_code(language)
    mode = _source_mode(source_note)
    label, scope, warning, severity = _SOURCE_COPY.get(lang, _SOURCE_COPY["en"]).get(mode, _SOURCE_COPY.get(lang, _SOURCE_COPY["en"])["none"])
    return {
        "report_source_mode": mode,
        "report_source_label": label,
        "report_data_scope": scope,
        "report_truth_warning": warning,
        "report_truth_severity": severity,
        "report_source_note": safe_text(source_note) or "none",
    }


def _has_live_odds(row: Mapping[str, Any]) -> bool:
    marker = " ".join(safe_text(row.get(key)).lower() for key in ("odds_status", "odds_source", "odds_api_status", "data_source"))
    return "live" in marker and "uploaded" not in marker and "fallback" not in marker


def _has_live_context(row: Mapping[str, Any]) -> bool:
    blocked = ("context unavailable", "not returned", "data unavailable", "uploaded row", "no live")
    for key in ("perplexity_context", "newsapi_summary", "weather_summary", "api_football_summary", "sportsdataio_context", "sports_context_summary"):
        text = safe_text(row.get(key)).lower()
        if text and not any(token in text for token in blocked):
            return True
    return False


def _annotate_source_contract(frame: pd.DataFrame, *, source_note: str, language: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    contract = _source_contract(source_note, language)
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        data = dict(row)
        for key, value in contract.items():
            data[key] = data.get(key) or value
        data["report_live_odds_detected"] = str(_has_live_odds(data))
        data["report_live_context_detected"] = str(_has_live_context(data))
        data["model_mutation_status"] = data.get("model_mutation_status") or "DISABLED_SAFE_MODE"
        data["model_mutation_label"] = data.get("model_mutation_label") or ("Model mutation disabled / safe mode" if lang_code(language) == "en" else "Mutación del modelo desactivada / modo seguro")
        data["gate_status_label"] = data.get("gate_status_label") or ("Gate status" if lang_code(language) == "en" else "Estado del filtro")
        if not _has_live_context(data):
            for key in ("sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_note"):
                if not safe_text(data.get(key)):
                    data[key] = contract["report_truth_warning"]
        rows.append(data)
    return pd.DataFrame(rows)


def _filter_sports(frame: pd.DataFrame, selected_sports: Sequence[str]) -> pd.DataFrame:
    sports = {safe_text(value) for value in selected_sports if safe_text(value)}
    if frame.empty or not sports or "sport" not in frame.columns:
        return frame.copy()
    return frame[frame["sport"].map(safe_text).isin(sports)].copy()


def _apply_context(frame: pd.DataFrame, *, language: str, enabled: bool) -> pd.DataFrame:
    if frame.empty or not enabled:
        return frame.copy()
    return enrich_sports_context(frame.copy(), language=language)


def _apply_context_preview(cards: pd.DataFrame, *, language: str) -> pd.DataFrame:
    if cards.empty or "sports_context_summary" not in cards.columns:
        return cards
    result = cards.copy()
    unavailable = CONTEXT_UNAVAILABLE.get(language, CONTEXT_UNAVAILABLE["en"])
    has_context = result["sports_context_summary"].map(safe_text).ne("").astype(bool) & result["sports_context_summary"].ne(unavailable)
    if "game_preview" in result.columns:
        result.loc[has_context, "game_preview"] = result.loc[has_context, "sports_context_summary"]
    return result


def _canonical_part(value: Any) -> str:
    text = safe_text(value).lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _row_action_text(row: Mapping[str, Any]) -> str:
    return _canonical_part(row.get("consumer_action") or row.get("recommended_action") or row.get("public_action") or row.get("report_lane"))


def _is_research_or_watch_row(row: Mapping[str, Any]) -> bool:
    lane = _canonical_part(row.get("report_lane") or row.get("report_lane_v2"))
    action = _row_action_text(row)
    publish_ready = str(row.get("official_publish_ready") or row.get("publish_ready") or "").strip().lower() in {"true", "1", "yes"}
    if publish_ready or lane in {"best play", "official ev", "official ev play"}:
        return False
    markers = (
        "no play",
        "research",
        "learning",
        "watchlist",
        "price watch",
        "seguimiento",
        "investigacion",
        "investigación",
        "lista de seguimiento",
        "no jugar",
        "momio",
    )
    return any(marker in action for marker in markers) or lane in {"no play", "research", "watchlist", "lista de seguimiento", "investigacion", "investigación"}


def _card_dedupe_key(row: Mapping[str, Any]) -> str:
    event = _canonical_part(row.get("public_event") or row.get("event") or row.get("event_name") or row.get("matchup"))
    action = _row_action_text(row)
    if event and _is_research_or_watch_row(row):
        return f"research-event|{event}"
    fields = (
        event,
        _canonical_part(row.get("public_pick") or row.get("prediction") or row.get("pick") or row.get("selection")),
        _canonical_part(row.get("market_type") or row.get("market")),
        _canonical_part(row.get("line_point") or row.get("line") or row.get("handicap") or row.get("total")),
        action,
    )
    key = "|".join(part for part in fields if part)
    return key or safe_text(row.get("proof_id") or row.get("locked_at_utc") or row.get("source_file"))


def _dedupe_cards(cards: pd.DataFrame) -> pd.DataFrame:
    if cards.empty:
        return cards
    keep: list[Any] = []
    seen: set[str] = set()
    for index, row in cards.iterrows():
        key = _card_dedupe_key(row.to_dict()) or f"row:{index}"
        if key in seen:
            continue
        seen.add(key)
        keep.append(index)
    return cards.loc[keep].reset_index(drop=True)


def _order_cards(cards: pd.DataFrame) -> pd.DataFrame:
    if cards.empty:
        return cards
    ordered = order_magazine_rows(cards.to_dict("records"))
    return pd.DataFrame(ordered).reset_index(drop=True)


def _bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(bool).sum())


def _data_issues(frame: pd.DataFrame) -> int:
    if frame.empty or "data_issue_reason" not in frame.columns:
        return 0
    return int(frame["data_issue_reason"].map(lambda value: bool(safe_text(value))).sum())


def build_report_studio_cards(raw_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, filters: ReportStudioFilters | None = None, source_note: str = "") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filters = filters or ReportStudioFilters()
    raw = _to_frame(raw_rows)
    if raw.empty:
        empty = pd.DataFrame()
        return raw, empty, empty, empty
    raw = _annotate_source_contract(raw, source_note=source_note, language=filters.language)
    normalized = normalize_frame(raw)
    filtered = _filter_sports(normalized, filters.selected_sports).head(max(int(filters.max_rows or 1), 1)).copy()
    contextual = _apply_context(filtered, language=filters.language, enabled=filters.include_sports_context)
    enriched = enrich_rows(contextual, language=filters.language)
    cards = apply_learning_layer_compat(enriched)
    cards = _apply_context_preview(cards, language=filters.language)
    cards = _dedupe_cards(cards)
    cards = _order_cards(cards)
    return raw, normalized, filtered, cards


def build_report_studio_state(raw_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, brand: MagazineBrand | Mapping[str, Any], *, filters: ReportStudioFilters | None = None, source_note: str = "") -> ReportStudioState:
    filters = filters or ReportStudioFilters()
    brand_obj = _brand_from(brand)
    raw, normalized, filtered, cards = build_report_studio_cards(raw_rows, filters, source_note=source_note)
    groups = grouped_report(cards) if not cards.empty else {"best_plays": pd.DataFrame(), "watchlist": pd.DataFrame(), "no_play": pd.DataFrame()}
    audit = calibration_audit(cards, min_sample=10) if not cards.empty else {}
    exports = build_report_export_bundle(cards, brand_obj, mode=filters.mode, public=filters.public_feed)
    feed = build_report_feed(cards, brand_obj, mode=filters.mode, public=filters.public_feed)
    diagnostics = ReportStudioDiagnostics(
        raw_rows=int(len(raw)),
        normalized_rows=int(len(normalized)),
        filtered_rows=int(len(filtered)),
        cards=int(len(cards)),
        official_publish_ready=_bool_count(cards, "official_publish_ready"),
        client_report_ready=_bool_count(cards, "client_report_ready"),
        learning_ready=_bool_count(cards, "learning_ready"),
        data_issues=_data_issues(cards),
        source_note=source_note,
    )
    source_contract = _source_contract(source_note, filters.language)
    context_note = (
        f"Fuente del reporte: {source_contract['report_source_label']} · Alcance: {source_contract['report_data_scope']} · {source_contract['report_truth_warning']}"
        if lang_code(filters.language) == "es"
        else f"Report source: {source_contract['report_source_label']} · Scope: {source_contract['report_data_scope']} · {source_contract['report_truth_warning']}"
    )
    return ReportStudioState(
        raw=raw,
        normalized=normalized,
        filtered=filtered,
        cards=cards,
        groups=groups,
        audit=audit,
        exports=exports,
        feed=feed,
        diagnostics=diagnostics,
        filters=filters,
        brand=brand_obj,
        context_note=context_note,
    )


def report_studio_summary(state: ReportStudioState) -> dict[str, Any]:
    return {
        "raw_rows": state.diagnostics.raw_rows,
        "cards": state.diagnostics.cards,
        "official_publish_ready": state.diagnostics.official_publish_ready,
        "client_report_ready": state.diagnostics.client_report_ready,
        "learning_ready": state.diagnostics.learning_ready,
        "data_issues": state.diagnostics.data_issues,
        "best_plays": int(len(state.groups.get("best_plays", pd.DataFrame()))),
        "watchlist": int(len(state.groups.get("watchlist", pd.DataFrame()))),
        "research": int(len(state.groups.get("no_play", pd.DataFrame()))),
    }
