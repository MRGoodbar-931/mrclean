"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from mrclean import __version__, pii_guard
from mrclean.errors import MRcleanError
from mrclean.logging_setup import configure_logging
from mrclean.paths import resolve_data_dir

log = logging.getLogger("mrclean")


def _cmd_init(_: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(create=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    print(f"Data directory: {data_dir}")
    print("Next: run `mrclean pii register` to arm the pre-commit PII guard.")
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    data_dir = resolve_data_dir()
    print(f"OK  data dir is outside any git repo and sync folder: {data_dir}")
    digests = data_dir / pii_guard.DIGEST_FILE
    if digests.is_file():
        print("OK  PII guard is armed")
        return 0
    print("ERR PII guard has no registered identifiers; commits will be blocked")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mrclean", description="Data broker scan and opt-out.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create the local data directory").set_defaults(func=_cmd_init)
    sub.add_parser("doctor", help="check that safety guards are in place").set_defaults(
        func=_cmd_doctor
    )
    pii = sub.add_parser("pii", help="manage the pre-commit PII guard")
    pii.add_argument("pii_args", nargs=argparse.REMAINDER)
    pii.set_defaults(func=lambda a: pii_guard.main(a.pii_args))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        log_dir: Path | None = resolve_data_dir() / "logs"
        if not log_dir.is_dir():  # don't create the data dir implicitly; `init` does that
            log_dir = None
    except MRcleanError:
        log_dir = None
    configure_logging(logging.DEBUG if args.verbose else logging.INFO, log_dir)
    try:
        return args.func(args)
    except MRcleanError as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
