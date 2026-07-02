from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_generated_at_does_not_change_restart_fingerprint_extra_6():
    a = {"stable": 1, "nested": {"generated_at_utc": "a"}}
    b = {"stable": 1, "nested": {"generated_at_utc": "b"}}
    assert package_fingerprint(a) == package_fingerprint(b)
