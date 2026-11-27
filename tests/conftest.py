import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A data dir in a temp location that is not inside any git repo."""
    path = tmp_path / "data"
    monkeypatch.setenv("MRCLEAN_DATA_DIR", str(path))
    return path


@pytest.fixture
def fake_keyring():
    """An in-memory keyring backend, so tests never touch the real credential store."""
    import keyring
    from keyring.backend import KeyringBackend

    class Memory(KeyringBackend):
        priority = 1

        def __init__(self):
            super().__init__()
            self.items = {}

        def get_password(self, service, username):
            return self.items.get((service, username))

        def set_password(self, service, username, password):
            self.items[(service, username)] = password

        def delete_password(self, service, username):
            self.items.pop((service, username), None)

    previous = keyring.get_keyring()
    backend = Memory()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)
