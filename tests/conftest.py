import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A data dir in a temp location that is not inside any git repo."""
    path = tmp_path / "data"
    monkeypatch.setenv("MRCLEAN_DATA_DIR", str(path))
    return path
