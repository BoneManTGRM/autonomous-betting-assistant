from pathlib import Path


def test_source_exists():
    assert Path("sitecustomize.py").exists()
