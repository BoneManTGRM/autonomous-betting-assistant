from __future__ import annotations


VERSION = "report_studio_bootstrap_v3_preserve_visible_rows"


def install() -> None:
    try:
        from . import magazine_book_export as renderer
        from . import active_magazine_export_guard as guard
        from . import magazine_export_state_guard as export_state_guard
        guard.install(renderer)
        original_page = renderer.render_full_pick_magazine_page

        def visible_rows_pages(picks, background_image=None, report_name=None, logo_image=None, background_mode="hero_right", logo_mode="header", background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None, **kwargs):
            rows = [guard.normalize_row(row) for row in list(picks)]
            if not rows:
                rows = [{"event": "No Verified Picks", "prediction": "NO VERIFIED BUYER PICKS"}]
            total = len(rows)
            return [original_page(row, background_image, report_name, index + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language) for index, row in enumerate(rows)]

        renderer.render_full_magazine_book_pages = visible_rows_pages
        export_state_guard.install(renderer)
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
