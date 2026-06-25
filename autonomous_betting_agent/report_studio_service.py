from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

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


def _bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(bool).sum())


def _data_issues(frame: pd.DataFrame) -> int:
    if frame.empty or "data_issue_reason" not in frame.columns:
        return 0
    return int(frame["data_issue_reason"].map(lambda value: bool(safe_text(value))).sum())


def build_report_studio_cards(raw_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, *, filters: ReportStudioFilters | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filters = filters or ReportStudioFilters()
    raw = _to_frame(raw_rows)
    if raw.empty:
        empty = pd.DataFrame()
        return raw, empty, empty, empty
    normalized = normalize_frame(raw)
    filtered = _filter_sports(normalized, filters.selected_sports).head(max(int(filters.max_rows or 1), 1)).copy()
    contextual = _apply_context(filtered, language=filters.language, enabled=filters.include_sports_context)
    enriched = enrich_rows(contextual, language=filters.language)
    cards = apply_learning_layer_compat(enriched)
    cards = _apply_context_preview(cards, language=filters.language)
    return raw, normalized, filtered, cards


def build_report_studio_state(raw_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, brand: MagazineBrand | Mapping[str, Any], *, filters: ReportStudioFilters | None = None, source_note: str = "") -> ReportStudioState:
    filters = filters or ReportStudioFilters()
    brand_obj = _brand_from(brand)
    raw, normalized, filtered, cards = build_report_studio_cards(raw_rows, filters=filters)
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
    context_note = "El contexto deportivo se agrega cuando hay campos o JSON configurado disponible; el contexto no disponible se etiqueta explícitamente." if lang_code(filters.language) == "es" else "Sports context added when fields or configured JSON context are available; unavailable context is labeled explicitly."
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
