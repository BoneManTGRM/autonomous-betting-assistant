from pathlib import Path


def test_sitecustomize_exists():
    assert Path("sitecustomize.py").exists()
