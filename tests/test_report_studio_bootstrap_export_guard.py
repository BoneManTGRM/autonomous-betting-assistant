from autonomous_betting_agent import report_studio_bootstrap


def test_report_studio_bootstrap_installs_export_state_guard():
    from autonomous_betting_agent import magazine_book_export as renderer

    report_studio_bootstrap.install()

    assert getattr(renderer, "_ABA_REPORT_STUDIO_BOOTSTRAP", "") == report_studio_bootstrap.VERSION
    assert getattr(renderer, "_ABA_MAGAZINE_EXPORT_STATE_GUARD_V3", False) is True
    assert callable(renderer.render_full_magazine_book_pdf)
