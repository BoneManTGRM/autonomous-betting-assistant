from autonomous_betting_agent import sidebar_nav


def test_s52_ledger_page_in_sidebar():
    target = "pages/" + "subscriber_ledger" + ".py"
    assert target in {item[2] for item in sidebar_nav.TOOLS}


def test_s52_ledger_language_key_present():
    target = "subscriber_ledger" + "_language"
    assert target in set(sidebar_nav.LANGUAGE_KEYS)
