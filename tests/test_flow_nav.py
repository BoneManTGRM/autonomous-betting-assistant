from autonomous_betting_agent import sidebar_nav


def test_flow_pages_in_sidebar():
    paths = {item[2] for item in sidebar_nav.TOOLS}
    required = {
        "pages/market_optimizer.py",
        "pages/market_dashboard_bridge.py",
        "pages/market_workflow_integration.py",
        "pages/real_page_wiring_audit.py",
    }

    assert required.issubset(paths)


def test_flow_language_keys_present():
    required = {
        "market_optimizer_language",
        "market_dashboard_bridge_language",
        "market_workflow_integration_language",
        "real_page_wiring_audit_language",
    }

    assert required.issubset(set(sidebar_nav.LANGUAGE_KEYS))
