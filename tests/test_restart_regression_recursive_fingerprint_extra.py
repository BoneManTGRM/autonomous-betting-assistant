from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_restart_hashes_do_not_change_restart_fingerprint_extra():
    a = {"x": {"generated_at_utc": "a", "dashboard_refresh_hash": "1", "stable": 2}}
    b = {"x": {"generated_at_utc": "b", "dashboard_refresh_hash": "2", "stable": 2}}
    assert package_fingerprint(a) == package_fingerprint(b)
