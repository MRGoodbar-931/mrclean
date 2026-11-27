"""Encrypted local state store.

The store is an ordinary SQLite database that lives on disk only as one
AES-256-GCM encrypted blob. MRclean decrypts it into memory on open and writes
it back, re-encrypted with a fresh nonce, after every committed transaction.
Writes are atomic (temp file, fsync, rename), so a crash leaves the previous
version intact. GCM authenticates the file, so tampering or a wrong key is
detected rather than producing garbage.

Why not SQLCipher: its Python bindings are a native extension that has lagged
new Python releases on Windows. ``cryptography`` ships version-independent
(abi3) wheels, so this works on any current CPython without a compiler.

The 32-byte key lives in the OS credential store (Windows Credential Manager,
macOS Keychain, Secret Service) via ``keyring`` and never touches disk in
plaintext. Trade-off: while MRclean runs, the decrypted database is in process
memory, which the OS may page to swap.
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mrclean.errors import MRcleanError
from mrclean.paths import resolve_data_dir

log = logging.getLogger(__name__)

DB_FILE = "mrclean.db"
KEYRING_SERVICE = "mrclean"
KEYRING_USER = "db-key"
KEY_BYTES = 32
MAGIC = b"MRCLEAN\x01"  # format id + version; authenticated as associated data
NONCE_BYTES = 12


class StoreError(MRcleanError):
    """The store can't be opened safely (wrong key, missing key, tampered, locked)."""


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
    """In-memory key, for tests and for checking a backed-up key."""

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


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    nonce = secrets.token_bytes(NONCE_BYTES)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, plaintext, MAGIC)


def decrypt(key: bytes, blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        raise StoreError("Not an MRclean store, or an unsupported format version.")
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_BYTES]
    try:
        return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + NONCE_BYTES :], MAGIC)
    except InvalidTag as exc:
        raise StoreError("Wrong database key, or the store file was modified.") from exc


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    if sys.platform != "win32":
        tmp.chmod(0o600)
    os.replace(tmp, path)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Hold an OS-level lock so two MRclean runs can't overwrite each other."""
    fh: IO[bytes] = path.open("a+b")
    try:
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise StoreError("Another MRclean run is using the store; try again later.") from exc
        yield
    finally:
        fh.close()  # closing the handle releases the lock on both platforms


class Store:
    """An in-memory SQLite connection persisted as an encrypted file."""

    def __init__(self, conn: sqlite3.Connection, path: Path, key: bytes, lock) -> None:
        self.conn = conn
        self.path = path
        self._key = key
        self._lock = lock

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
        if len(key) != KEY_BYTES:
            raise StoreError("The database key has the wrong length.")

        lock = _exclusive_lock(path.with_name(path.name + ".lock"))
        lock.__enter__()
        try:
            conn = sqlite3.connect(":memory:")
            if exists:
                conn.deserialize(decrypt(key, path.read_bytes()))
            conn.execute("PRAGMA foreign_keys = ON")
            store = cls(conn, path, key, lock)
            # A new store is first written by the first migration's transaction:
            # SQLite before ~3.46 can't serialize a database with zero pages.
            store._migrate()
            if not path.exists():
                raise StoreError("New store was not written; is MIGRATIONS empty?")
        except BaseException:
            lock.__exit__(None, None, None)
            raise
        return store

    def _persist(self) -> None:
        _atomic_write(self.path, encrypt(self._key, self.conn.serialize()))

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for index, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            with self.transaction():
                self.conn.executescript(sql)
                self.conn.execute(f"PRAGMA user_version = {index:d}")
            log.info("Store migrated to schema version %d", index)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit, then persist the encrypted file; roll back on any error."""
        try:
            yield self.conn
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        self._persist()

    def close(self) -> None:
        self.conn.close()
        self._lock.__exit__(None, None, None)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
