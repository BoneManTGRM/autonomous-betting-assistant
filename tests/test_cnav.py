from autonomous_betting_agent import sidebar_nav


def test_cnav_page_present():
    paths = {item[2] for item in sidebar_nav.TOOLS}
    target = "pages/" + "pro_recommendation_cards" + ".py"
    assert target in paths


def test_cnav_language_present():
    target = "pro_recommendation_cards" + "_language"
    assert target in set(sidebar_nav.LANGUAGE_KEYS)
