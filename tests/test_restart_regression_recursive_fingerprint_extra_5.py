from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_local_ids_do_not_change_restart_fingerprint_extra_5():
    a = {"stable": 1, "nested": {"local_review_id": "a", "local_review_hash": "b"}}
    b = {"stable": 1, "nested": {"local_review_id": "c", "local_review_hash": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
