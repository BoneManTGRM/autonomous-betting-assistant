from __future__ import annotations

import os
from typing import Any, Iterable, Mapping


def _skip_runtime_patches() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() in {"1", "true", "yes"}


def _run_magazine_bridge() -> None:
    try:
        import sitecustomize as _aba_sitecustomize
        if hasattr(_aba_sitecustomize, "_ci_enabled"):
            _aba_sitecustomize._ci_enabled = lambda: False  # type: ignore[attr-defined]
        for name in (
            "_install_magazine_reload_bridge",
            "_install_magazine_polish_bridge",
            "_apply_magazine_display_bridge",
        ):
            func = getattr(_aba_sitecustomize, name, None)
            if callable(func):
                func()
    except Exception:
        pass


def _max_magazine_rows() -> int:
    raw = os.getenv("ABA_REPORT_STUDIO_MAX_BOOK_ROWS", "12")
    try:
        return max(1, int(raw))
    except Exception:
        return 12


def _limited_rows(rows: Iterable[Any]) -> list[Any]:
    data = list(rows or [])
    limit = _max_magazine_rows()
    return data[:limit] if len(data) > limit else data


def _text(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in {"", "nan", "none", "null", "n/a", "na", "--"} else text


def _first(data: Mapping[str, Any], names: Iterable[str]) -> str:
    for name in names:
        value = _text(data.get(name))
        if value:
            return value
    return ""


def _truth_label(value: Any) -> str:
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y", "verified", "live", "ok", "current"}:
        return "YES"
    if text in {"0", "false", "no", "n", "unverified", "not_verified", "not verified", "stale", "missing"}:
        return "NO"
    return "UNKNOWN"


def _install_spanish_report_text_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
        from autonomous_betting_agent import magazine_second_page_patch as page_two
        from autonomous_betting_agent.report_studio_spanish_ui import spanish_report_text
    except Exception:
        return

    for module in (book, page_two):
        original = getattr(module, "_tr", None)
        if not callable(original) or getattr(original, "_ABA_USERCUSTOMIZE_SPANISH_TEXT_GUARD", False):
            continue

        def patched(value: Any, language: str, _original=original) -> str:
            return spanish_report_text(_original(value, language), language)

        patched._ABA_USERCUSTOMIZE_SPANISH_TEXT_GUARD = True  # type: ignore[attr-defined]
        module._tr = patched


def _install_report_studio_memory_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
    except Exception:
        return
    if getattr(book, "_ABA_USERCUSTOMIZE_MEMORY_GUARD", False):
        return

    original_pdf = book.render_full_magazine_book_pdf
    original_png = book.render_full_magazine_book_png
    original_zip = book.render_full_magazine_zip
    original_pages = book.render_full_magazine_book_pages

    def guarded_pages(picks, *args: Any, **kwargs: Any):
        return original_pages(_limited_rows(picks), *args, **kwargs)

    def guarded_pdf(picks, *args: Any, **kwargs: Any):
        return original_pdf(_limited_rows(picks), *args, **kwargs)

    def guarded_png(picks, *args: Any, **kwargs: Any):
        return original_png(_limited_rows(picks), *args, **kwargs)

    def guarded_zip(picks, *args: Any, **kwargs: Any):
        return original_zip(_limited_rows(picks), *args, **kwargs)

    book.render_full_magazine_book_pages = guarded_pages
    book.render_full_magazine_book_pdf = guarded_pdf
    book.render_full_magazine_book_png = guarded_png
    book.render_full_magazine_zip = guarded_zip
    book._ABA_USERCUSTOMIZE_MEMORY_GUARD = True


def _install_report_export_verification_gate() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
        from autonomous_betting_agent.report_export_verification import patch_magazine_renderer
    except Exception:
        return
    try:
        patch_magazine_renderer(book)
    except Exception:
        pass


def _install_verified_price_magazine_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as book
    except Exception:
        return
    original = getattr(book, "_pairs", None)
    if not callable(original) or getattr(original, "_ABA_USERCUSTOMIZE_VERIFIED_PRICE_GUARD", False):
        return

    label_es = {
        "VERIFIED PRICE": "CUOTA VERIFICADA",
        "PRICE": "CUOTA",
        "BOOK": "CASA",
        "MARKET STATUS": "ESTADO DEL MERCADO",
        "ODDS SOURCE": "FUENTE DE CUOTAS",
    }

    def _localized_pair(label: str, value: str, language: str) -> tuple[str, str]:
        if language == "es":
            yes_no = value.replace("YES", "SÍ").replace("NO", "NO").replace("UNKNOWN", "SIN CONFIRMAR")
            yes_no = yes_no.replace("Not verified", "No verificada").replace("Verified", "Verificada")
            return label_es.get(label, label), yes_no
        return label, value

    def patched(row: Any, lang: str) -> list[tuple[str, str]]:
        data = book._row(row)
        base = list(original(row, lang) or [])
        price = _first(data, ("verified_price", "current_verified_price", "decimal_price", "best_price", "odds_at_pick", "american_odds", "odds_american", "odds"))
        book_name = _first(data, ("bookmaker", "sportsbook", "book", "odds_book"))
        source = _first(data, ("odds_source", "price_source", "data_source", "provider", "api_source"))
        timestamp = _first(data, ("odds_timestamp", "price_timestamp", "odds_updated_at", "line_timestamp", "locked_at_utc", "commence_time"))
        status = _first(data, ("export_verification_status", "market_status", "line_status", "odds_status", "market_state", "live_status"))
        verified = _truth_label(_first(data, ("odds_verified", "price_verified", "verified_odds", "live_odds_verified", "current_price_verified", "source_verified")))

        verification_value = "Not verified"
        if verified == "YES":
            verification_value = "Verified"
        elif verified == "UNKNOWN" and source and "upload" not in source.lower() and "cached" not in source.lower():
            verification_value = "Source present"
        if price:
            verification_value = f"{verification_value} · {price}"
        if timestamp:
            verification_value = f"{verification_value} · {timestamp}"

        rows: list[tuple[str, str]] = [_localized_pair("VERIFIED PRICE", verification_value, lang)]
        if price:
            rows.append(_localized_pair("PRICE", price, lang))
        if book_name:
            rows.append(_localized_pair("BOOK", book_name, lang))
        if status:
            rows.append(_localized_pair("MARKET STATUS", status, lang))
        if source:
            rows.append(_localized_pair("ODDS SOURCE", source, lang))

        seen = {label.lower() for label, _value in rows}
        for label, value in base:
            key = str(label).lower()
            if key not in seen and value:
                rows.append((label, value))
                seen.add(key)
        return rows[:5]

    patched._ABA_USERCUSTOMIZE_VERIFIED_PRICE_GUARD = True  # type: ignore[attr-defined]
    book._pairs = patched


def _install_dynamic_odds_baseline_guard() -> None:
    try:
        from autonomous_betting_agent import dynamic_odds_shadow_memory as memory
    except Exception:
        return
    original = getattr(memory, "shadow_model_status", None)
    if not callable(original) or getattr(original, "_ABA_USERCUSTOMIZE_BASELINE_GUARD", False):
        return

    def patched(model_payload: Mapping[str, Any] | None, source: str = "saved_model") -> dict[str, Any]:
        status = dict(original(model_payload, source))
        wins = int(status.get("wins") or 0)
        losses = int(status.get("losses") or 0)
        baseline = memory.protected_baseline_metrics(wins, losses)
        for key, value in baseline.items():
            if status.get(key) is None:
                status[key] = value
        if not status.get("model_loaded"):
            status["model_quality_label"] = "NO SAVED MODEL" if not model_payload else "NEEDS TRAINING DATA"
            status["model_quality_reason"] = "train_or_import_shadow_model"
        return status

    patched._ABA_USERCUSTOMIZE_BASELINE_GUARD = True  # type: ignore[attr-defined]
    memory.shadow_model_status = patched
    try:
        from autonomous_betting_agent import dynamic_odds_display
        dynamic_odds_display.shadow_model_status = patched
    except Exception:
        pass
    try:
        from autonomous_betting_agent import odds_math_control_panel
        odds_math_control_panel.shadow_model_status = patched
    except Exception:
        pass


if not _skip_runtime_patches():
    _run_magazine_bridge()

    try:
        from autonomous_betting_agent.proof_persistence_patch import install_proof_persistence_patch
        install_proof_persistence_patch()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_report_cleanup_patch import install as install_magazine_report_cleanup
        install_magazine_report_cleanup()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_provider_usage_patch import install as install_magazine_provider_usage
        install_magazine_provider_usage()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
        install_magazine_report_polish()
    except Exception:
        pass

    _run_magazine_bridge()
    _install_spanish_report_text_guard()
    _install_report_studio_memory_guard()
    _install_report_export_verification_gate()
    _install_verified_price_magazine_guard()
    _install_dynamic_odds_baseline_guard()

    try:
        from autonomous_betting_agent.sidebar_tools import install_sidebar_tools
        install_sidebar_tools()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
        install_odds_breakdown_normalizer()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
        install_proof_dashboard_patch()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
        install_streamlit_local_user_selector()
    except Exception:
        pass
