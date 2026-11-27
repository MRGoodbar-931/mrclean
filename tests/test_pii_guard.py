"""PII guard tests, including an end-to-end run against a real git commit.

All identifiers here are fictional (555-01xx numbers are reserved for fiction,
example.com is reserved by RFC 2606).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mrclean import pii_guard
from mrclean.errors import PIIGuardError

IDENTIFIERS = ["Jane Q Public", "jane.public@example.com", "(206) 555-0142", "1234 Elm Street"]


@pytest.fixture
def armed(data_dir):
    pii_guard.register(IDENTIFIERS)
    return pii_guard.DigestStore.load(pii_guard.digest_path())


def test_digest_file_never_contains_plaintext(armed, data_dir):
    raw = (data_dir / pii_guard.DIGEST_FILE).read_text().lower()
    for ident in IDENTIFIERS:
        assert pii_guard.normalize_identifier(ident) not in raw


@pytest.mark.parametrize(
    "line",
    [
        "name = 'jane   q. public'",
        "JANE.PUBLIC@EXAMPLE.COM",
        "call +1 206.555.0142",
        "addr: 1234 elm street, apt 2",
    ],
)
def test_detects_variants(armed, tmp_path, line):
    f = tmp_path / "x.py"
    f.write_text(f"ok\n{line}\n")
    assert [x.line for x in pii_guard.scan_file(f, armed)] == [2]


def test_clean_file_passes(armed, tmp_path):
    f = tmp_path / "x.py"
    f.write_text("def jane():\n    return 'public'\n")  # words split across lines: no match
    assert pii_guard.scan_file(f, armed) == []


def test_fails_closed_when_unarmed(data_dir):
    with pytest.raises(PIIGuardError):
        pii_guard.DigestStore.load(pii_guard.digest_path())
    assert pii_guard.main(["scan"]) == 2


def test_register_is_idempotent(data_dir):
    assert pii_guard.register(IDENTIFIERS) == len(IDENTIFIERS)
    assert pii_guard.register(IDENTIFIERS) == 0


def test_output_never_echoes_value(armed, tmp_path, capsys):
    f = tmp_path / "leak.md"
    f.write_text("Jane Q Public lives here\n")
    assert pii_guard.main(["scan", str(f)]) == 1
    err = capsys.readouterr().err
    assert "Jane" not in err and "leak.md:1" in err


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_real_git_commit_is_blocked(armed, tmp_path, data_dir):
    """Install the guard as a real pre-commit hook and attempt real commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "MRCLEAN_DATA_DIR": str(data_dir), "GIT_CONFIG_GLOBAL": os.devnull}

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    git("init", "-q")
    hook = repo / ".git" / "hooks" / "pre-commit"
    src = Path(pii_guard.__file__).resolve().parents[1]
    hook.write_text(
        "#!/bin/sh\n"
        f'PYTHONPATH="{src}" exec "{sys.executable}" -m mrclean.pii_guard scan '
        "$(git diff --cached --name-only --diff-filter=ACM)\n"
    )
    hook.chmod(0o755)

    (repo / "notes.md").write_text("Owner: Jane Q Public\n")
    git("add", "notes.md")
    blocked = git("commit", "-q", "-m", "leak")
    assert blocked.returncode != 0
    assert "Jane" not in blocked.stderr
    assert git("rev-parse", "HEAD").returncode != 0  # nothing was committed

    (repo / "notes.md").write_text("Owner: [your name here]\n")
    git("add", "notes.md")
    assert git("commit", "-q", "-m", "clean").returncode == 0
