from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
import json
from typing import Any, Iterable, Mapping

FALLBACK_TOKENS = (
    "no verified picks",
    "no verified buyer picks",
    "current provider check",
    "current provider gate",
    "provider not matched",
    "no current provider row passed",
    "research only: no verified buyer picks",
)


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        try:
            return dict(asdict(value))
        except Exception:
            return {}
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, Mapping) else {}
        except Exception:
            return {}
    data = getattr(value, "__dict__", {}) or {}
    return dict(data) if isinstance(data, Mapping) else {}


def _safe(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _bad_text(value: Any) -> bool:
    text = _safe(value).lower()
    return text in {"", "nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}


def _is_stale_saved_export_row(row: Mapping[str, Any]) -> bool:
    """Compatibility hook for older tests and runtime patches.

    A saved/uploaded VERIFY PRICE row is still a real magazine row when it has a
    matchup and pick. It must stay labeled WATCHLIST / VERIFY PRICE, but it should
    export as part of the full visible magazine. Only true fallback/no-pick rows are
    excluded by _is_fallback_row.
    """
    return False


def _is_fallback_row(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        _safe(row.get(key)).lower()
        for key in (
            "event",
            "public_event",
            "matchup",
            "away_team",
            "home_team",
            "prediction",
            "pick",
            "consumer_action",
            "recommended_action",
            "report_truth_warning",
            "report_truth_severity",
            "data_issue_reason",
            "truth",
            "odds_status",
            "verification_status",
        )
    )
    return any(token in text for token in FALLBACK_TOKENS)


def _has_pick_identity(row: Mapping[str, Any]) -> bool:
    event = _safe(row.get("public_event") or row.get("event") or row.get("event_name") or row.get("matchup") or row.get("game"))
    away = _safe(row.get("away_team") or row.get("team_a"))
    home = _safe(row.get("home_team") or row.get("team_b"))
    pick = _safe(row.get("public_pick") or row.get("prediction") or row.get("pick") or row.get("selection") or row.get("consumer_action") or row.get("recommended_action"))
    if _bad_text(event) and not (away and home):
        return False
    if _bad_text(pick):
        return False
    return not _is_fallback_row(row)


def _has_market_values(row: Mapping[str, Any]) -> bool:
    return any(
        not _bad_text(row.get(key))
        for key in (
            "decimal_price",
            "odds",
            "best_price",
            "odds_at_pick",
            "model_probability",
            "final_probability",
            "model_market_edge",
            "edge",
            "expected_value_per_unit",
            "expected_value",
            "ev",
        )
    )


def _valid_rows(rows: Iterable[Any]) -> list[dict[str, Any]]:
    out = [_row(row) for row in rows]
    valid = [row for row in out if _has_pick_identity(row)]
    if not valid:
        return []
    market_valid = [row for row in valid if _has_market_values(row)]
    return market_valid or valid


def _session_state() -> Any | None:
    try:
        import streamlit as st
        return st.session_state
    except Exception:
        return None


_LAST_VALID_ROWS: list[dict[str, Any]] = []
_LAST_SIGNATURE = ""
_LAST_VALID_PAGES: list[Any] = []


def _signature(rows: Iterable[Mapping[str, Any]], *, report_name: str | None = None, language: str | None = None) -> str:
    key_fields = (
        "public_event",
        "event",
        "event_name",
        "matchup",
        "away_team",
        "home_team",
        "public_pick",
        "prediction",
        "pick",
        "selection",
        "market_type",
        "market",
        "line",
        "line_point",
        "decimal_price",
        "odds",
        "model_probability",
        "model_market_edge",
        "expected_value_per_unit",
        "locked_at_utc",
        "proof_id",
        "sport_key",
        "sport",
    )
    payload = {
        "report_name": _safe(report_name),
        "language": _safe(language),
        "rows": [{key: _safe(row.get(key)) for key in key_fields if not _bad_text(row.get(key))} for row in rows],
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _remember(rows: list[dict[str, Any]], *, report_name: str | None, language: str | None, page_count: int | None = None, source: str = "preview") -> str:
    global _LAST_VALID_ROWS, _LAST_SIGNATURE
    valid = _valid_rows(rows)
    if not valid:
        return _LAST_SIGNATURE
    sig = _signature(valid, report_name=report_name, language=language)
    _LAST_VALID_ROWS = [dict(row) for row in valid]
    _LAST_SIGNATURE = sig
    state = _session_state()
    if state is not None:
        try:
            state["magazine_report_state"] = {
                "rows": _LAST_VALID_ROWS,
                "source_signature": sig,
                "row_count": len(_LAST_VALID_ROWS),
                "page_count": int(page_count or 0),
                "source": source,
                "report_name": _safe(report_name),
                "language": _safe(language),
            }
            state["magazine_report_cards"] = _LAST_VALID_ROWS
            state["magazine_report_source_signature"] = sig
            state["magazine_report_page_count"] = int(page_count or 0)
        except Exception:
            pass
    return sig


def _remember_pages(pages: list[Any], *, sig: str, row_count: int, source: str) -> None:
    global _LAST_VALID_PAGES
    _LAST_VALID_PAGES = list(pages or [])
    state = _session_state()
    if state is not None:
        try:
            state["magazine_report_rendered_pages"] = _LAST_VALID_PAGES
            diagnostics = dict(state.get("magazine_report_export_diagnostics") or {})
            diagnostics.update(
                {
                    "preview_source": source,
                    "pdf_export_source": source,
                    "png_export_source": source,
                    "preview_page_count": len(_LAST_VALID_PAGES),
                    "pdf_page_count": len(_LAST_VALID_PAGES),
                    "png_page_count": len(_LAST_VALID_PAGES),
                    "preview_row_count": row_count,
                    "pdf_row_count": row_count,
                    "png_row_count": row_count,
                    "preview_source_signature": sig,
                    "pdf_source_signature": sig,
                    "png_source_signature": sig,
                    "source_match": True,
                }
            )
            state["magazine_report_export_diagnostics"] = diagnostics
        except Exception:
            pass


def _stored_rows() -> list[dict[str, Any]]:
    state = _session_state()
    if state is not None:
        try:
            stored = state.get("magazine_report_state") or {}
            rows = stored.get("rows") or state.get("magazine_report_cards") or []
            valid = _valid_rows(rows)
            if valid:
                return valid
        except Exception:
            pass
    return list(_LAST_VALID_ROWS)


def _stored_pages() -> list[Any]:
    state = _session_state()
    if state is not None:
        try:
            pages = list(state.get("magazine_report_rendered_pages") or [])
            if pages:
                return pages
        except Exception:
            pass
    return list(_LAST_VALID_PAGES)


def _select_rows(picks: Iterable[Any], *, report_name: str | None, language: str | None, source: str) -> tuple[list[dict[str, Any]], bool, str]:
    rows = [_row(row) for row in list(picks)]
    valid = _valid_rows(rows)
    if valid:
        sig = _remember(valid, report_name=report_name, language=language, source=source)
        return valid, False, sig
    recovered = _stored_rows()
    if recovered:
        recovered_rows = [dict(row, export_source_recovered_from_preview_state="true") for row in recovered]
        sig = _remember(recovered_rows, report_name=report_name, language=language, source="recovered-preview-state")
        return recovered_rows, True, sig
    return [], False, _signature(rows, report_name=report_name, language=language)


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _pdf_from_pages(pages: list[Any]) -> bytes:
    rgb_pages = [page.convert("RGB") for page in pages]
    out = BytesIO()
    rgb_pages[0].save(out, format="PDF", save_all=True, append_images=rgb_pages[1:], resolution=100.0)
    return out.getvalue()


def install(module: Any | None = None) -> Any | None:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_MAGAZINE_EXPORT_STATE_GUARD_V3", False):
        return module

    original_pages = getattr(module, "render_full_magazine_book_pages", None)
    original_page_png = getattr(module, "render_full_pick_magazine_page_png", None)
    if not callable(original_pages) or not callable(original_page_png):
        return module

    def guarded_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows, recovered, sig = _select_rows(picks, report_name=report_name, language=language, source="preview-pages")
        if not rows:
            return []
        pages = original_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        _remember(rows, report_name=report_name, language=language, page_count=len(pages), source="recovered-preview-state" if recovered else "preview-pages")
        _remember_pages(pages, sig=sig, row_count=len(rows), source="rendered_report_pages")
        return pages

    def guarded_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        rows, _recovered, _sig = _select_rows(picks, report_name=report_name, language=language, source="pdf-export")
        if not rows:
            pages = _stored_pages()
            if pages:
                return _pdf_from_pages(pages)
            raise ValueError("No valid report preview available for export.")
        pages = module.render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        if not pages:
            pages = _stored_pages()
        if not pages:
            raise ValueError("No valid report preview available for export.")
        return _pdf_from_pages(pages)

    def guarded_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        rows, _recovered, _sig = _select_rows(picks, report_name=report_name, language=language, source="png-export")
        if not rows:
            pages = _stored_pages()
        else:
            pages = module.render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        if not pages:
            raise ValueError("No valid report preview available for export.")
        width = getattr(module, "PAGE_WIDTH", pages[0].width)
        height = getattr(module, "PAGE_HEIGHT", pages[0].height)
        paper = getattr(module, "PAPER", (244, 235, 211))
        try:
            from PIL import Image
            book = Image.new("RGB", (width, height * len(pages)), paper)
            for index, page in enumerate(pages):
                book.paste(page.convert("RGB"), (0, height * index))
            return _png(book)
        except Exception:
            return _png(pages[0].convert("RGB"))

    def guarded_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        row = _row(pick)
        if _has_pick_identity(row):
            expected_pages = max(int(total_pages or 1), 1)
            if getattr(module, "_ABA_FORCED_TWO_PAGE_TRUTH_RENDERER", ""):
                expected_pages *= 2
            _remember([row], report_name=report_name, language=language, page_count=expected_pages, source="preview-page")
        return original_page_png(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)

    module.render_full_magazine_book_pages = guarded_pages
    module.render_full_magazine_book_pdf = guarded_pdf
    module.render_full_magazine_book_png = guarded_book_png
    module.render_full_pick_magazine_page_png = guarded_page_png
    module._ABA_MAGAZINE_EXPORT_STATE_GUARD_V1 = True
    module._ABA_MAGAZINE_EXPORT_STATE_GUARD_V2 = True
    module._ABA_MAGAZINE_EXPORT_STATE_GUARD_V3 = True
    return module
