"""Pre-commit guard: block commits that contain *your* identifiers.

Generic secret scanners (gitleaks) catch API keys, not your street address.
This guard checks staged text against your actual identifiers without
storing them in plaintext anywhere near the repo:

* ``mrclean-pii register`` prompts for identifiers (no echo, never argv) and
  stores HMAC-SHA256 digests, keyed with a random per-install salt, in the
  data dir, which is outside the repo by construction (see :mod:`mrclean.paths`).
* ``python -m mrclean.pii_guard scan FILE...`` (the pre-commit hook) tokenises
  each file into candidate identifiers, hashes them the same way and fails on
  any match. It reports file and line only, never the matched value.

The guard fails closed: if no identifiers are registered, scanning exits
non-zero so a fresh clone can't commit until the guard is armed.

Threat-model note: names and phone numbers are low-entropy, so the digest
file is brute-forceable by someone who already holds it. It stays in the
local data dir and is never committed; its job is to keep plaintext out of
the repo and out of the hook's own output.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import logging
import re
import secrets
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from mrclean.errors import PIIGuardError
from mrclean.paths import resolve_data_dir

log = logging.getLogger(__name__)

DIGEST_FILE = "pii_guard_digests.json"
MAX_NGRAM = 6  # longest word sequence considered, e.g. "1234 north main street apt 5"
MIN_TOKEN_CHARS = 3  # single tokens shorter than this are never registered or matched

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_text(value: str) -> str:
    """Lowercase and reduce to alphanumeric words joined by single spaces."""
    return " ".join(_WORD_RE.findall(value.lower()))


def normalize_identifier(value: str) -> str:
    """Normalise a user-supplied identifier to the form used for matching."""
    if _EMAIL_RE.fullmatch(value.strip()):
        return normalize_email(value)
    if _PHONE_RE.fullmatch(value.strip()):
        return normalize_phone(value)
    return normalize_text(value)


def candidates(line: str) -> Iterator[str]:
    """Yield every normalised substring of ``line`` that could be an identifier."""
    for match in _EMAIL_RE.finditer(line):
        yield normalize_email(match.group())
    for match in _PHONE_RE.finditer(line):
        yield normalize_phone(match.group())
    words = _WORD_RE.findall(line.lower())
    for size in range(1, MAX_NGRAM + 1):
        for start in range(len(words) - size + 1):
            gram = " ".join(words[start : start + size])
            if size > 1 or len(gram) >= MIN_TOKEN_CHARS:
                yield gram


@dataclass(frozen=True)
class DigestStore:
    salt: bytes
    digests: frozenset[str]

    def digest(self, normalized: str) -> str:
        return hmac.new(self.salt, normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    def matches(self, normalized: str) -> bool:
        return self.digest(normalized) in self.digests

    @classmethod
    def load(cls, path: Path) -> DigestStore:
        if not path.is_file():
            raise PIIGuardError(
                f"No PII guard digests at {path}. Run `mrclean pii register` before committing."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        store = cls(salt=bytes.fromhex(data["salt"]), digests=frozenset(data["digests"]))
        if not store.digests:
            raise PIIGuardError("PII guard digest file is empty. Register identifiers first.")
        return store

    def save(self, path: Path) -> None:
        payload = {"version": 1, "salt": self.salt.hex(), "digests": sorted(self.digests)}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)


def digest_path() -> Path:
    return resolve_data_dir(create=True) / DIGEST_FILE


def register(values: Iterable[str], path: Path | None = None) -> int:
    """Add identifiers to the digest store. Returns the number newly added."""
    path = path or digest_path()
    try:
        store = DigestStore.load(path)
    except PIIGuardError:
        store = DigestStore(salt=secrets.token_bytes(32), digests=frozenset())
    new: set[str] = set()
    for raw in values:
        normalized = normalize_identifier(raw)
        if " " not in normalized and len(normalized) < MIN_TOKEN_CHARS:
            log.warning("Skipped an identifier shorter than %d characters", MIN_TOKEN_CHARS)
            continue
        new.add(store.digest(normalized))
    added = len(new - store.digests)
    DigestStore(salt=store.salt, digests=store.digests | new).save(path)
    return added


@dataclass(frozen=True)
class Finding:
    path: str
    line: int


def scan_file(path: Path, store: DigestStore) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        log.debug("Skipping non-UTF-8 file %s", path)
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if any(store.matches(c) for c in candidates(line)):
            findings.append(Finding(str(path), lineno))
    return findings


def scan(paths: Sequence[Path], store: DigestStore) -> list[Finding]:
    return [f for p in paths if p.is_file() for f in scan_file(p, store)]


def _prompt_identifiers() -> list[str]:
    print("Enter identifiers one per line (input hidden). Blank line to finish.")
    values = []
    while value := getpass.getpass("identifier: ").strip():
        values.append(value)
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mrclean-pii", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("register", help="add identifiers to the guard (prompted, never echoed)")
    scan_p = sub.add_parser("scan", help="scan files; exit 1 on any match")
    scan_p.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)

    if args.command == "register":
        added = register(_prompt_identifiers())
        print(f"Registered {added} new identifier(s).")
        return 0

    try:
        store = DigestStore.load(digest_path())
    except PIIGuardError as exc:
        print(f"mrclean PII guard: {exc}", file=sys.stderr)
        return 2
    findings = scan(args.files, store)
    for f in findings:
        print(f"{f.path}:{f.line}: matches a registered personal identifier", file=sys.stderr)
    if findings:
        print("Commit blocked: remove personal data from the files above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
