import pytest

from mrclean.errors import MRcleanError
from mrclean.profile import Address, Name, NameKind, Profile, load_profile, save_profile
from mrclean.store import KeyringKeyProvider, StaticKeyProvider, Store, StoreError

FICTIONAL = Profile(
    names=[
        Name(first="Jane", middle="Quinn", last="Public"),
        Name(first="Jane", last="Doe", kind=NameKind.FORMER),
    ],
    addresses=[
        Address(street="1234 Elm Street", city="Spokane", state="WA", current=True),
        Address(city="Portland", state="OR"),
    ],
    phones=["206-555-0142"],
    emails=["jane.public@example.com"],
)


@pytest.fixture
def keys():
    return StaticKeyProvider()


def test_file_is_encrypted_at_rest(tmp_path, keys):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True) as store:
        save_profile(store, FICTIONAL)
    raw = db.read_bytes()
    assert not raw.startswith(b"SQLite format 3")
    for needle in (b"Jane", b"Public", b"1234 Elm", b"555-0142", b"example.com"):
        assert needle not in raw


def test_profile_round_trip(tmp_path, keys):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True) as store:
        save_profile(store, FICTIONAL)
    with Store.open(db, keys) as store:
        assert load_profile(store) == FICTIONAL


def test_wrong_key_is_refused(tmp_path, keys):
    db = tmp_path / "m.db"
    Store.open(db, keys, create=True).close()
    with pytest.raises(StoreError, match="Wrong database key"):
        Store.open(db, StaticKeyProvider(b"\x00" * 32))


def test_tampering_is_detected(tmp_path, keys):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True) as store:
        save_profile(store, FICTIONAL)
    blob = bytearray(db.read_bytes())
    blob[-5] ^= 0x01
    db.write_bytes(bytes(blob))
    with pytest.raises(StoreError, match="modified"):
        Store.open(db, keys)


def test_failed_write_keeps_previous_version(tmp_path, keys, monkeypatch):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True) as store:
        save_profile(store, FICTIONAL)
    before = db.read_bytes()

    def boom(*_a):
        raise OSError("disk full")

    with Store.open(db, keys) as store:
        monkeypatch.setattr("mrclean.store.os.replace", boom)
        with pytest.raises(OSError):
            save_profile(store, Profile())
        monkeypatch.undo()
    assert db.read_bytes() == before
    with Store.open(db, keys) as store:
        assert load_profile(store) == FICTIONAL


def test_second_concurrent_open_is_refused(tmp_path, keys):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True), pytest.raises(StoreError, match="Another"):
        Store.open(db, keys)
    Store.open(db, keys).close()  # lock released on close


def test_each_save_uses_a_fresh_nonce(tmp_path, keys):
    db = tmp_path / "m.db"
    with Store.open(db, keys, create=True) as store:
        save_profile(store, FICTIONAL)
        first = db.read_bytes()
        save_profile(store, FICTIONAL)
        assert db.read_bytes()[8:20] != first[8:20]


def test_missing_key_for_existing_store(tmp_path, keys):
    db = tmp_path / "m.db"
    Store.open(db, keys, create=True).close()
    with pytest.raises(StoreError, match="restore"):
        Store.open(db, StaticKeyProvider(None))


def test_no_store_without_create(tmp_path, keys):
    with pytest.raises(StoreError, match="init"):
        Store.open(tmp_path / "none.db", keys)


def test_migrations_are_idempotent(tmp_path, keys):
    db = tmp_path / "m.db"
    for _ in range(3):
        with Store.open(db, keys, create=True) as store:
            version = store.conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1


def test_keyring_provider_never_overwrites(fake_keyring):
    p = KeyringKeyProvider(service="mrclean-test")
    key = p.create()
    assert p.get() == key
    with pytest.raises(MRcleanError):
        p.create()


def test_search_variants_fan_out_and_stay_narrow():
    variants = FICTIONAL.search_variants()
    # 2 names x 2 states, and the middle-initial variant for the current name
    assert len(variants) == 6
    allowed = {"first", "last", "middle", "state", "city"}
    for q in variants:
        assert set(q.model_dump()) == allowed
        assert q.city == ""
    assert {q.middle for q in variants} == {"", "Q"}


def test_city_only_when_asked():
    assert {q.city for q in FICTIONAL.search_variants(with_city=True)} == {"Spokane", "Portland"}


def test_identifiers_cover_every_literal():
    ids = FICTIONAL.identifiers()
    for v in ("Jane Quinn Public", "Jane Public", "Jane Doe", "1234 Elm Street", "206-555-0142"):
        assert v in ids
