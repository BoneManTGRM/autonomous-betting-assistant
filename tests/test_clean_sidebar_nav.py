from autonomous_betting_agent import sidebar_nav


def test_clean_sidebar_has_core_and_advanced_groups():
    assert sidebar_nav.CORE_TOOLS
    assert sidebar_nav.ADVANCED_TOOLS
    assert len(sidebar_nav.CORE_TOOLS) < len(sidebar_nav.TOOLS)


def test_clean_sidebar_keeps_core_user_pages_visible():
    core_paths = {item[2] for item in sidebar_nav.CORE_TOOLS}
    required = {
        "pages/dashboard.py",
        "pages/signal_board.py",
        "pages/pro_predictor_volume.py",
        "pages/odds_lock_pro.py",
        "pages/fresh_odds_slate_builder.py",
        "pages/market_optimizer.py",
        "pages/pro_recommendation_cards.py",
        "pages/subscriber_intelligence.py",
        "pages/subscriber_ledger.py",
        "pages/subscriber_export_center.py",
        "pages/report_studio.py",
        "pages/proof_center.py",
    }

    assert required.issubset(core_paths)


def test_clean_sidebar_hides_internal_tools_by_default_group():
    core_paths = {item[2] for item in sidebar_nav.CORE_TOOLS}
    advanced_paths = {item[2] for item in sidebar_nav.ADVANCED_TOOLS}
    internal = {
        "pages/market_dashboard_bridge.py",
        "pages/market_workflow_integration.py",
        "pages/real_page_wiring_audit.py",
        "pages/proof_hardening_closeout.py",
        "pages/storage_diagnostics.py",
        "pages/reset_storage.py",
    }

    assert internal.isdisjoint(core_paths)
    assert internal.issubset(advanced_paths)


def test_clean_sidebar_keeps_legacy_tools_tuple_for_existing_tests():
    all_paths = {item[2] for item in sidebar_nav.TOOLS}
    grouped_paths = {item[2] for item in sidebar_nav.CORE_TOOLS + sidebar_nav.ADVANCED_TOOLS}

    assert all_paths == grouped_paths


def test_advanced_toggle_constant_present():
    assert sidebar_nav.ADVANCED_NAV_KEY == "aba_show_advanced_tools"
