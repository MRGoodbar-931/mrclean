"""Encrypted local state store (SQLCipher).

The database key is 32 random bytes kept in the OS credential store (Windows
Credential Manager, macOS Keychain, Secret Service on Linux) through
``keyring``. It never touches disk in plaintext, and scheduled runs can open
the store without a passphrase.

The store refuses to open if the SQLite library in use isn't SQLCipher, so a
broken install can't silently write plaintext.
"""

from __future__ import annotations

import logging
import secrets
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

import sqlcipher3

from mrclean.errors import MRcleanError
from mrclean.paths import resolve_data_dir

log = logging.getLogger(__name__)

DB_FILE = "mrclean.db"
KEYRING_SERVICE = "mrclean"
KEYRING_USER = "db-key"
KEY_BYTES = 32


class StoreError(MRcleanError):
    """The store can't be opened safely (wrong key, missing key, not encrypted)."""


class KeyProvider(Protocol):
    def get(self) -> bytes | None: ...

    def create(self) -> bytes: ...


class KeyringKeyProvider:
    """Keeps the database key in the OS credential store."""

    def __init__(self, service: str = KEYRING_SERVICE, user: str = KEYRING_USER) -> None:
        self.service, self.user = service, user

    def get(self) -> bytes | None:
        import keyring

        value = keyring.get_password(self.service, self.user)
        return bytes.fromhex(value) if value else None

    def create(self) -> bytes:
        import keyring

        if self.get() is not None:
            raise StoreError("A database key already exists; refusing to overwrite it.")
        key = secrets.token_bytes(KEY_BYTES)
        keyring.set_password(self.service, self.user, key.hex())
        return key


class StaticKeyProvider:
    """In-memory key, for tests and for restoring from a backup key."""

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key

    def get(self) -> bytes | None:
        return self._key

    def create(self) -> bytes:
        if self._key is None:
            self._key = secrets.token_bytes(KEY_BYTES)
        return self._key


# Ordered, append-only. Never edit a shipped migration; add a new one.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    """,
)


class Store:
    """A thin wrapper over an encrypted SQLite connection."""

    def __init__(self, conn: sqlcipher3.Connection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    def open(
        cls,
        path: Path | None = None,
        keys: KeyProvider | None = None,
        *,
        create: bool = False,
    ) -> Store:
        keys = keys or KeyringKeyProvider()
        path = path or resolve_data_dir(create=create) / DB_FILE
        exists = path.exists()
        if not exists and not create:
            raise StoreError(f"No store at {path}. Run `mrclean init` first.")

        key = keys.get()
        if key is None:
            if exists:
                raise StoreError(
                    "The store exists but its key isn't in the credential store. "
                    "Restore it with `mrclean key restore`."
                )
            key = keys.create()

        conn = sqlcipher3.connect(str(path))
        try:
            cipher = conn.execute("PRAGMA cipher_version").fetchone()
            if not cipher or not cipher[0]:
                raise StoreError(
                    "SQLite library isn't SQLCipher; refusing to store data unencrypted."
                )
            conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            except sqlcipher3.DatabaseError as exc:
                raise StoreError("Wrong database key, or the file isn't an MRclean store.") from exc
        except BaseException:
            conn.close()
            raise

        if not exists and sys.platform != "win32":
            path.chmod(0o600)
        store = cls(conn, path)
        store._migrate()
        return store

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for index, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            with self.transaction():
                self.conn.executescript(sql)
                self.conn.execute(f"PRAGMA user_version = {index:d}")
            log.info("Store migrated to schema version %d", index)

    @contextmanager
    def transaction(self) -> Iterator[sqlcipher3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_store(create: bool = False, keys: KeyProvider | None = None) -> Store:
    return Store.open(keys=keys, create=create)


StoreFactory = Callable[[], Store]
