from autonomous_betting_agent import report_studio_bootstrap


def test_report_studio_bootstrap_installs_export_state_guard():
    from autonomous_betting_agent import magazine_book_export as renderer

    report_studio_bootstrap.install()

    assert getattr(renderer, "_ABA_REPORT_STUDIO_BOOTSTRAP", "") == report_studio_bootstrap.VERSION
    assert getattr(renderer, "_ABA_MAGAZINE_EXPORT_STATE_GUARD_V3", False) is True
    assert callable(renderer.render_full_magazine_book_pdf)


def _watchlist_rows():
    return [
        {
            "event": "Seattle Storm vs Phoenix Mercury",
            "prediction": "Spread: Phoenix Mercury -1.5",
            "report_source": "Uploaded / saved row",
            "truth": "VERIFY PRICE",
            "odds_status": "UPLOADED_ROW",
            "decimal_price": 1.65,
            "model_probability": 0.62,
            "model_market_edge": 0.011,
        },
        {
            "event": "San Diego Padres vs Los Angeles Dodgers",
            "prediction": "Run Line: Padres +1.5",
            "report_source": "Uploaded / saved row",
            "truth": "VERIFY PRICE",
            "odds_status": "UPLOADED_ROW",
            "decimal_price": 1.78,
            "model_probability": 0.58,
            "model_market_edge": 0.022,
        },
    ]


def test_report_studio_full_book_pages_preserve_visible_watchlist_rows():
    from autonomous_betting_agent import magazine_book_export as renderer

    report_studio_bootstrap.install()
    pages = renderer.render_full_magazine_book_pages(_watchlist_rows(), report_name="ABA Signal Pro")

    assert len(pages) == 4


def test_report_studio_full_pdf_preserves_visible_watchlist_rows():
    from autonomous_betting_agent import magazine_book_export as renderer

    report_studio_bootstrap.install()
    pdf_bytes = renderer.render_full_magazine_book_pdf(_watchlist_rows(), report_name="ABA Signal Pro")

    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.count(b"/Type /Page") >= 4
