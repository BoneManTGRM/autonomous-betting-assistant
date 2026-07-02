import sitecustomize


def test_runtime_hooks_present():
    assert callable(sitecustomize.get_secret)
