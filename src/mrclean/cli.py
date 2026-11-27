"""Command-line entry point."""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from mrclean import __version__, pii_guard
from mrclean.errors import MRcleanError
from mrclean.logging_setup import configure_logging, redactor
from mrclean.paths import resolve_data_dir
from mrclean.profile import Address, Name, NameKind, Profile, load_profile, save_profile
from mrclean.registry import load_registry
from mrclean.registry.loader import execution_order
from mrclean.store import DB_FILE, KeyringKeyProvider, StaticKeyProvider, Store, StoreError

log = logging.getLogger("mrclean")


# --- init / doctor -----------------------------------------------------------


def _cmd_init(_: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(create=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    with Store.open(data_dir / DB_FILE, create=True):
        pass
    print(f"Data directory: {data_dir}")
    print("Encrypted store ready; its key is in your OS credential store.")
    print("Next: `mrclean key backup` (save the key in a password manager),")
    print("      then `mrclean profile add name` to describe who to look for.")
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    ok = True

    def report(good: bool, msg: str, fix: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"OK  {msg}" if good else f"ERR {fix or msg}")

    data_dir = resolve_data_dir()
    report(True, f"data dir is outside any git repo and sync folder: {data_dir}")
    report(
        (data_dir / pii_guard.DIGEST_FILE).is_file(),
        "PII commit guard is armed",
        "PII commit guard is NOT armed: run `mrclean profile add name`",
    )
    try:
        with Store.open() as store:
            profile = load_profile(store)
        report(True, "encrypted store opens with the key from the credential store")
        report(
            bool(profile.names),
            f"profile has {len(profile.names)} name(s)",
            "profile has no names yet: run `mrclean profile add name`",
        )
    except StoreError as exc:
        report(False, str(exc))
    try:
        brokers = load_registry()
        stale = [b.id for b in brokers.values() if b.is_stale()]
        report(not stale, f"{len(brokers)} brokers loaded; stale entries: {stale or 'none'}")
    except MRcleanError as exc:
        report(False, str(exc))
    return 0 if ok else 1


# --- key -----------------------------------------------------------------------


def _cmd_key_backup(_: argparse.Namespace) -> int:
    key = KeyringKeyProvider().get()
    if key is None:
        raise StoreError("No key in the credential store. Run `mrclean init` first.")
    print("Store this recovery key in a password manager. Anyone with it AND your")
    print("data folder can read your MRclean data. Clear your terminal afterwards.\n")
    print(key.hex())
    return 0


def _cmd_key_restore(_: argparse.Namespace) -> int:
    provider = KeyringKeyProvider()
    if provider.get() is not None:
        raise StoreError("A key is already present; refusing to overwrite it.")
    raw = getpass.getpass("Recovery key (hidden): ").strip()
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise StoreError("That isn't a valid recovery key.") from exc
    with Store.open(keys=StaticKeyProvider(key)):  # proves the key opens the store
        pass
    import keyring

    keyring.set_password(provider.service, provider.user, key.hex())
    print("Key restored.")
    return 0


# --- profile ---------------------------------------------------------------------


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _add_name() -> Name:
    kind = _ask("Kind (current/former/alias)", "current")
    return Name(
        first=_ask("First"),
        middle=_ask("Middle (optional)"),
        last=_ask("Last"),
        kind=NameKind(kind),
    )


def _add_address() -> Address:
    return Address(
        street=_ask("Street line (optional, used only to match results locally)"),
        city=_ask("City"),
        state=_ask("State (2 letters)").upper(),
        zip=_ask("ZIP (optional)"),
        current=_ask("Current address? (y/n)", "n").lower().startswith("y"),
    )


def _add_to(profile: Profile, kind: str) -> list[str]:
    """Prompt for one entry of ``kind``, add it, and return its guard identifiers."""
    match kind:
        case "name":
            name = _add_name()
            profile.names.append(name)
            return [name.full, f"{name.first} {name.last}"]
        case "address":
            address = _add_address()
            profile.addresses.append(address)
            return [address.street]
        case "phone" | "email" | "username":
            value = _ask(kind.capitalize())
            getattr(profile, f"{kind}s").append(value)
            return [value]
    raise MRcleanError(f"Unknown kind {kind!r}")


_KINDS = ("address", "email", "name", "phone", "username")


def _cmd_profile_add(args: argparse.Namespace) -> int:
    with Store.open() as store:
        profile = load_profile(store)
        new_identifiers = _add_to(profile, args.kind)
        profile = Profile.model_validate(profile.model_dump())  # re-validate after edit
        save_profile(store, profile)
    added = pii_guard.register(v for v in new_identifiers if v)
    print(f"Saved. {added} new identifier(s) added to the PII commit guard.")
    return 0


def _cmd_profile_show(_: argparse.Namespace) -> int:
    with Store.open() as store:
        profile = load_profile(store)
    print("Shown on screen only; never logged.")
    for kind in ("names", "addresses", "phones", "emails", "usernames"):
        for i, item in enumerate(getattr(profile, kind)):
            text = item.model_dump_json() if hasattr(item, "model_dump_json") else item
            print(f"{kind}[{i}]: {text}")
    return 0


def _cmd_profile_remove(args: argparse.Namespace) -> int:
    with Store.open() as store:
        profile = load_profile(store)
        items = getattr(profile, args.kind)
        if not 0 <= args.index < len(items):
            raise MRcleanError(f"No {args.kind}[{args.index}]")
        del items[args.index]
        save_profile(store, profile)
    print("Removed. (Its PII guard digest stays; extra protection is harmless.)")
    return 0


def _cmd_profile_variants(args: argparse.Namespace) -> int:
    with Store.open() as store:
        profile = load_profile(store)
    variants = profile.search_variants(with_city=args.with_city)
    print(f"{len(variants)} outbound queries per broker (shown on screen only):")
    for q in variants:
        middle = f"{q.middle} " if q.middle else ""
        city = f"{q.city}, " if q.city else ""
        print(f"  {q.first} {middle}{q.last}, {city}{q.state}")
    return 0


# --- registry ---------------------------------------------------------------------


def _cmd_registry_validate(args: argparse.Namespace) -> int:
    brokers = load_registry(args.dir) if args.dir else load_registry()
    print(f"OK: {len(brokers)} brokers valid")
    return 0


def _cmd_registry_list(_: argparse.Namespace) -> int:
    for b in execution_order(load_registry()):
        live = "" if b.verified_live else "  (not yet checked live)"
        print(f"P{b.priority}  {b.id:<24} {b.optout.method:<9} {b.optout.mode:<9}{live}")
    return 0


# --- wiring -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mrclean", description="Data broker scan and opt-out.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the data dir and encrypted store").set_defaults(
        func=_cmd_init
    )
    sub.add_parser("doctor", help="check that safety guards are in place").set_defaults(
        func=_cmd_doctor
    )

    key = sub.add_parser("key", help="back up or restore the store's encryption key")
    key_sub = key.add_subparsers(dest="key_command", required=True)
    key_sub.add_parser("backup", help="print the recovery key").set_defaults(func=_cmd_key_backup)
    key_sub.add_parser("restore", help="restore the key from a backup").set_defaults(
        func=_cmd_key_restore
    )

    prof = sub.add_parser("profile", help="manage who MRclean looks for")
    prof_sub = prof.add_subparsers(dest="profile_command", required=True)
    add = prof_sub.add_parser("add", help="add an identifier (interactive)")
    add.add_argument("kind", choices=_KINDS)
    add.set_defaults(func=_cmd_profile_add)
    prof_sub.add_parser("show", help="print the profile").set_defaults(func=_cmd_profile_show)
    rm = prof_sub.add_parser("remove", help="remove an entry by index (see `show`)")
    rm.add_argument("kind", choices=["names", "addresses", "phones", "emails", "usernames"])
    rm.add_argument("index", type=int)
    rm.set_defaults(func=_cmd_profile_remove)
    var = prof_sub.add_parser("variants", help="show the narrow search queries")
    var.add_argument("--with-city", action="store_true")
    var.set_defaults(func=_cmd_profile_variants)

    reg = sub.add_parser("registry", help="inspect the broker registry")
    reg_sub = reg.add_subparsers(dest="registry_command", required=True)
    val = reg_sub.add_parser("validate", help="validate broker YAML files")
    val.add_argument("--dir", type=Path)
    val.set_defaults(func=_cmd_registry_validate)
    reg_sub.add_parser("list", help="list brokers in execution order").set_defaults(
        func=_cmd_registry_list
    )

    pii = sub.add_parser("pii", help="manage the pre-commit PII guard")
    pii.add_argument("pii_args", nargs=argparse.REMAINDER)
    pii.set_defaults(func=lambda a: pii_guard.main(a.pii_args))
    return parser


def _arm_redactor() -> None:
    """Teach the log redactor this profile's literals, if the store opens."""
    try:
        with Store.open() as store:
            redactor.add_literals(load_profile(store).identifiers())
    except MRcleanError:
        pass  # no store yet (e.g. during init); pattern-based redaction still applies


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        log_dir: Path | None = resolve_data_dir() / "logs"
        if not log_dir.is_dir():  # don't create the data dir implicitly; `init` does that
            log_dir = None
    except MRcleanError:
        log_dir = None
    configure_logging(logging.DEBUG if args.verbose else logging.INFO, log_dir)
    if log_dir is not None and (log_dir.parent / DB_FILE).exists():
        _arm_redactor()
    try:
        return args.func(args)
    except MRcleanError as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
