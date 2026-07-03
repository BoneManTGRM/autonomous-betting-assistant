from __future__ import annotations


VERSION = "report_studio_bootstrap_v2_full_export_state_guard"


def install() -> None:
    try:
        from . import magazine_book_export as renderer
        from . import active_magazine_export_guard as guard
        from . import magazine_export_state_guard as export_state_guard
        from . import report_verification_gate as gate
        guard.install(renderer)
        original_page = renderer.render_full_pick_magazine_page

        def gated_pages(picks, background_image=None, report_name=None, logo_image=None, background_mode="hero_right", logo_mode="header", background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None, **kwargs):
            mode = kwargs.pop("report_mode", None)
            rows = [guard.normalize_row(row) for row in gate.build_report_rows(list(picks), mode=mode)]
            total = len(rows)
            return [original_page(row, background_image, report_name, index + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language) for index, row in enumerate(rows)]

        renderer.render_full_magazine_book_pages = gated_pages
        export_state_guard.install(renderer)
        renderer._ABA_VERIFICATION_GATE = gate.VERSION
        renderer._ABA_REPORT_STUDIO_BOOTSTRAP = VERSION
    except Exception:
        pass
    try:
        from . import magazine_sale_ready_patch as sale_module
        from . import active_magazine_export_guard as guard
        setattr(sale_module, "_force_truthful_gate", guard.normalize_row)
        setattr(sale_module, "_truth_pairs", guard.public_truth_pairs)
    except Exception:
        pass
