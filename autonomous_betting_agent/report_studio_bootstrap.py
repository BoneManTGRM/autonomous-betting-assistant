from __future__ import annotations


VERSION = "report_studio_bootstrap_v5_paired_page_exports"


def install() -> None:
    try:
        from . import magazine_book_export as renderer
        from . import active_magazine_export_guard as guard
        from . import magazine_export_state_guard as export_state_guard
        try:
            from . import magazine_second_page_patch as second_page
        except Exception:
            second_page = None
        guard.install(renderer)
        original_page = renderer.render_full_pick_magazine_page

        def visible_rows_pages(picks, background_image=None, report_name=None, logo_image=None, background_mode="hero_right", logo_mode="header", background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None, **kwargs):
            rows = [guard.normalize_row(row) for row in list(picks)]
            if not rows:
                rows = [{"event": "No Verified Picks", "prediction": "NO VERIFIED PICKS"}]
            if second_page is None:
                total = len(rows)
                return [original_page(row, background_image, report_name, index + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language) for index, row in enumerate(rows)]
            total = len(rows) * 2
            pages = []
            for index, row in enumerate(rows):
                first_page = index * 2 + 1
                pages.append(original_page(row, background_image, report_name, first_page, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
                pages.append(second_page._draw_second_page(
                    renderer,
                    row,
                    background_image,
                    report_name,
                    first_page + 1,
                    total,
                    language,
                    logo_image,
                    background_mode,
                    logo_mode,
                    background_opacity,
                    logo_opacity,
                ))
            return pages

        renderer.render_full_magazine_book_pages = visible_rows_pages
        for marker in ("_ABA_MAGAZINE_EXPORT_STATE_GUARD_V1", "_ABA_MAGAZINE_EXPORT_STATE_GUARD_V2", "_ABA_MAGAZINE_EXPORT_STATE_GUARD_V3"):
            try:
                delattr(renderer, marker)
            except Exception:
                pass
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
