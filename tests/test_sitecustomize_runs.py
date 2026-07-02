import sitecustomize


def test_sitecustomize_imported():
    assert hasattr(sitecustomize, "get_secret")
