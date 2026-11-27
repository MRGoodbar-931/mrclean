import datetime as dt
from pathlib import Path

import pytest
import yaml

from mrclean.registry import BROKERS_DIR, RegistryError, load_registry
from mrclean.registry.loader import execution_order


def test_shipped_registry_is_valid():
    brokers = load_registry()
    assert len(brokers) >= 10
    for b in brokers.values():
        assert b.sources, b.id


def _entry(**over):
    base = {
        "id": "example",
        "name": "Example",
        "url": "https://example.test",
        "category": "people_search",
        "priority": 1,
        "search": {"method": "manual"},
        "optout": {"method": "web_form", "url": "https://example.test/optout"},
        "sources": ["https://example.test/source"],
        "last_verified": "2026-01-01",
    }
    base.update(over)
    return base


def _write(tmp: Path, *entries):
    for e in entries:
        (tmp / f"{e['id']}.yaml").write_text(yaml.safe_dump(e))
    return tmp


def test_unknown_key_is_rejected(tmp_path):
    _write(tmp_path, _entry(optuot={"method": "email"}))
    with pytest.raises(RegistryError, match="optuot"):
        load_registry(tmp_path)


def test_id_must_match_filename(tmp_path):
    (tmp_path / "other.yaml").write_text(yaml.safe_dump(_entry()))
    with pytest.raises(RegistryError, match="filename"):
        load_registry(tmp_path)


def test_missing_parent_and_all_problems_reported_together(tmp_path):
    _write(tmp_path, _entry(parent="ghost"), _entry(id="bad", priority=9))
    with pytest.raises(RegistryError) as exc:
        load_registry(tmp_path)
    assert len(exc.value.problems) == 2


def test_email_method_needs_address(tmp_path):
    _write(tmp_path, _entry(optout={"method": "email"}))
    with pytest.raises(RegistryError, match="needs its"):
        load_registry(tmp_path)


@pytest.mark.parametrize(
    ("template", "inputs", "msg"),
    [
        ("https://x.test/{first}-{last}/{phone}", ["first", "last", "phone"], "unsupported"),
        ("https://x.test/{first}-{last}", ["first"], "exactly"),
    ],
)
def test_search_template_query_hygiene(tmp_path, template, inputs, msg):
    search = {"method": "http", "url_template": template, "inputs": inputs}
    _write(tmp_path, _entry(search=search))
    with pytest.raises(RegistryError, match=msg):
        load_registry(tmp_path)


def test_future_verification_date_rejected(tmp_path):
    future = (dt.date.today() + dt.timedelta(days=2)).isoformat()
    _write(tmp_path, _entry(last_verified=future))
    with pytest.raises(RegistryError, match="future"):
        load_registry(tmp_path)


def test_parents_run_before_children(tmp_path):
    _write(tmp_path, _entry(id="child", parent="up", priority=1), _entry(id="up", priority=3))
    assert [b.id for b in execution_order(load_registry(tmp_path))] == ["up", "child"]


def test_parent_cycle_detected(tmp_path):
    _write(tmp_path, _entry(id="aa", parent="bb"), _entry(id="bb", parent="aa"))
    with pytest.raises(RegistryError, match="cycle"):
        execution_order(load_registry(tmp_path))


@pytest.mark.parametrize(
    ("optout", "mode"),
    [
        ({"method": "email", "email": "privacy@x.test"}, "auto"),
        ({"method": "web_form", "url": "https://x.test"}, "assisted"),
        ({"method": "web_form", "url": "https://x.test", "captcha": True}, "manual"),
        ({"method": "email", "email": "p@x.test", "verification": ["id_document"]}, "manual"),
    ],
)
def test_optout_mode(tmp_path, optout, mode):
    _write(tmp_path, _entry(optout=optout))
    assert load_registry(tmp_path)["example"].optout.mode == mode


def test_registry_files_contain_no_personal_emails():
    """Broker files may name broker contact addresses only."""
    for path in BROKERS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        email = data["optout"].get("email")
        if email:
            assert not email.endswith(("@gmail.com", "@proton.me", "@protonmail.com")), path
