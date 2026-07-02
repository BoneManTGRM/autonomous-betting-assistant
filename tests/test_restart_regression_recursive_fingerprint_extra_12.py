from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_volatile_keys_do_not_change_restart_fingerprint_extra_12():
    a = {"stable": 1, "nested": {"dashboard_refresh_hash": "a"}}
    b = {"stable": 1, "nested": {"dashboard_refresh_hash": "b"}}
    assert package_fingerprint(a) == package_fingerprint(b)
