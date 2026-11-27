"""End-to-end CLI runs against a real encrypted store and a temp data dir."""

import builtins

from mrclean import cli


def _answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(it))


def test_full_first_run(data_dir, fake_keyring, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    assert (data_dir / "mrclean.db").is_file()

    _answers(monkeypatch, "current", "Jane", "Quinn", "Public")
    assert cli.main(["profile", "add", "name"]) == 0
    _answers(monkeypatch, "1234 Elm Street", "Spokane", "wa", "", "y")
    assert cli.main(["profile", "add", "address"]) == 0
    capsys.readouterr()

    assert cli.main(["profile", "variants"]) == 0
    out = capsys.readouterr().out
    assert "2 outbound queries" in out and "Jane Q Public, WA" in out

    # adding to the profile armed the commit guard with the same identifiers
    assert cli.main(["doctor"]) == 0, capsys.readouterr().out

    # nothing personal reached the log file, even at debug level
    assert cli.main(["-v", "profile", "show"]) == 0
    log_text = "".join(p.read_text() for p in (data_dir / "logs").glob("*.log*"))
    assert "Jane" not in log_text and "Elm" not in log_text


def test_key_backup_restore_round_trip(data_dir, fake_keyring, monkeypatch, capsys):
    cli.main(["init"])
    capsys.readouterr()
    cli.main(["key", "backup"])
    key = capsys.readouterr().out.strip().splitlines()[-1]
    fake_keyring.items.clear()  # simulate a new machine / wiped credential store
    assert cli.main(["profile", "show"]) == 2
    monkeypatch.setattr("getpass.getpass", lambda _p="": key)
    assert cli.main(["key", "restore"]) == 0
    assert cli.main(["profile", "show"]) == 0


def test_restore_rejects_wrong_key(data_dir, fake_keyring, monkeypatch):
    cli.main(["init"])
    fake_keyring.items.clear()
    monkeypatch.setattr("getpass.getpass", lambda _p="": "00" * 32)
    assert cli.main(["key", "restore"]) == 2
    assert not fake_keyring.items
