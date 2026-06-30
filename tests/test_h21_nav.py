from autonomous_betting_agent import sidebar_nav


def test_h21_closeout_page_in_sidebar():
    target = "pages/" + "proof_hardening_closeout" + ".py"
    assert target in {item[2] for item in sidebar_nav.TOOLS}


def test_h21_closeout_language_key_present():
    target = "proof_hardening_closeout" + "_language"
    assert target in set(sidebar_nav.LANGUAGE_KEYS)
